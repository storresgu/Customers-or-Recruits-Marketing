"""Command-line initial-state export. This command does not simulate months."""
import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from . import MODEL_VERSION, SPEC_VERSION
from .config import ModelConfig
from .model import Population, initialize_population
from .randomness import Process, RNG_SCHEMA


def code_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(path.name.encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _write_json(path: Path, data):
    path.write_text(json.dumps(data, indent=2, sort_keys=True, allow_nan=False) + "\n",
                    encoding="utf-8")


def _write_csv(path: Path, fieldnames, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def export_initial_state(population: Population, output: str | Path) -> dict:
    population.validate()
    if population.month != 0:
        raise ValueError("M1 export requires initialization at month 0")
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    population.save_json(output / "initial_state.json")
    rows = [a.to_dict() for a in population.agents]
    for row in rows:
        row["recent_net_income"] = json.dumps(row["recent_net_income"])
    _write_csv(output / "agents.csv", list(rows[0]), rows)
    _write_csv(output / "social_edges.csv", ["source", "target"],
               ({"source": min(u, v), "target": max(u, v)}
                for u, v in sorted((min(u, v), max(u, v))
                                   for u, v in population.social_graph.edges)))
    _write_csv(output / "sponsor_edges.csv", ["sponsor", "recruit"],
               ({"sponsor": u, "recruit": v}
                for u, v in sorted(population.sponsor_graph.edges)))
    _write_json(output / "summary.json", population.summary())
    _write_json(output / "config.json", population.config.to_dict())
    manifest = {
        "stage": "M3_initialization_only", "model_version": MODEL_VERSION,
        "spec_version": SPEC_VERSION, "rng_schema": RNG_SCHEMA,
        "seed": population.seed,
        "network_seed_hex": hex(population.random.seed_for(Process.NETWORK)),
        "process_registry": {p.name: p.value for p in Process},
        "python_version": platform.python_version(),
        "dependencies": {name: importlib.metadata.version(name)
                         for name in ("numpy", "networkx")},
        "config_hash": population.config.config_hash, "code_hash": code_hash(),
        "state_hash": population.state_hash,
        "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                         for p in sorted(output.iterdir()) if p.is_file()},
    }
    _write_json(output / "manifest.json", manifest)
    restored = Population.load_json(output / "initial_state.json")
    if restored.state_hash != population.state_hash:
        raise ValueError("Snapshot readback did not reproduce the original state")
    return manifest


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        population = initialize_population(ModelConfig.from_json(args.config), args.seed)
        export_initial_state(population, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"Initialization failed: {exc}\n")
    print(json.dumps(population.summary(), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
