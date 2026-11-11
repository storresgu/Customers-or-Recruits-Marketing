"""Run or prepare a registered matched experiment from an explicit JSON design."""
import argparse
import copy
from dataclasses import dataclass, replace
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
import re
from time import perf_counter
from . import MODEL_VERSION, SPEC_VERSION
from .config import ModelConfig, canonical_json, read_json, require_int, require_number
from .initialize import code_hash, _write_csv, _write_json
from .model import Population
from .outcomes import (participant_rows, participant_outcomes, enriched_monthly,
                       window_summary, paired_effects, summarize_pairs)
from .randomness import RNG_SCHEMA, Process
from .run import export_simulation
from .simulation import Simulation

DESIGN_SCHEMA = "article25-experiment-v1"
SEED_SCHEMA = "article25-pair-seed-v1"
DEFAULT_WINDOWS = [
    {"name": "pre", "start": 49, "end": 60},
    {"name": "immediate", "start": 61, "end": 72},
    {"name": "late", "start": 109, "end": 120},
]
IDENTITY_COLUMNS = ["model_version", "code_hash", "config_hash", "experiment_id", "scenario_id",
                    "replicate_id", "pair_id", "seed", "condition", "run_id"]


def digest(value):
    return hashlib.sha256(canonical_json(value).encode()).hexdigest()


def identifier(value, name):
    if (not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,63}", value)
            or "__" in value):
        raise ValueError(f"Invalid {name}: use 1–64 safe characters without double underscores")


@dataclass(frozen=True)
class ExperimentDesign:
    experiment_id: str
    purpose: str
    master_seed: int
    replicates: int
    shock_multiplier: float
    base_config: ModelConfig
    scenarios: tuple
    windows: tuple

    def __post_init__(self):
        identifier(self.experiment_id, "experiment_id")
        if self.purpose not in ("verification", "pilot", "main", "sensitivity", "robustness"):
            raise ValueError("Unknown experiment purpose")
        require_int("master_seed", self.master_seed)
        require_int("replicates", self.replicates, 1)
        require_number("shock_multiplier", self.shock_multiplier, maximum=1)
        if not isinstance(self.base_config, ModelConfig) or self.base_config.recruitment_multiplier != 1:
            raise ValueError("Base configuration must be an untreated control")
        if not isinstance(self.scenarios, (tuple, list)) or not self.scenarios:
            raise ValueError("At least one scenario is required")
        names = set()
        configs = []
        for scenario in self.scenarios:
            if type(scenario) is not dict or set(scenario) != {"scenario_id", "overrides"}:
                raise ValueError("Each scenario needs scenario_id and overrides only")
            sid = scenario["scenario_id"]
            identifier(sid, "scenario_id")
            if sid in names:
                raise ValueError("Duplicate scenario_id")
            names.add(sid)
            overrides = scenario["overrides"]
            if type(overrides) is not dict or "recruitment_multiplier" in overrides:
                raise ValueError("Scenario overrides cannot set the treatment multiplier")
            configs.append(ModelConfig.from_dict({**self.base_config.to_dict(), **overrides}))
        if not isinstance(self.windows, (tuple, list)) or not self.windows:
            raise ValueError("Reporting windows are required")
        window_names = set()
        previous_end = 0
        for window in self.windows:
            if type(window) is not dict or set(window) != {"name", "start", "end"}:
                raise ValueError("A window requires name, start, and end only")
            identifier(window["name"], "window name")
            require_int("window start", window["start"], 1)
            require_int("window end", window["end"], 1)
            if window["name"] in window_names or not previous_end < window["start"] <= window["end"]:
                raise ValueError("Windows must have unique names and be ordered and disjoint")
            window_names.add(window["name"])
            previous_end = window["end"]
            for cfg in configs:
                if window["end"] > cfg.horizon_months:
                    raise ValueError("Window extends beyond the horizon")
                if window["start"] < cfg.shock_start_month <= window["end"]:
                    raise ValueError("Window straddles the shock boundary")
        for cfg in configs:
            if not 1 < cfg.shock_start_month <= cfg.horizon_months:
                raise ValueError("A matched design needs both a preshock prefix and a postshock period")
            if not (any(w["end"] < cfg.shock_start_month for w in self.windows)
                    and any(w["start"] >= cfg.shock_start_month for w in self.windows)):
                raise ValueError("Include at least one pre and one post window")

    @classmethod
    def from_dict(cls, data):
        expected = {"schema", "experiment_id", "purpose", "master_seed", "replicates",
                    "shock_multiplier", "base_config", "scenarios", "windows"}
        if type(data) is not dict or set(data) != expected or data["schema"] != DESIGN_SCHEMA:
            raise ValueError("Incomplete or unsupported experiment design")
        if type(data["scenarios"]) is not list or type(data["windows"]) is not list:
            raise ValueError("scenarios and windows must be JSON arrays")
        return cls(data["experiment_id"], data["purpose"], data["master_seed"], data["replicates"],
                   data["shock_multiplier"], ModelConfig.from_dict(data["base_config"]),
                   tuple(copy.deepcopy(data["scenarios"])), tuple(copy.deepcopy(data["windows"])))

    def to_dict(self):
        return {"schema": DESIGN_SCHEMA, "experiment_id": self.experiment_id, "purpose": self.purpose,
                "master_seed": self.master_seed, "replicates": self.replicates,
                "shock_multiplier": self.shock_multiplier, "base_config": self.base_config.to_dict(),
                "scenarios": copy.deepcopy(list(self.scenarios)), "windows": copy.deepcopy(list(self.windows))}

    @property
    def design_hash(self):
        return digest(self.to_dict())

    def registry(self):
        # Order-independent identifiers; a global collision check forbids accidental seed reuse.
        self.__post_init__()
        rows, seen_seeds = [], set()
        source_hash = code_hash()
        for scenario in self.scenarios:
            sid = scenario["scenario_id"]
            cfg = ModelConfig.from_dict({**self.base_config.to_dict(), **scenario["overrides"]})
            for replicate in range(1, self.replicates+1):
                seed = int(digest([SEED_SCHEMA, self.master_seed, self.experiment_id, sid, replicate])[:8], 16)
                if seed in seen_seeds:
                    raise ValueError("Seed collision: choose and record a different master seed")
                seen_seeds.add(seed)
                pair = f"{self.experiment_id}__{sid}__r{replicate:04d}"
                for condition, multiplier in (("control", 1.0), ("shock", self.shock_multiplier)):
                    branch_config = replace(cfg, recruitment_multiplier=float(multiplier))
                    rows.append({"model_version": MODEL_VERSION, "code_hash": source_hash,
                                 "config_hash": branch_config.config_hash,
                                 "experiment_id": self.experiment_id, "scenario_id": sid,
                                 "replicate_id": replicate, "pair_id": pair, "seed": seed,
                                 "condition": condition, "run_id": f"{pair}__{condition}",
                                 "config": branch_config.to_dict(), "status": "planned"})
        return rows


