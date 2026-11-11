"""Participant and paired estimands. Missing values retain explicit reasons.

Quantiles use linear interpolation at (n-1)*p. Earnings are normalized cash,
not firm profit or the utility of personal consumption. No net-income Gini.
"""
from collections import defaultdict
from math import fsum, isfinite, sqrt
from statistics import stdev
import networkx as nx
from .agents import State


def quantile(values, probability):
    if not isinstance(probability, (int, float)) or not isfinite(probability) or not 0 <= probability <= 1:
        raise ValueError("Quantile probability must be in [0, 1]")
    ordered = sorted(values)
    if not ordered:
        return None
    position = (len(ordered)-1)*probability
    low = int(position)
    high = min(low+1, len(ordered)-1)
    return ordered[low] + (ordered[high]-ordered[low])*(position-low)


def distribution(values):
    values = list(values)
    if any(not isfinite(x) for x in values):
        raise ValueError("Distribution requires finite values")
    n = len(values)
    result = {"n": n, "missing_reason": None if n else "empty_cohort",
              "mean": fsum(values)/n if n else None}
    for name, p in (("q05", .05), ("q25", .25), ("median", .5), ("q75", .75), ("q95", .95)):
        result[name] = quantile(values, p)
    result.update(iqr=result["q75"]-result["q25"] if n else None,
                  loss_share=sum(x < 0 for x in values)/n if n else None,
                  positive_share=sum(x > 0 for x in values)/n if n else None)
    return result


def gross_gini(values):
    values = sorted(values)
    if any(not isfinite(x) or x < 0 for x in values):
        raise ValueError("Conventional Gini requires finite nonnegative gross earnings")
    if not values:
        return None, "empty_cohort"
    if values[-1] == 0:
        return None, "all_gross_earnings_zero"
    # Scaling prevents overflow without shifting observations or changing Gini.
    scaled = [x/values[-1] for x in values]
    n = len(scaled)
    value = fsum((2*i-n-1)*x for i, x in enumerate(scaled, 1))/(n*fsum(scaled))
    return value, None


def participant_rows(population):
    """One row per all-ever participant, retaining exited agents and censoring."""
    population.validate()
    depths = {}
    for person_id in nx.topological_sort(population.sponsor_graph):
        person = population.agents[person_id]
        depths[person_id] = 0 if person.sponsor_id is None else depths[person.sponsor_id]+1
    rows = []
    for person_id in sorted(depths):
        p = population.agents[person_id]
        end = p.exit_month if p.exit_month is not None else population.month
        neighbors = [population.agents[i] for i in population.social_graph.neighbors(person_id)]
        rows.append({
            "person_id": person_id, "final_state": p.state.value,
            "enrollment_month": p.enrollment_month, "first_operating_month": p.first_operating_month,
            "exit_month": p.exit_month, "exit_observed": p.exit_month is not None,
            "right_censored": p.exit_month is None,
            "tenure_months": end-p.enrollment_month,
            "operating_months": max(0, end-p.first_operating_month+1),
            "sponsor_id": p.sponsor_id, "sponsor_depth": depths[person_id],
            "cumulative_gross_earnings": p.cumulative_gross_earnings,
            "cumulative_net_cash": p.cumulative_net_cash,
            "retail_exposures": p.retail_exposures,
            "recruitment_exposures": p.recruitment_exposures,
            "eligible_retail_neighbors_at_end": sum(a.state is State.PROSPECT for a in neighbors),
            "eligible_recruitment_neighbors_at_end": sum(
                a.state in (State.PROSPECT, State.CUSTOMER) for a in neighbors),
        })
    return rows


def participant_outcomes(rows):
    result = {}
    for label, cohort in (("all_ever", rows), ("end_active", [r for r in rows if r["final_state"] == "D"])):
        for key, value in distribution(r["cumulative_net_cash"] for r in cohort).items():
            result[f"{label}_cumulative_net_{key}"] = value
        gini, reason = gross_gini(r["cumulative_gross_earnings"] for r in cohort)
        result[f"{label}_cumulative_gross_gini"] = gini
        result[f"{label}_cumulative_gross_gini_reason"] = reason
        result[f"{label}_cumulative_gross_total"] = fsum(r["cumulative_gross_earnings"] for r in cohort)
        result[f"{label}_cumulative_net_total"] = fsum(r["cumulative_net_cash"] for r in cohort)
    return result


