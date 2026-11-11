import copy
import csv
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from article25 import ModelConfig, Population
from article25.config import canonical_json
from article25.experiments import ExperimentDesign, run_pair, execute_design, export_pair
from article25.simulation import Simulation
from article25.outcomes import paired_effects
from test_m2_dynamics import simple_config


def small_design():
    return ExperimentDesign.from_dict({
        "schema": "article25-experiment-v1", "experiment_id": "fixture", "purpose": "verification",
        "master_seed": 20260926, "replicates": 1, "shock_multiplier": 0,
        "base_config": simple_config(population_size=40, social_degree=6, initial_distributors=2,
            horizon_months=10, shock_start_month=4, contact_budget=2, recruitment_share=.5,
            p_retail=.3, p_repurchase=.6, p_recruit=.3, entry_units=1, cost_per_contact=.01).to_dict(),
        "scenarios": [{"scenario_id": "a", "overrides": {}}],
        "windows": [{"name": "pre", "start": 2, "end": 3},
                    {"name": "immediate", "start": 4, "end": 5},
                    {"name": "late", "start": 9, "end": 10}]})


@pytest.mark.parametrize("seed", [0, 17, 20260925])
def test_primary_120_month_pair_has_identical_complete_prefix_and_no_late_enrollments(seed):
    config = ModelConfig(population_size=50, social_degree=6, initial_distributors=3)
    pair = run_pair(config, seed)
    assert pair.prefix.population.month == 60
    for trace in ("monthly", "events", "transactions", "earnings"):
        assert [r for r in getattr(pair.control, trace) if r["month"] <= 60] == getattr(pair.prefix, trace)
        assert [r for r in getattr(pair.shock, trace) if r["month"] <= 60] == getattr(pair.prefix, trace)
    assert all(r["new_recruits"] == 0 for r in pair.shock.monthly[60:])
    assert all(r["recruitment_multiplier"] == 0 for r in pair.shock.monthly[60:])
    assert pair.control.population.config == config
    assert replace(pair.shock.population.config, recruitment_multiplier=1.0) == config


def test_two_controls_have_identical_complete_histories():
    design = small_design()
    pair = run_pair(design.base_config, 19, 1)
    assert pair.control.to_dict() == pair.shock.to_dict()
    effects = paired_effects(pair.control.monthly, pair.shock.monthly, design.windows)
    assert all(r["difference"] == 0 for r in effects)


def test_real_shock_pair_branches_after_boundary_and_keeps_recruitment_contact_costs():
    cfg = small_design().base_config
    pair = run_pair(cfg, 19)
    assert sum(r["new_recruits"] for r in pair.control.monthly[3:]) > 0
    assert sum(r["new_recruits"] for r in pair.shock.monthly[3:]) == 0
    assert sum(r["recruitment_contacts"] for r in pair.shock.monthly[3:]) > 0
    assert pair.prefix.population.month == 3 and pair.initial.month == 0
    assert pair.control.population.agents is not pair.shock.population.agents
    assert pair.control.population.social_graph is not pair.shock.population.social_graph


def test_pair_matches_independently_initialized_branches_and_restart(tmp_path):
    cfg = small_design().base_config
    pair = run_pair(cfg, 19)
    independent = Simulation.initialize(cfg, 19).run()
    treated = Simulation.initialize(replace(cfg, recruitment_multiplier=0.0), 19).run()
    assert pair.control.to_dict() == independent.to_dict()
    assert pair.shock.to_dict() == treated.to_dict()
    checkpoint = tmp_path/"checkpoint.json"
    pair.prefix.save_json(checkpoint)
    for multiplier, expected in ((1, pair.control), (0, pair.shock)):
        resumed = Simulation.load_json(checkpoint)
        resumed.population.config = replace(cfg, recruitment_multiplier=float(multiplier))
        assert resumed.run().to_dict() == expected.to_dict()


