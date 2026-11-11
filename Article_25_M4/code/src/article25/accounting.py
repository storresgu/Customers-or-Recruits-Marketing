"""Minimum cash ledger required by M2's loss-responsive exit rule.

No firm profit, imputed personal-use value, or multi-level compression is assumed.
"""
from math import fsum, isclose, isfinite
from .ledger import EXTERNAL, Category


def settle_month(ctx) -> list[dict]:
    operating = set(ctx.operating)
    cohort = sorted(operating | ctx.entrants)
    rows = {p: {
        "month": ctx.month, "person_id": p, "retail_margin": 0.0,
        "commission": 0.0, "own_purchase_cost": 0.0,
        "operating_cost": ctx.config.fixed_operating_cost if p in operating else 0.0,
        "contact_cost": ctx.config.cost_per_contact * sum(
            ctx.contact_counts[(p, channel)] for channel in ("retail", "recruitment")),
        "entry_fee": ctx.config.entry_fee if (
            p in ctx.entrants or (ctx.month == 1 and p in ctx.population.root_ids)) else 0.0,
    } for p in cohort}
    for tx in ctx.transactions:
        if tx.distributor_id not in rows:
            raise ValueError("Transaction responsible distributor absent from monthly cohort")
        expected_price = ctx.config.retail_price if tx.category in EXTERNAL else ctx.config.wholesale_price
        if tx.unit_price != expected_price or tx.month != ctx.month or tx.units < 1:
            raise ValueError("Transaction price, month or units is inconsistent")
        if tx.category in EXTERNAL:
            if tx.buyer_state not in ("U", "C") or tx.distributor_id not in operating:
                raise ValueError("Invalid external retail transaction")
            rows[tx.distributor_id]["retail_margin"] += (
                ctx.config.retail_price - ctx.config.wholesale_price) * tx.units
        else:
            if tx.category is Category.PARTICIPANT_QUALIFICATION:
                raise ValueError("Qualification purchases are disabled")
            if tx.buyer_state != "D" or tx.buyer_id != tx.distributor_id:
                raise ValueError("Participant purchase must belong to its distributor buyer")
            rows[tx.buyer_id]["own_purchase_cost"] += ctx.config.wholesale_price * tx.units
        sponsor = ctx.population.agents[tx.distributor_id].sponsor_id
        if sponsor in operating:
            rows[sponsor]["commission"] += ctx.config.commission_rate * ctx.config.wholesale_price * tx.units
    total_units = sum(tx.units for tx in ctx.transactions)
    commissions = fsum(row["commission"] for row in rows.values())
    if commissions > ctx.config.commission_rate * ctx.config.wholesale_price * total_units + 1e-10:
        raise ValueError("Sponsor commissions exceed the modeled commission base")
    for person_id, row in rows.items():
        gross = row["retail_margin"] + row["commission"]
        expenses = fsum(row[k] for k in ("own_purchase_cost", "operating_cost", "contact_cost", "entry_fee"))
        row.update(gross_earnings=gross, expenses=expenses, net_cash=gross-expenses,
                   operating_at_start=person_id in operating, enrolled_this_month=person_id in ctx.entrants)
        if not all(isfinite(row[k]) for k in ("gross_earnings", "expenses", "net_cash")):
            raise ValueError("Nonfinite accounting result")
        person = ctx.population.agents[person_id]
        person.cumulative_gross_earnings += gross
        person.cumulative_net_cash += row["net_cash"]
        person.recent_net_income = (person.recent_net_income + [row["net_cash"]])[-ctx.config.income_window:]
    external = sum(t.units for t in ctx.transactions if t.category in EXTERNAL)
    if not isclose(fsum(r["retail_margin"] for r in rows.values()),
                   (ctx.config.retail_price-ctx.config.wholesale_price)*external, abs_tol=1e-10):
        raise ValueError("Retail margins do not reconcile with external units")
    ctx.earnings = list(rows.values())
    return ctx.earnings