def enriched_monthly(simulation):
    """Derive reporting fields without changing M2's behavioral schedule."""
    by_month = defaultdict(list)
    for r in simulation.earnings:
        by_month[r["month"]].append(r)
    participants = participant_rows(simulation.population)
    result = []
    for base in simulation.monthly:
        row = dict(base)
        enrolled = [p for p in participants if p["enrollment_month"] <= row["month"]]
        row["all_ever_participants"] = len(enrolled)
        row["maximum_sponsor_depth"] = max((p["sponsor_depth"] for p in enrolled), default=None)
        for key, value in distribution(r["net_cash"] for r in by_month[base["month"]]).items():
            row["monthly_net_"+key] = value
        contacts = row["retail_contacts"]+row["recruitment_contacts"]
        row["repeat_contact_overlap"] = contacts-row["distinct_people_contacted"]
        row["repeat_contact_overlap_share"] = row["repeat_contact_overlap"]/contacts if contacts else None
        row["repeat_contact_overlap_reason"] = None if contacts else "zero_actual_contacts"
        for metric, denominator in (
            ("external_retail_share", "total_units"),
            ("observed_repurchase_rate", "repurchase_eligible"),
            ("served_repurchase_rate", "served_customers"),
            ("customer_churn_rate", "repurchase_eligible"),
            ("distributor_churn_rate", "operating_distributors"),
            ("positive_monthly_net_share", "earnings_cohort_size")):
            row[metric+"_reason"] = None if row[denominator] else "zero_"+denominator
        result.append(row)
    return result


def window_summary(monthly, windows):
    result = []
    for window in windows:
        start, end = window["start"], window["end"]
        selected = [r for r in monthly if start <= r["month"] <= end]
        if [r["month"] for r in selected] != list(range(start, end+1)):
            raise ValueError("A reporting window must contain every month exactly once")
        n = len(selected)
        net = [r["median_net_cash"] for r in selected if r["median_net_cash"] is not None]
        external = sum(r["external_units"] for r in selected)
        total = sum(r["total_units"] for r in selected)
        result.append({"window": window["name"], "start_month": start, "end_month": end,
                       "months": n, "external_units": external, "total_units": total,
                       "external_retail_share": external/total if total else None,
                       "external_retail_share_reason": None if total else "zero_total_units",
                       "distributor_months": sum(r["n_D"] for r in selected),
                       "mean_monthly_median_net_cash": fsum(net)/n if len(net) == n else None,
                       "net_median_valid_months": len(net),
                       "net_median_reason": None if len(net) == n else "empty_monthly_cohort",
                       "new_recruits": sum(r["new_recruits"] for r in selected)})
    return result


def paired_effects(control, shock, windows):
    result = []
    for c, s in zip(window_summary(control, windows), window_summary(shock, windows)):
        for outcome in ("external_units", "distributor_months", "mean_monthly_median_net_cash"):
            cv, sv = c[outcome], s[outcome]
            missing = cv is None or sv is None
            net = outcome == "mean_monthly_median_net_cash"
            ratio = None if net or cv == 0 or missing else sv/cv
            reason = ("not_defined_for_net_earnings" if net else
                      "missing_outcome" if missing else "zero_control_denominator" if cv == 0 else None)
            result.append({
                "window": c["window"], "start_month": c["start_month"], "end_month": c["end_month"],
                "outcome": outcome, "control": cv, "shock": sv,
                "difference": None if missing else sv-cv,
                "difference_reason": "empty_monthly_cohort" if missing else None,
                "resilience_ratio": ratio, "ratio_reason": reason,
                "recruitment_dependence": 1-ratio if ratio is not None else None,
                "low_control_external_volume": c["external_units"] < 12,
                "control_net_valid_months": c["net_median_valid_months"] if net else None,
                "shock_net_valid_months": s["net_median_valid_months"] if net else None,
            })
    return result


def summarize_pairs(rows):
    """Independent pairs are the sampling units; monthly rows are never replicas."""
    groups = defaultdict(list)
    seen = set()
    for r in rows:
        key = (r["experiment_id"], r["scenario_id"], r["window"], r["outcome"])
        identity = (*key, r["pair_id"])
        if identity in seen:
            raise ValueError("Duplicate pair/window/outcome in aggregate")
        seen.add(identity)
        groups[key].append(r)
    result = []
    for (experiment, scenario, window, outcome), group in sorted(groups.items()):
        differences = [r["difference"] for r in group if r["difference"] is not None]
        stats = distribution(differences)
        n = len(differences)
        result.append({"experiment_id": experiment, "scenario_id": scenario,
                       "window": window, "outcome": outcome, "pairs": len(group),
                       **{"difference_"+k: v for k, v in stats.items()},
                       "difference_p025": quantile(differences, .025),
                       "difference_p975": quantile(differences, .975),
                       "percentile_interval_kind": "simulation_distribution_not_mean_CI",
                       "mean_difference_standard_error": stdev(differences)/sqrt(n) if n > 1 else None,
                       "standard_error_reason": None if n > 1 else "fewer_than_two_valid_pairs",
                       "undefined_ratios": sum(r["resilience_ratio"] is None for r in group),
                       "low_control_pairs": sum(r["low_control_external_volume"] for r in group)})
    return result
