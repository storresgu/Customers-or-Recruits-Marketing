from dataclasses import replace
from collections import Counter
import math
import pytest
from article25 import ModelConfig, initialize_population
from article25.agents import State
from article25.ledger import Category
from article25.simulation import Simulation
from article25.probabilities import (
    adjusted_probability, retail_probability, distributor_exit_probability,
    customer_exit_probability)


def simple_config(**overrides):
    values = dict(population_size=7, social_degree=6, initial_distributors=1,
                  homogeneous_agents=True, p_retail=0, p_recruit=0, p_repurchase=0,
                  p_personal=0, customer_churn=0, unserved_churn_increment=0,
                  distributor_churn=0, loss_exit_weight=0, contact_budget=6,
                  recruitment_share=0, fatigue=0, entry_units=0, entry_fee=0,
                  fixed_operating_cost=0, cost_per_contact=0)
    values.update(overrides)
    return ModelConfig(**values)


def customer_fixture(pop, customer_id, seller_id, month=1):
    pop.month=month
    person=pop.agents[customer_id]
    person.state=State.CUSTOMER
    person.ever_customer=True
    person.customer_since_month=month
    person.state_since_month=month
    person.last_purchase_month=month
    person.seller_id=seller_id


@pytest.mark.parametrize("p,z,expected", [
    (0,-1000,0), (0,1000,0), (1,-1000,1), (1,1000,1),
    (0.5,0,0.5), (0.5,1000,1), (0.5,-1000,0),
])
def test_stable_probability_endpoints(p,z,expected):
    assert adjusted_probability(p,z)==expected


def test_invalid_probability_and_adjustment_rejected():
    for p,z in [(-1,0),(2,0),(True,0),(0.5,float("nan")),(0.5,float("inf"))]:
        with pytest.raises(ValueError):
            adjusted_probability(p,z)


def test_fatigue_uses_prior_exposure_and_reduces_success_probability():
    c=simple_config(p_retail=0.5,fatigue=0.3)
    pop=initialize_population(c,1)
    seller=pop.agents[pop.root_ids[0]]
    buyer=next(a for a in pop.agents if a.state is State.PROSPECT)
    initial=retail_probability(c,seller,buyer)
    buyer.retail_exposures=4
    assert retail_probability(c,seller,buyer) < initial == 0.5
    sim=Simulation.initialize(replace(c,p_retail=0),1).run(2)
    contacts=[e for e in sim.events if e["event"]=="retail_contact" and e["target"]==buyer.person_id]
    assert [e["exposure_before"] for e in contacts]==[0,1]
    assert sim.population.agents[buyer.person_id].retail_exposures==2


def test_contact_budget_floor_and_no_same_month_cross_channel_repeats():
    sim=Simulation.initialize(simple_config(contact_budget=5,recruitment_share=0.5),2).run(2)
    for month in (1,2):
        rows=[e for e in sim.events if e["month"]==month and e["event"].endswith("_contact")]
        assert len(rows)==5
        assert len({(e["actor"],e["target"]) for e in rows})==5
        assert sum(e["event"]=="retail_contact" for e in rows)==3
        assert sum(e["event"]=="recruitment_contact" for e in rows)==2
    assert len(sim.events)>0


def test_different_distributors_can_contact_same_person_and_exposures_accumulate():
    sim=Simulation.initialize(simple_config(initial_distributors=2,contact_budget=20),3)
    row=sim.step()
    contacts=[e for e in sim.events if e["event"]=="retail_contact"]
    assert len(contacts)==10
    assert row["unused_retail_slots"]==30
    assert row["distinct_people_contacted"]==5
    assert all(a.retail_exposures==2 for a in sim.population.agents if a.state is State.PROSPECT)


