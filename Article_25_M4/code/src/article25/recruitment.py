"""Finite-neighborhood enrollment, personal purchases, and distributor exit."""
from .agents import State
from .ledger import Category
from .probabilities import recruitment_probability, personal_probability, distributor_exit_probability
from .randomness import Process


def recruitment_contacts(ctx):
    slots = int(ctx.config.contact_budget * ctx.config.recruitment_share)
    for actor in ctx.rng.rank(ctx.operating, Process.RECRUITMENT_ORDER, ctx.month):
        recruiter = ctx.population.agents[actor]
        used = ctx.contacted.setdefault(actor, set())
        candidates = [p for p in ctx.population.social_graph.neighbors(actor)
                      if ctx.population.agents[p].state in (State.PROSPECT, State.CUSTOMER)
                      and p not in used and p not in ctx.new_customers]
        for target in ctx.rng.rank(candidates, Process.RECRUITMENT_TARGET, ctx.month, actor)[:slots]:
            prospect = ctx.population.agents[target]
            if prospect.state not in (State.PROSPECT, State.CUSTOMER) or target in used:
                continue
            probability = recruitment_probability(ctx.config, recruiter, prospect, ctx.multiplier)
            draw = ctx.rng.uniform(Process.RECRUITMENT_CONVERSION, ctx.month, actor, target)
            exposure = prospect.recruitment_exposures
            prospect.recruitment_exposures += 1
            used.add(target)
            ctx.contact_counts[(actor, "recruitment")] += 1
            success = draw < probability
            ctx.event("recruitment_contact", actor, target, probability=probability, draw=draw,
                      exposure_before=exposure, success=success)
            if success:
                previous = prospect.state.value
                ctx.transition(prospect, State.DISTRIBUTOR)
                prospect.seller_id = None
                prospect.customer_since_month = None
                prospect.sponsor_id = actor
                prospect.enrollment_month = ctx.month
                prospect.first_operating_month = ctx.month + 1
                ctx.population.sponsor_graph.add_edge(actor, target)
                ctx.entrants.add(target)
                ctx.event("enrollment", actor, target, previous_state=previous,
                          first_operating_month=ctx.month + 1)
                if ctx.config.entry_units:
                    ctx.purchase(target, target, Category.PARTICIPANT_ENTRY, ctx.config.entry_units)


def participant_purchases(ctx):
    for person_id in ctx.operating:
        person = ctx.population.agents[person_id]
        if ctx.month == 1 and person_id in ctx.population.root_ids:
            if ctx.config.entry_units:
                ctx.purchase(person_id, person_id, Category.PARTICIPANT_ENTRY, ctx.config.entry_units)
            continue  # No personal purchase even if entry_units is zero.
        probability = personal_probability(ctx.config, person)
        draw = ctx.rng.uniform(Process.PERSONAL_PURCHASE, ctx.month, person_id)
        success = draw < probability
        ctx.event("personal_purchase_decision", person_id, probability=probability,
                  draw=draw, success=success)
        if success:
            ctx.purchase(person_id, person_id, Category.PARTICIPANT_PERSONAL)


def distributor_exits(ctx):
    for person_id in ctx.operating:
        person = ctx.population.agents[person_id]
        probability = distributor_exit_probability(ctx.config, person.recent_net_income)
        draw = ctx.rng.uniform(Process.DISTRIBUTOR_EXIT, ctx.month, person_id)
        success = draw < probability
        ctx.event("distributor_exit_decision", person_id, probability=probability,
                  draw=draw, recent_net= sum(person.recent_net_income) / len(person.recent_net_income),
                  success=success)
        if success:
            ctx.transition(person, State.INACTIVE)
            person.exit_month = ctx.month
