"""Run one documented trajectory; matched designs use article25.experiments."""
import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import platform
from . import MODEL_VERSION, SPEC_VERSION
from .config import ModelConfig
from .initialize import code_hash, _write_json, _write_csv
from .simulation import Simulation
from .randomness import RNG_SCHEMA


def export_simulation(simulation, output):
    simulation.validate()
    path = Path(output)
    path.mkdir(parents=True, exist_ok=False)
    simulation.save_json(path/"checkpoint.json")
    simulation.population.save_json(path/"final_population.json")
    columns = list(simulation.monthly[0]) if simulation.monthly else ["month"]
    _write_csv(path/"monthly_metrics.csv", columns, simulation.monthly)
    for name, rows in (("events", simulation.events), ("transactions", simulation.transactions),
                       ("participant_earnings", simulation.earnings)):
        with (path/(name+".jsonl")).open("w",encoding="utf-8") as stream:
            for row in rows:
                stream.write(json.dumps(row,sort_keys=True,allow_nan=False)+"\n")
    _write_json(path/"config.json", simulation.population.config.to_dict())
    summary = {
        "model_version": MODEL_VERSION, "start_month": simulation.start_month,
        "end_month": simulation.population.month, "seed": simulation.population.seed,
        "last_month": simulation.monthly[-1] if simulation.monthly else None,
        "external_units_all_months": sum(r["external_units"] for r in simulation.monthly),
        "recruits_all_months": sum(r["new_recruits"] for r in simulation.monthly),
        "transactions": len(simulation.transactions), "events": len(simulation.events),
        "final_state_hash": simulation.population.state_hash,
    }
    _write_json(path/"summary.json",summary)
    manifest = {
        "model_version":MODEL_VERSION,"spec_version":SPEC_VERSION,"rng_schema":RNG_SCHEMA,
        "seed":simulation.population.seed,"code_hash":code_hash(),
        "config_hash":simulation.population.config.config_hash,
        "python":platform.python_version(),
        "dependencies":{p:importlib.metadata.version(p) for p in ("numpy","networkx")},
        "files_sha256":{p.name:hashlib.sha256(p.read_bytes()).hexdigest()
                        for p in sorted(path.iterdir()) if p.is_file()},
    }
    _write_json(path/"manifest.json",manifest)
    restored = Simulation.load_json(path/"checkpoint.json")
    if restored.to_dict() != simulation.to_dict():
        raise ValueError("Simulation export readback differs from source")
    return summary


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config",type=Path,required=True)
    parser.add_argument("--seed",type=int,required=True)
    parser.add_argument("--months",type=int)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args(argv)
    try:
        if args.output.exists():
            raise FileExistsError(f"Output already exists: {args.output}")
        simulation=Simulation.initialize(ModelConfig.from_json(args.config),args.seed)
        simulation.run(args.months)
        summary=export_simulation(simulation,args.output)
    except (ValueError,OSError) as exc:
        parser.exit(2,f"Trajectory failed: {exc}\n")
    print(json.dumps(summary,sort_keys=True))
    return 0


if __name__=="__main__":
    raise SystemExit(main())