@dataclass
class MatchedPair:
    initial: Population
    prefix: Simulation
    control: Simulation
    shock: Simulation
    prefix_seconds: float
    control_seconds: float
    shock_seconds: float

    def validate(self):
        for simulation in (self.prefix, self.control, self.shock):
            simulation.validate()
        cfg = self.control.population.config
        boundary = cfg.shock_start_month-1
        if (self.initial.month != 0 or self.prefix.start_month != 0
                or self.prefix.population.month != boundary):
            raise ValueError("Common prefix must cover initialization through the branch boundary")
        if self.initial.config != cfg or self.prefix.population.config != cfg or cfg.recruitment_multiplier != 1:
            raise ValueError("Initial state and common prefix must use the control configuration")
        shock_cfg = self.shock.population.config
        if replace(shock_cfg, recruitment_multiplier=1.0) != cfg:
            raise ValueError("Paired configurations differ outside the recruitment multiplier")
        for simulation in (self.control, self.shock):
            if (simulation.start_month != 0 or simulation.population.month != cfg.horizon_months
                    or simulation.population.seed != self.initial.seed
                    or simulation.social_hash != self.prefix.social_hash):
                raise ValueError("Branch horizon, seed, start, or social graph differs")
            for name in ("monthly", "events", "transactions", "earnings"):
                before = [r for r in getattr(simulation, name) if r["month"] <= boundary]
                if before != getattr(self.prefix, name):
                    raise ValueError("Branch history differs before intervention")
        if shock_cfg.recruitment_multiplier == 0 and any(
            r["new_recruits"] for r in self.shock.monthly if r["month"] > boundary):
            raise ValueError("Complete recruitment interruption produced an enrollment")
        if shock_cfg.recruitment_multiplier == 1 and self.control.to_dict() != self.shock.to_dict():
            raise ValueError("Two control branches must match exactly")