def test_new_customers_cannot_repeat_enroll_or_exit_in_acquisition_month():
    cfg=simple_config(p_retail=1,p_repurchase=1,p_recruit=1,
                      customer_churn=1,recruitment_share=0.5)
    sim=Simulation.initialize(cfg,3)
    row=sim.step()
    assert row["new_customers"]==3
    assert row["repeat_purchases"]==row["customer_exits"]==row["customer_to_distributor"]==0
    assert row["new_recruits"]==3
    assert row["operating_distributors"]==1
    acquired={t["buyer_id"] for t in sim.transactions if t["category"]=="external_first"}
    assert all(sim.population.agents[i].state is State.CUSTOMER for i in acquired)
    actors={e["actor"] for e in sim.events if e["event"].endswith("_contact")}
    assert actors==set(sim.population.root_ids)


def test_perfect_repurchase_is_one_purchase_per_existing_customer():
    sim=Simulation.initialize(simple_config(p_retail=1,p_repurchase=1),5).run(2)
    assert sim.monthly[0]["external_units"]==6
    assert sim.monthly[0]["repeat_purchases"]==0
    assert sim.monthly[1]["repeat_purchases"]==6
    assert sim.monthly[1]["observed_repurchase_rate"]==1
    assert all(v==1 for v in Counter((t["month"],t["buyer_id"]) for t in sim.transactions).values())


def test_zero_repurchase_does_not_force_customer_exit():
    sim=Simulation.initialize(simple_config(p_retail=1,p_repurchase=0),5).run(3)
    assert sim.monthly[-1]["n_C"]==6
    assert sim.monthly[-1]["external_units"]==0
    assert sim.monthly[-1]["observed_repurchase_rate"]==0


def test_reacquisition_preserves_customer_history_and_is_not_a_new_unique_customer():
    sim=Simulation.initialize(simple_config(p_retail=1,customer_churn=1),5).run(3)
    assert [r["n_C"] for r in sim.monthly]==[6,0,6]
    assert sim.monthly[2]["new_customers"]==0
    assert sim.monthly[2]["reacquired_customers"]==6
    assert all(a.ever_customer for a in sim.population.agents if a.state is State.CUSTOMER)


def test_existing_customer_enrollment_precedes_and_prevents_external_repurchase():
    cfg=simple_config(p_recruit=1,p_repurchase=1,recruitment_share=1,entry_units=1)
    pop=initialize_population(cfg,9)
    root=pop.root_ids[0]
    for person in pop.agents:
        if person.person_id!=root:
            customer_fixture(pop,person.person_id,root)
    sim=Simulation(pop)
    row=sim.step()
    assert row["customer_to_distributor"]==6
    assert row["external_units"]==row["customer_exits"]==0
    assert row["participant_entry_units"]==6
    assert row["n_C"]==0 and row["n_D"]==7
    assert all(t["buyer_state"]=="D" for t in sim.transactions)


def test_unserved_customer_cannot_purchase_even_with_probability_one():
    cfg=simple_config(p_retail=1,p_repurchase=1,distributor_churn=1,unserved_churn_increment=1)
    sim=Simulation.initialize(cfg,5).run(2)
    assert sim.monthly[0]["distributor_exits"]==1
    row=sim.monthly[1]
    assert row["operating_distributors"]==0
    assert row["external_units"]==0
    assert row["unserved_customers"]==6
    assert row["customer_exits"]==6
    assert row["served_repurchase_rate"] is None
    assert row["observed_repurchase_rate"]==0


def test_seller_reassigned_to_active_neighbor_preserving_customer_status():
    pop=initialize_population(simple_config(initial_distributors=2,p_repurchase=1),8)
    old,new=pop.root_ids
    customer=next(a.person_id for a in pop.agents if a.state is State.PROSPECT)
    customer_fixture(pop,customer,old)
    pop.agents[old].state=State.INACTIVE
    pop.agents[old].state_since_month=1
    pop.agents[old].exit_month=1
    sim=Simulation(pop)
    row=sim.step()
    assert row["repeat_purchases"]==1
    assert sim.population.agents[customer].seller_id==new
    assert sim.transactions[0]["distributor_id"]==new
    assert old in sim.population.sponsor_graph


