from dataclasses import replace
import pytest
from article25 import initialize_population
from article25.agents import State
from article25.ledger import MonthContext, Category
from article25.accounting import settle_month
from article25.simulation import Simulation
from test_m2_dynamics import simple_config


def chain_fixture(root_inactive=False):
    cfg=simple_config(fixed_operating_cost=0.05,cost_per_contact=0.005,entry_fee=0.2)
    pop=initialize_population(cfg,2)
    root=pop.root_ids[0]
    child,grandchild,buyer=[a.person_id for a in pop.agents if a.state is State.PROSPECT][:3]
    pop.month=3
    for person_id,parent,month in [(child,root,1),(grandchild,child,2)]:
        person=pop.agents[person_id]
        person.state=State.DISTRIBUTOR
        person.state_since_month=month
        person.sponsor_id=parent
        person.enrollment_month=month
        person.first_operating_month=month+1
        pop.sponsor_graph.add_edge(parent,person_id)
    if root_inactive:
        pop.agents[root].state=State.INACTIVE
        pop.agents[root].exit_month=2
        pop.agents[root].state_since_month=2
    pop.validate()
    ctx=MonthContext(pop,3,pop.operating_ids(3),(),pop.counts(),1.0)
    ctx.contact_counts[(child,"retail")]=2
    ctx.purchase(buyer,grandchild,Category.EXTERNAL_FIRST)
    ctx.purchase(grandchild,grandchild,Category.PARTICIPANT_PERSONAL)
    ctx.purchase(child,child,Category.PARTICIPANT_PERSONAL)
    return ctx,root,child,grandchild


def test_hand_calculated_margins_commissions_and_net_cash():
    ctx,root,child,grandchild=chain_fixture()
    rows={r["person_id"]:r for r in settle_month(ctx)}
    assert rows[root]["commission"]==pytest.approx(0.07)
    assert rows[child]["commission"]==pytest.approx(0.14)
    assert rows[grandchild]["commission"]==0
    assert rows[grandchild]["retail_margin"]==pytest.approx(0.3)
    assert rows[child]["contact_cost"]==pytest.approx(0.01)
    assert rows[grandchild]["own_purchase_cost"]==pytest.approx(0.7)
    assert rows[root]["net_cash"]==pytest.approx(0.02)
    assert rows[child]["net_cash"]==pytest.approx(-0.62)
    assert rows[grandchild]["net_cash"]==pytest.approx(-0.45)
    assert sum(r["commission"] for r in rows.values())==pytest.approx(0.21)


def test_inactive_sponsor_is_unpaid_without_compression():
    ctx,root,child,grandchild=chain_fixture(root_inactive=True)
    rows={r["person_id"]:r for r in settle_month(ctx)}
    assert root not in rows
    assert rows[child]["commission"]==pytest.approx(0.14)
    assert sum(r["commission"] for r in rows.values())==pytest.approx(0.14)
    assert ctx.population.sponsor_graph.has_edge(root,child)


def test_enrollment_has_no_reward_without_product_volume_and_fee_is_charged_once():
    cfg=simple_config(p_recruit=1,recruitment_share=1,entry_units=0,entry_fee=0.2)
    sim=Simulation.initialize(cfg,2).run(2)
    assert sim.monthly[0]["total_units"]==0
    assert sim.monthly[0]["commissions_total"]==0
    assert sum(r["entry_fee"] for r in sim.earnings if r["month"]==1)==pytest.approx(1.4)
    assert sum(r["entry_fee"] for r in sim.earnings if r["month"]==2)==0
    assert all(r["operating_cost"]==r["contact_cost"]==0 for r in sim.earnings
               if r["month"]==1 and r["enrolled_this_month"])


def test_sponsor_exiting_at_month_end_still_receives_current_commissions():
    cfg=simple_config(p_recruit=1,recruitment_share=1,entry_units=1,distributor_churn=1)
    sim=Simulation.initialize(cfg,2)
    root=sim.population.root_ids[0]
    sim.step()
    row=next(r for r in sim.earnings if r["person_id"]==root)
    assert row["commission"]==pytest.approx(6*0.7*0.1)
    assert sim.population.agents[root].state is State.INACTIVE


def test_income_histories_are_bounded_and_cumulative_cash_reconciles():
    sim=Simulation.initialize(simple_config(fixed_operating_cost=0.05),3).run(7)
    person=sim.population.agents[sim.population.root_ids[0]]
    assert len(person.recent_net_income)==3
    assert person.recent_net_income==[-0.05]*3
    assert person.cumulative_net_cash==pytest.approx(-0.35)
    assert person.cumulative_net_cash==pytest.approx(sum(r["net_cash"] for r in sim.earnings))


def test_purchase_guard_rejects_duplicate_person_and_participant_external_purchase():
    ctx,root,child,grandchild=chain_fixture()
    with pytest.raises(ValueError,match="twice"):
        ctx.purchase(child,child,Category.PARTICIPANT_PERSONAL)
    with pytest.raises(ValueError,match="nonparticipants"):
        ctx.purchase(root,root,Category.EXTERNAL_FIRST)