def run_pair(config, seed, shock_multiplier=0.0):
    require_number("shock_multiplier", shock_multiplier, maximum=1)
    if config.recruitment_multiplier != 1 or not 1 < config.shock_start_month <= config.horizon_months:
        raise ValueError("Matched runs require a control with an interior shock boundary")
    start = perf_counter()
    prefix = Simulation.initialize(config, seed)
    initial = prefix.population.clone()
    prefix.run(config.shock_start_month-1)
    prefix_seconds = perf_counter()-start
    # Clone the complete checkpoint BEFORE altering the sole intervention field.
    control = prefix.clone()
    shock = prefix.clone()
    if control.to_dict() != shock.to_dict():
        raise ValueError("Pre-intervention clones differ")
    # Preserve byte-identical control metadata for a null intervention (1 == 1.0).
    multiplier = config.recruitment_multiplier if shock_multiplier == 1 else float(shock_multiplier)
    shock.population.config = replace(config, recruitment_multiplier=multiplier)
    start = perf_counter()
    control.run()
    control_seconds = perf_counter()-start
    start = perf_counter()
    shock.run()
    pair = MatchedPair(initial, prefix, control, shock, prefix_seconds, control_seconds, perf_counter()-start)
    pair.validate()
    return pair


def _csv(path, rows, empty_columns=()):
    _write_csv(path, list(rows[0]) if rows else list(empty_columns), rows)


def _hash_files(path):
    return {str(p.relative_to(path)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(path.rglob("*")) if p.is_file() and p != path/"manifest.json"}


def _identity(row):
    return {key: row[key] for key in IDENTITY_COLUMNS}


def export_pair(pair, design, records, output):
    pair.validate()
    if len(records) != 2 or [r["condition"] for r in records] != ["control", "shock"]:
        raise ValueError("Export requires one ordered control/shock registry pair")
    for row, sim in zip(records, (pair.control, pair.shock)):
        if (row["config"] != sim.population.config.to_dict() or row["seed"] != sim.population.seed
                or row["config_hash"] != sim.population.config.config_hash
                or row["experiment_id"] != design.experiment_id
                or row["code_hash"] != code_hash() or row["model_version"] != MODEL_VERSION):
            raise ValueError("Run registry does not describe the exported simulation")
    if any(records[0][key] != records[1][key] for key in
           ("experiment_id", "scenario_id", "replicate_id", "pair_id", "seed")):
        raise ValueError("Run records are not a matched pair")
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)
    pair.initial.save_json(path/"initial_state.json")
    checkpoint_name = f"checkpoint_{pair.prefix.population.month:03d}.json"
    pair.prefix.save_json(path/checkpoint_name)
    if Population.load_json(path/"initial_state.json").state_hash != pair.initial.state_hash:
        raise ValueError("Initial-state readback failed")
    if Simulation.load_json(path/checkpoint_name).to_dict() != pair.prefix.to_dict():
        raise ValueError("Common-checkpoint readback failed")
    monthly, participants, summaries = [], [], []
    run_manifests = []
    for row, simulation, seconds in zip(records, (pair.control, pair.shock),
                                         (pair.control_seconds, pair.shock_seconds)):
        identity = _identity(row)
        branch = path/row["condition"]
        export_simulation(simulation, branch)
        people = participant_rows(simulation.population)
        participants.extend({**identity, **r} for r in people)
        monthly.extend({**identity, **r} for r in enriched_monthly(simulation))
        summary = {**identity, **participant_outcomes(people)}
        for window in window_summary(simulation.monthly, design.windows):
            for key, value in window.items():
                if key != "window":
                    summary[window["window"]+"_"+key] = value
        summaries.append(summary)
        run_manifest = {**identity, "spec_version": SPEC_VERSION, "rng_schema": RNG_SCHEMA,
                        "config": row["config"], "status": "completed",
                        "environment": environment(),
                        "initial_state_id": pair.initial.state_hash,
                        "common_checkpoint_sha256": pair.prefix.to_dict()["sha256"],
                        "prefix_runtime_seconds_shared": pair.prefix_seconds,
                        "branch_runtime_seconds": seconds,
                        "final_state_hash": simulation.population.state_hash}
        run_manifests.append(run_manifest)
    pair_identity = {key: records[0][key] for key in (
        "model_version", "code_hash", "experiment_id", "scenario_id", "replicate_id", "pair_id", "seed")}
    pair_identity.update(control_config_hash=records[0]["config_hash"], shock_config_hash=records[1]["config_hash"])
    effects = [{**pair_identity, **r} for r in paired_effects(pair.control.monthly, pair.shock.monthly, design.windows)]
    _csv(path/"monthly_metrics.csv", monthly)
    _csv(path/"participant_summary.csv", participants, [*IDENTITY_COLUMNS, "person_id", "final_state"])
    _csv(path/"run_summary.csv", summaries)
    _csv(path/"paired_effects.csv", effects)
    _write_json(path/"paired_effects.json", effects)
    _write_json(path/"run_manifest.json", run_manifests)
    _write_json(path/"manifest.json", {
        **pair_identity, "status": "completed", "design_hash": design.design_hash,
        "initial_state_id": pair.initial.state_hash,
        "common_checkpoint_sha256": pair.prefix.to_dict()["sha256"],
        "common_prefix_months": pair.prefix.population.month,
        "prefix_equality_checked": True,
        "zero_postshock_enrollment_checked": pair.shock.population.config.recruitment_multiplier == 0,
        "network_seed_hex": hex(pair.initial.random.seed_for(Process.NETWORK)),
        "process_registry": {p.name: p.value for p in Process},
        "environment": environment(), "files_sha256": _hash_files(path)})
    return effects, summaries


