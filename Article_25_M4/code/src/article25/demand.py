"""Retail acquisition, service continuity, repurchase, and customer exit."""
from .agents import State
from .ledger import Category
from .probabilities import retail_probability, repurchase_probability, customer_exit_probability
from .randomness import Process


def resolve_sellers(ctx):
    operating = set(ctx.operating)
    for person_id in ctx.customers_start:
        customer = ctx.population.agents[person_id]
        if customer.seller_id in operating:
            continue
        candidates = [p for p in ctx.population.social_graph.neighbors(person_id)
                      if p in operating]
        old = customer.seller_id
        customer.seller_id = (ctx.rng.rank(candidates, Process.SELLER_REASSIGNMENT,
                                         ctx.month, person_id)[0] if candidates else None)
        if old != customer.seller_id:
            ctx.event("seller_reassigned", person_id, customer.seller_id, previous_seller=old)


def retail_contacts(ctx):
    slots = ctx.config.contact_budget - int(ctx.config.contact_budget * ctx.config.recruitment_share)
    for actor in ctx.rng.rank(ctx.operating, Process.RETAIL_ORDER, ctx.month):
        seller = ctx.population.agents[actor]
        used = ctx.contacted.setdefault(actor, set())
        candidates = [p for p in ctx.population.social_graph.neighbors(actor)
                      if ctx.population.agents[p].state is State.PROSPECT and p not in used]
        for target in ctx.rng.rank(candidates, Process.RETAIL_TARGET, ctx.month, actor)[:slots]:
            prospect = ctx.population.agents[target]
            if prospect.state is not State.PROSPECT or target in used:
                continue
            probability = retail_probability(ctx.config, seller, prospect)
            draw = ctx.rng.uniform(Process.RETAIL_CONVERSION, ctx.month, actor, target)
            exposure = prospect.retail_exposures
            prospect.retail_exposures += 1
            used.add(target)
            ctx.contact_counts[(actor, "retail")] += 1
            success = draw < probability
            ctx.event("retail_contact", actor, target, probability=probability, draw=draw,
                      exposure_before=exposure, success=success)
            if success:
                category = (Category.EXTERNAL_REACQUISITION if prospect.ever_customer
                            else Category.EXTERNAL_FIRST)
                ctx.purchase(target, actor, category)
                ctx.transition(prospect, State.CUSTOMER)
                prospect.ever_customer = True
                prospect.seller_id = actor
                prospect.customer_since_month = ctx.month
                ctx.new_customers.add(target)
                ctx.event(category.value, actor, target)


def repurchases(ctx):
    operating = set(ctx.operating)
    for person_id in ctx.customers_start:
        person = ctx.population.agents[person_id]
        if person.state is not State.CUSTOMER:
            continue  # A customer enrolled during recruitment this month.
        ctx.repeat_eligible.append(person_id)
        served = person.seller_id in operating
        if not served:
            ctx.unserved.add(person_id)
        probability = repurchase_probability(ctx.config, person)
        draw = ctx.rng.uniform(Process.REPURCHASE, ctx.month, person_id)
        success = served and draw < probability
        ctx.event("repurchase_opportunity", person_id, person.seller_id, served=served,
                  probability=probability, draw=draw, success=success)
        if success:
            ctx.purchase(person_id, person.seller_id, Category.EXTERNAL_REPEAT)


def customer_exits(ctx):
    for person_id in ctx.repeat_eligible:
        person = ctx.population.agents[person_id]
        probability = customer_exit_probability(ctx.config, person_id in ctx.unserved)
        draw = ctx.rng.uniform(Process.CUSTOMER_EXIT, ctx.month, person_id)
        success = draw < probability
        ctx.event("customer_exit_decision", person_id, probability=probability,
                  draw=draw, success=success)
        if success:
            ctx.transition(person, State.PROSPECT)
            person.seller_id = None
            person.customer_since_month = None