def test_pair_validation_detects_changed_preshock_trace():
    pair = run_pair(small_design().base_config, 19)
    pair.shock.monthly[0]["external_units"] += 1
    with pytest.raises(ValueError, match="history"):
        pair.validate()


def test_pair_validation_rejects_unrelated_configuration_change():
    pair = run_pair(small_design().base_config, 19)
    pair.shock.population.config = replace(pair.shock.population.config, p_retail=.9)
    with pytest.raises(ValueError, match="outside"):
        pair.validate()


def test_registry_has_explicit_stable_unique_pair_seeds_and_run_ids():
    design = replace(small_design(), replicates=3, scenarios=(
        {"scenario_id": "a", "overrides": {}}, {"scenario_id": "b", "overrides": {"p_retail": .8}}))
    registry = design.registry()
    assert len(registry) == 12
    assert len({r["run_id"] for r in registry}) == 12
    assert len({r["seed"] for r in registry}) == 6
    for control, shock in zip(registry[::2], registry[1::2]):
        assert control["seed"] == shock["seed"] and control["pair_id"] == shock["pair_id"]
        assert control["config_hash"] != shock["config_hash"]
    reordered = replace(design, scenarios=tuple(reversed(design.scenarios))).registry()
    assert {r["run_id"]: r for r in registry} == {r["run_id"]: r for r in reordered}
    assert ExperimentDesign.from_dict(design.to_dict()).registry() == registry


@pytest.mark.parametrize("field,value", [
    ("master_seed", True), ("master_seed", -1), ("replicates", 0), ("replicates", 1.5),
    ("shock_multiplier", -1), ("shock_multiplier", float("nan")), ("shock_multiplier", 2),
    ("experiment_id", "../escape"), ("experiment_id", "a__b"), ("purpose", "unspecified"),
    ("scenarios", []), ("windows", []), ("schema", "future")])
def test_invalid_designs_are_rejected(field, value):
    data = small_design().to_dict()
    data[field] = value
    with pytest.raises(ValueError):
        ExperimentDesign.from_dict(data)


@pytest.mark.parametrize("mutation", ["unknown", "missing", "duplicate_scenario", "duplicate_window",
    "multiplier_override", "unknown_parameter", "cross_boundary", "beyond_horizon", "treated_base"])
def test_invalid_nested_designs_are_rejected(mutation):
    data = small_design().to_dict()
    if mutation == "unknown": data["typo"] = 1
    if mutation == "missing": del data["purpose"]
    if mutation == "duplicate_scenario": data["scenarios"] *= 2
    if mutation == "duplicate_window": data["windows"][1]["name"] = "pre"
    if mutation == "multiplier_override": data["scenarios"][0]["overrides"]["recruitment_multiplier"] = 0
    if mutation == "unknown_parameter": data["scenarios"][0]["overrides"]["typo"] = 0
    if mutation == "cross_boundary": data["windows"][0]["end"] = 4
    if mutation == "beyond_horizon": data["windows"][-1]["end"] = 11
    if mutation == "treated_base": data["base_config"]["recruitment_multiplier"] = 0
    with pytest.raises(ValueError):
        ExperimentDesign.from_dict(data)


def test_prepare_only_does_not_initialize_or_simulate(monkeypatch, tmp_path):
    def forbidden(*args, **kwargs):
        raise AssertionError("prepare-only tried to simulate")
    monkeypatch.setattr(Simulation, "initialize", forbidden)
    manifest = execute_design(small_design(), tmp_path/"plan", prepare_only=True)
    assert manifest["status"] == "prepared" and manifest["completed_pairs"] == 0
    assert not (tmp_path/"plan"/"pairs").exists()
    assert json.loads((tmp_path/"plan"/"run_registry.json").read_text())[0]["status"] == "planned"