def test_entry_purchase_replaces_personal_even_if_entry_quantity_is_zero():
    sim=Simulation.initialize(simple_config(p_personal=1,entry_units=0),4).run(2)
    assert sim.monthly[0]["total_units"]==0
    assert sim.monthly[1]["participant_personal_units"]==1


def test_entry_tags_do_not_inflate_total_volume_and_expire_after_three_commercial_months():
    sim=Simulation.initialize(simple_config(p_personal=1,entry_units=2),4).run(4)
    assert [r["total_units"] for r in sim.monthly]==[2,1,1,1]
    assert [r["new_entrant_tagged_units"] for r in sim.monthly]==[2,1,1,0]
    assert all(r["external_units"]==0 for r in sim.monthly)


def test_zero_recruitment_and_zero_retail_conversions_produce_no_growth():
    sim=Simulation.initialize(simple_config(recruitment_share=0.5),2).run(5)
    assert all(r["new_customers"]==r["new_recruits"]==0 for r in sim.monthly)


def test_high_exit_removes_only_start_of_month_distributors_and_keeps_sponsor_links():
    sim=Simulation.initialize(simple_config(p_recruit=1,recruitment_share=1,
                                           distributor_churn=1),7)
    root=sim.population.root_ids[0]
    row=sim.step()
    assert row["new_recruits"]==6 and row["distributor_exits"]==1
    assert row["n_D"]==6
    assert sim.population.agents[root].state is State.INACTIVE
    assert sim.population.sponsor_graph.number_of_edges()==6
    sim.step()
    assert sim.monthly[-1]["n_I"]==7
    assert sim.population.sponsor_graph.number_of_edges()==6


def test_loss_rule_uses_rolling_net_cash_and_caps_probabilities():
    cfg=simple_config(distributor_churn=0.01,loss_exit_weight=0.04)
    assert distributor_exit_probability(cfg,[-0.3,-0.3,-0.3])==pytest.approx(0.05)
    assert distributor_exit_probability(cfg,[-0.3,0.6,-0.3])==pytest.approx(0.01)
    assert distributor_exit_probability(cfg,[-100,0.3,0.3,0.3])==pytest.approx(0.01)
    assert distributor_exit_probability(replace(cfg,distributor_churn=1,loss_exit_weight=1),[-1])==1
    with pytest.raises(ValueError):
        distributor_exit_probability(cfg,[])
    assert customer_exit_probability(replace(cfg,customer_churn=0.9,unserved_churn_increment=0.9),True)==1


def test_cash_loss_can_trigger_exit_with_zero_base_churn():
    cfg=simple_config(loss_exit_weight=1,loss_scale=0.1,fixed_operating_cost=0.2)
    sim=Simulation.initialize(cfg,4)
    row=sim.step()
    assert row["net_cash_total"]==pytest.approx(-0.2)
    assert row["distributor_exits"]==1


def test_income_cohort_includes_people_exiting_in_the_month():
    sim=Simulation.initialize(simple_config(distributor_churn=1,fixed_operating_cost=0.2),4)
    row=sim.step()
    assert row["n_D"]==0
    assert row["earnings_cohort_size"]==1
    assert row["median_net_cash"]==pytest.approx(-0.2)
    next_row=sim.step()
    assert next_row["earnings_cohort_size"]==0
    assert next_row["median_net_cash"] is None


def test_population_with_no_distributors_has_no_fictitious_activity():
    sim=Simulation.initialize(simple_config(initial_distributors=0,p_retail=1,p_recruit=1),3).run(3)
    assert all(r["total_units"]==r["new_recruits"]==0 for r in sim.monthly)
    assert all(r["external_retail_share"] is None for r in sim.monthly)
