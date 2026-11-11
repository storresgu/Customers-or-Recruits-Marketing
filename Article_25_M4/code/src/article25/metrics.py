"""Monthly stock-flow, volume and cash summaries with explicit denominators."""
from collections import Counter
from math import fsum
from statistics import median
from .ledger import Category, EXTERNAL


def ratio(numerator, denominator):
    return numerator / denominator if denominator else None


def summarize_month(ctx) -> dict:
    ctx.verify_flows()
    units = Counter()
    for tx in ctx.transactions:
        units[tx.category] += tx.units
    external = sum(units[c] for c in EXTERNAL)
    total = sum(units.values())
    repeats = units[Category.EXTERNAL_REPEAT]
    served = len(ctx.repeat_eligible) - len(ctx.unserved)
    counts = ctx.population.counts()
    gross = [r["gross_earnings"] for r in ctx.earnings]
    net = [r["net_cash"] for r in ctx.earnings]
    recruit_slots = int(ctx.config.contact_budget * ctx.config.recruitment_share)
    retail_slots = ctx.config.contact_budget - recruit_slots
    retail_attempts = sum(ctx.contact_counts[(p, "retail")] for p in ctx.operating)
    recruit_attempts = sum(ctx.contact_counts[(p, "recruitment")] for p in ctx.operating)
    for p in ctx.operating:
        if (ctx.contact_counts[(p, "retail")] > retail_slots
                or ctx.contact_counts[(p, "recruitment")] > recruit_slots
                or len(ctx.contacted.get(p, set())) != sum(
                    ctx.contact_counts[(p, c)] for c in ("retail", "recruitment"))):
            raise ValueError("Contact budget or no-repeat constraint violated")
    return {
        "month": ctx.month, **{"n_" + s: counts[s] for s in ("U", "C", "D", "I")},
        "operating_distributors": len(ctx.operating),
        "new_customers": units[Category.EXTERNAL_FIRST],
        "reacquired_customers": units[Category.EXTERNAL_REACQUISITION],
        "repeat_purchases": repeats,
        "new_recruits": len(ctx.entrants), "customer_to_distributor": ctx.flows["CD"],
        "customer_exits": ctx.flows["CU"], "distributor_exits": ctx.flows["DI"],
        "external_units": external, "total_units": total,
        "external_retail_share": ratio(external, total),
        **{c.value + "_units": units[c] for c in Category},
        "new_entrant_tagged_units": sum(tx.units for tx in ctx.transactions if tx.new_entrant_purchase),
        "repurchase_eligible": len(ctx.repeat_eligible), "served_customers": served,
        "unserved_customers": len(ctx.unserved), "observed_repurchase_rate": ratio(repeats, len(ctx.repeat_eligible)),
        "served_repurchase_rate": ratio(repeats, served),
        "customer_churn_rate": ratio(ctx.flows["CU"], len(ctx.repeat_eligible)),
        "distributor_churn_rate": ratio(ctx.flows["DI"], len(ctx.operating)),
        "retail_contacts": retail_attempts, "recruitment_contacts": recruit_attempts,
        "unused_retail_slots": len(ctx.operating)*retail_slots-retail_attempts,
        "unused_recruitment_slots": len(ctx.operating)*recruit_slots-recruit_attempts,
        "distinct_people_contacted": len(set().union(*ctx.contacted.values())) if ctx.contacted else 0,
        "earnings_cohort_size": len(ctx.earnings),
        "median_gross_earnings": median(gross) if gross else None,
        "median_net_cash": median(net) if net else None,
        "mean_net_cash": fsum(net)/len(net) if net else None,
        "positive_monthly_net_share": ratio(sum(x>0 for x in net), len(net)),
        "gross_earnings_total": fsum(gross), "net_cash_total": fsum(net),
        "commissions_total": fsum(r["commission"] for r in ctx.earnings),
        "expenses_total": fsum(r["expenses"] for r in ctx.earnings),
        "recruitment_multiplier": ctx.multiplier,
        "sponsor_edges": ctx.population.sponsor_graph.number_of_edges(),
    }