def test_export_readback_ids_hashes_and_refusal_to_overwrite(tmp_path):
    design = small_design()
    out = tmp_path/"run"
    manifest = execute_design(design, out)
    assert manifest["status"] == "completed" and manifest["completed_pairs"] == 1
    for file, checksum in manifest["files_sha256"].items():
        assert hashlib.sha256((out/file).read_bytes()).hexdigest() == checksum
    pairs = list((out/"pairs").iterdir())
    monthly = list(csv.DictReader((pairs[0]/"monthly_metrics.csv").open()))
    assert len(monthly) == 20 and {r["condition"] for r in monthly} == {"control", "shock"}
    assert all(r["experiment_id"] == "fixture" and r["code_hash"] and r["config_hash"] for r in monthly)
    assert (pairs[0]/"initial_state.json").exists() and (pairs[0]/"checkpoint_003.json").exists()
    runs = json.loads((pairs[0]/"run_manifest.json").read_text())
    assert all(r["status"] == "completed" and "environment" in r for r in runs)
    with pytest.raises(FileExistsError):
        execute_design(design, out)


def test_export_checks_registry_matches_simulation_before_creating_files(tmp_path):
    design = small_design()
    records = design.registry()
    pair = run_pair(design.base_config, records[0]["seed"])
    records[1]["seed"] += 1
    with pytest.raises(ValueError, match="registry"):
        export_pair(pair, design, records, tmp_path/"invalid")
    assert not (tmp_path/"invalid").exists()


def test_failed_execution_records_failure_without_claiming_completion(monkeypatch, tmp_path):
    import article25.experiments as module
    def broken(*args, **kwargs):
        raise ValueError("deliberate verification failure")
    monkeypatch.setattr(module, "run_pair", broken)
    with pytest.raises(ValueError):
        execute_design(small_design(), tmp_path/"run")
    manifest = json.loads((tmp_path/"run"/"manifest.json").read_text())
    assert manifest["status"] == "failed" and manifest["completed_pairs"] == 0


def test_old_m2_population_and_checkpoint_can_be_imported_losslessly():
    simulation = Simulation.initialize(small_design().base_config, 2).run(3)
    data = simulation.to_dict()
    data["model_version"] = "0.2.0-m2"
    data["payload"]["population"]["model_version"] = "0.2.0-m2"
    data["sha256"] = hashlib.sha256(canonical_json(data["payload"]).encode()).hexdigest()
    restored = Simulation.from_dict(data)
    assert restored.to_dict() == simulation.to_dict()
    assert restored.run().to_dict() == simulation.run().to_dict()


def test_cli_repeats_scientific_outputs_across_python_hash_seeds(tmp_path):
    config = tmp_path/"design.json"
    config.write_text(json.dumps(small_design().to_dict()))
    paths = [tmp_path/"first", tmp_path/"second"]
    for path, seed in zip(paths, ("1", "99")):
        result = subprocess.run([sys.executable, "-m", "article25.experiments", "--config", str(config),
             "--output", str(path)], env=dict(os.environ, PYTHONHASHSEED=seed),
             check=True, capture_output=True, text=True)
        assert json.loads(result.stdout)["completed_pairs"] == 1
    for source in paths[0].rglob("*"):
        if source.is_file() and "manifest" not in source.name:
            assert source.read_bytes() == (paths[1]/source.relative_to(paths[0])).read_bytes()


def test_pilot_configuration_is_exactly_four_scenarios_and_40_pairs():
    path = Path(__file__).parents[1]/"configs"/"pilot_m3.json"
    design = ExperimentDesign.from_dict(json.loads(path.read_text()))
    assert design.purpose == "pilot" and design.replicates == 10
    assert design.base_config.population_size == 500 and design.base_config.initial_distributors == 10
    assert design.base_config.horizon_months == 120 and design.base_config.shock_start_month == 61
    assert {(s["overrides"]["p_retail"], s["overrides"]["p_repurchase"]) for s in design.scenarios} == {
        (.03, .30), (.03, .80), (.12, .30), (.12, .80)}
    assert len(design.registry()) == 80