def environment():
    return {"python": platform.python_version(), "platform": platform.platform(),
            "dependencies": {name: importlib.metadata.version(name) for name in ("numpy", "networkx")}}


def execute_design(design, output, prepare_only=False):
    # Resolve and validate the entire registry before creating output or simulating.
    registry = design.registry()
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)
    _write_json(path/"design_resolved.json", design.to_dict())
    _write_json(path/"run_registry.json", registry)
    _csv(path/"seed_registry.csv", [{**_identity(r), "status": r["status"]} for r in registry])
    manifest = {"schema": DESIGN_SCHEMA, "experiment_id": design.experiment_id,
                "purpose": design.purpose, "model_version": MODEL_VERSION, "spec_version": SPEC_VERSION,
                "rng_schema": RNG_SCHEMA, "seed_schema": SEED_SCHEMA, "design_hash": design.design_hash,
                "code_hash": code_hash(), "environment": environment(),
                "planned_pairs": len(registry)//2, "planned_branch_trajectories": len(registry),
                "completed_pairs": 0, "status": "prepared" if prepare_only else "running"}
    _write_json(path/"manifest.json", manifest)
    if prepare_only:
        manifest["files_sha256"] = _hash_files(path)
        _write_json(path/"manifest.json", manifest)
        return manifest
    start = perf_counter()
    effects, summaries = [], []
    try:
        for index in range(0, len(registry), 2):
            records = registry[index:index+2]
            control = records[0]
            pair = run_pair(ModelConfig.from_dict(control["config"]), control["seed"], design.shock_multiplier)
            current, run_summaries = export_pair(pair, design, records, path/"pairs"/control["pair_id"])
            effects.extend(current)
            summaries.extend(run_summaries)
            for record in records:
                record["status"] = "completed"
            manifest["completed_pairs"] += 1
            _write_json(path/"run_registry.json", registry)
            _write_json(path/"manifest.json", manifest)
        _csv(path/"paired_effects.csv", effects)
        _write_json(path/"paired_effects.json", effects)
        _csv(path/"run_summary.csv", summaries)
        _csv(path/"replicate_summary.csv", summarize_pairs(effects))
        _csv(path/"seed_registry.csv", [{**_identity(r), "status": r["status"]} for r in registry])
        manifest["status"] = "completed"
    except Exception as exc:
        manifest.update(status="failed", error_type=type(exc).__name__, error=str(exc))
        raise
    finally:
        manifest["runtime_seconds"] = perf_counter()-start
        manifest["files_sha256"] = _hash_files(path)
        _write_json(path/"manifest.json", manifest)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--prepare-only", action="store_true", help="Register seeds and parameters without simulation")
    args = parser.parse_args(argv)
    try:
        design = ExperimentDesign.from_dict(read_json(args.config))
        result = execute_design(design, args.output, args.prepare_only)
    except (ValueError, OSError, TypeError) as exc:
        parser.exit(2, f"Experiment failed: {exc}\n")
    print(json.dumps({key: result[key] for key in (
        "experiment_id", "status", "planned_pairs", "planned_branch_trajectories", "completed_pairs")}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
