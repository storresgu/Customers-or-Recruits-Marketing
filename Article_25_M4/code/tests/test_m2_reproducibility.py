from dataclasses import replace
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import networkx as nx
import pytest
from article25 import ModelConfig, Population, initialize_population
from article25.simulation import Simulation
from article25.run import export_simulation
import article25.simulation as simulation_module
from test_m2_dynamics import simple_config


def test_identical_seeds_produce_identical_complete_trajectories():
    cfg=ModelConfig(population_size=60,social_degree=6,initial_distributors=3)
    first=Simulation.initialize(cfg,51).run(12)
    second=Simulation.initialize(cfg,51).run(12)
    assert first.to_dict()==second.to_dict()


def test_clone_and_checkpoint_resume_match_uninterrupted_run(tmp_path):
    cfg=ModelConfig(population_size=60,social_degree=6,initial_distributors=3)
    full=Simulation.initialize(cfg,51).run(20)
    prefix=Simulation.initialize(cfg,51).run(7)
    path=tmp_path/"checkpoint.json"
    prefix.save_json(path)
    restored=Simulation.load_json(path)
    cloned=prefix.clone()
    restored.run(20)
    cloned.run(20)
    assert restored.to_dict()==cloned.to_dict()==full.to_dict()
    assert prefix.population.month==7 and len(prefix.monthly)==7
    with pytest.raises(FileExistsError):
        prefix.save_json(path)


def test_complete_shock_leaves_preshock_behavior_identical_and_stops_enrollment():
    cfg=simple_config(population_size=40,social_degree=6,initial_distributors=2,
                      contact_budget=3,recruitment_share=1,p_recruit=0.5,
                      horizon_months=12,shock_start_month=4,cost_per_contact=0.01,
                      entry_units=1)
    control=Simulation.initialize(cfg,4).run()
    shock=Simulation.initialize(replace(cfg,recruitment_multiplier=0),4).run()
    assert control.monthly[:3]==shock.monthly[:3]
    assert [e for e in control.events if e["month"]<4]==[e for e in shock.events if e["month"]<4]
    assert sum(r["new_recruits"] for r in control.monthly[3:])>0
    assert all(r["new_recruits"]==0 for r in shock.monthly[3:])
    attempts=sum(r["recruitment_contacts"] for r in shock.monthly[3:])
    assert attempts>0
    assert sum(r["contact_cost"] for r in shock.earnings if r["month"]>=4)==pytest.approx(attempts*0.01)
    assert all(e["probability"]==0 for e in shock.events
               if e["month"]>=4 and e["event"]=="recruitment_contact")


@pytest.mark.parametrize("seed",[0,17,20260925])
def test_120_month_multi_seed_stock_volume_and_income_reconciliation(seed):
    cfg=ModelConfig(population_size=50,social_degree=6,initial_distributors=3)
    sim=Simulation.initialize(cfg,seed).run()
    sim.validate()
    previous={"U":47,"C":0,"D":3,"I":0}
    for row in sim.monthly:
        assert sum(row["n_"+s] for s in "UCDI")==50
        assert row["n_C"]==previous["C"]+row["new_customers"]+row["reacquired_customers"]-row["customer_exits"]-row["customer_to_distributor"]
        assert row["n_D"]==previous["D"]+row["new_recruits"]-row["distributor_exits"]
        assert row["total_units"]==sum(row[k] for k in (
            "external_first_units","external_reacquisition_units","external_repeat_units",
            "participant_personal_units","participant_entry_units","participant_qualification_units"))
        assert row["gross_earnings_total"]-row["expenses_total"]==pytest.approx(row["net_cash_total"])
        previous={s:row["n_"+s] for s in "UCDI"}
    for person in sim.population.agents:
        assert person.cumulative_net_cash==pytest.approx(
            sum(r["net_cash"] for r in sim.earnings if r["person_id"]==person.person_id))


def test_month_is_atomic_if_accounting_fails(monkeypatch):
    sim=Simulation.initialize(simple_config(p_retail=1),2)
    before=sim.to_dict()
    def broken(ctx):
        raise ValueError("deliberate accounting failure")
    monkeypatch.setattr(simulation_module,"settle_month",broken)
    with pytest.raises(ValueError,match="deliberate"):
        sim.step()
    assert sim.to_dict()==before


def test_static_graph_mutation_is_rejected_even_when_edge_count_is_preserved():
    sim=Simulation.initialize(simple_config(social_degree=2),2)
    graph=sim.population.social_graph
    missing=next(nx.non_edges(graph))
    graph.remove_edge(*next(iter(graph.edges)))
    graph.add_edge(*missing)
    with pytest.raises(ValueError,match="static"):
        sim.step()


def test_checkpoint_corruption_rejected():
    sim=Simulation.initialize(simple_config(p_retail=1),2).run(2)
    data=sim.to_dict()
    data["payload"]["monthly"][0]["external_units"]+=1
    with pytest.raises(ValueError,match="checksum"):
        Simulation.from_dict(data)


def test_horizon_and_rewind_rejected_without_mutation():
    sim=Simulation.initialize(simple_config(horizon_months=2,shock_start_month=2),3).run()
    original=sim.to_dict()
    with pytest.raises(ValueError):
        sim.step()
    with pytest.raises(ValueError):
        sim.run(1)
    assert sim.to_dict()==original


def test_m1_initial_snapshot_import_is_explicit_and_lossless():
    pop=initialize_population(simple_config(),3)
    old=pop.to_dict()
    old["model_version"]="0.1.0-m1"
    restored=Population.from_dict(old)
    assert restored.state_hash==pop.state_hash


def test_cli_and_exports_reproduce_across_python_processes(tmp_path):
    cfg=simple_config(p_retail=0.5,p_repurchase=0.7,recruitment_share=0.5,p_recruit=0.2)
    path=tmp_path/"config.json"
    path.write_text(json.dumps(cfg.to_dict()))
    dirs=[tmp_path/"first",tmp_path/"second"]
    for destination,hashseed in zip(dirs,["3","99"]):
        result=subprocess.run([sys.executable,"-m","article25.run","--config",str(path),
            "--seed","42","--months","8","--output",str(destination)],
            env=dict(os.environ,PYTHONHASHSEED=hashseed),check=True,capture_output=True,text=True)
        assert json.loads(result.stdout)["end_month"]==8
    assert {p.name:p.read_bytes() for p in dirs[0].iterdir()}=={
        p.name:p.read_bytes() for p in dirs[1].iterdir()}
    sim=Simulation.load_json(dirs[0]/"checkpoint.json")
    with pytest.raises(FileExistsError):
        export_simulation(sim,dirs[0])
