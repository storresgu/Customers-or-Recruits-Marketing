import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import pytest
from article25 import Population
from article25.config import canonical_json
from article25.initialize import export_initial_state
from article25.randomness import Process


def test_snapshot_roundtrip_and_overwrite_protection(population, tmp_path):
    path = tmp_path / "state.json"
    population.save_json(path)
    restored = Population.load_json(path)
    assert restored.to_dict() == population.to_dict()
    assert restored.random.uniform(Process.REPURCHASE, 61, 3) == population.random.uniform(
        Process.REPURCHASE, 61, 3)
    with pytest.raises(FileExistsError):
        population.save_json(path)


def test_modified_snapshot_fails_checksum(population):
    data = population.to_dict()
    data["payload"]["agents"][0]["product_fit"] = 0.111
    with pytest.raises(ValueError, match="checksum"):
        Population.from_dict(data)


@pytest.mark.parametrize("damage", ["duplicate_edge", "missing_config", "unknown_agent_field",
                                  "unsupported_version"])
def test_structural_snapshot_rejection_even_with_recomputed_checksum(population, damage):
    data = population.to_dict()
    if damage == "duplicate_edge":
        data["payload"]["social_edges"].append(data["payload"]["social_edges"][0])
        data["payload"]["social_edges"].sort()
    elif damage == "missing_config":
        del data["payload"]["config"]["p_retail"]
    elif damage == "unknown_agent_field":
        data["payload"]["agents"][0]["extra"] = 1
    else:
        data["model_version"] = "unknown"
    data["sha256"] = hashlib.sha256(canonical_json(data["payload"]).encode()).hexdigest()
    with pytest.raises(ValueError):
        Population.from_dict(data)


def test_exports_include_valid_hashes_and_readable_edge_lists(population, tmp_path):
    output = tmp_path / "export"
    manifest = export_initial_state(population, output)
    for name, digest in manifest["files_sha256"].items():
        assert hashlib.sha256((output / name).read_bytes()).hexdigest() == digest
    assert manifest["state_hash"] == Population.load_json(output / "initial_state.json").state_hash
    assert (output / "sponsor_edges.csv").read_text().strip() == "sponsor,recruit"
    assert len((output / "agents.csv").read_text().splitlines()) == 61
    with pytest.raises(FileExistsError):
        export_initial_state(population, output)


def test_installed_cli_reproduces_identical_exports_across_processes(config, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps(config.to_dict()))
    destinations = [tmp_path / "first", tmp_path / "second"]
    for hash_seed, destination in zip(("4", "98"), destinations):
        result = subprocess.run(
            [sys.executable, "-m", "article25.initialize", "--config", str(config_path),
             "--seed", "53", "--output", str(destination)], check=True,
            capture_output=True, text=True,
            env=dict(os.environ, PYTHONHASHSEED=hash_seed))
        assert json.loads(result.stdout)["monthly_simulation_implemented"] is True
    assert {p.name: p.read_bytes() for p in destinations[0].iterdir()} == {
        p.name: p.read_bytes() for p in destinations[1].iterdir()}


def test_cli_rejects_unknown_parameter_without_partial_output(tmp_path):
    config = tmp_path / "bad.json"
    config.write_text('{"unknown": 1}')
    output = tmp_path / "should_not_exist"
    result = subprocess.run([sys.executable, "-m", "article25.initialize",
                             "--config", str(config), "--seed", "1",
                             "--output", str(output)], capture_output=True, text=True)
    assert result.returncode == 2
    assert "Unknown" in result.stderr
    assert not output.exists()
