from math import sqrt
import pytest
from article25.outcomes import (quantile, distribution, gross_gini, participant_rows,
    participant_outcomes, enriched_monthly, window_summary, paired_effects, summarize_pairs)
from article25.simulation import Simulation
from test_m2_dynamics import simple_config
from test_m2_accounting import chain_fixture
from article25.accounting import settle_month


def test_net_distribution_keeps_negative_values_and_interpolates():
    result = distribution([-4, -2, 0, 2])
    assert result["n"] == 4
    assert result["mean"] == result["median"] == -1
    assert result["q25"] == -2.5 and result["q75"] == .5 and result["iqr"] == 3
    assert result["loss_share"] == .5 and result["positive_share"] == .25


@pytest.mark.parametrize("values,expected,reason", [
    ([], None, "empty_cohort"), ([0, 0], None, "all_gross_earnings_zero"),
    ([1, 1, 1], 0, None), ([0, 0, 3], 2/3, None), ([1, 2, 3], 2/9, None),
    ([1e308, 1e308], 0, None), ([2], 0, None)])
def test_gross_gini_against_analytic_fixtures(values, expected, reason):
    value, actual_reason = gross_gini(values)
    assert actual_reason == reason
    assert value is None if expected is None else value == pytest.approx(expected)


@pytest.mark.parametrize("values", [[-1, 3], [float("nan")], [float("inf")]])
def test_gross_gini_rejects_negative_and_nonfinite(values):
    with pytest.raises(ValueError):
        gross_gini(values)


@pytest.mark.parametrize("p", [-.1, 1.1, float("nan")])
def test_invalid_quantiles_fail(p):
    with pytest.raises(ValueError):
        quantile([0, 1], p)


def test_empty_distribution_has_missing_values_not_zero_income():
    data = distribution([])
    assert data["n"] == 0 and data["missing_reason"] == "empty_cohort"
    assert all(v is None for k, v in data.items() if k not in ("n", "missing_reason"))
    with pytest.raises(ValueError):
        distribution([float("nan")])


def test_participant_output_retains_exited_roots_and_historical_depth():
    ctx, root, child, grandchild = chain_fixture(root_inactive=True)
    settle_month(ctx)
    data = {r["person_id"]: r for r in participant_rows(ctx.population)}
    assert set(data) == {root, child, grandchild}
    assert data[root]["exit_observed"] and not data[root]["right_censored"]
    assert data[root]["tenure_months"] == data[root]["operating_months"] == 2
    assert data[grandchild]["sponsor_depth"] == 2
    assert data[grandchild]["operating_months"] == 1
    summary = participant_outcomes(list(data.values()))
    assert summary["all_ever_cumulative_net_n"] == 3
    assert summary["end_active_cumulative_net_n"] == 2
    assert summary["all_ever_cumulative_net_loss_share"] == 2/3
    assert summary["end_active_cumulative_net_loss_share"] == 1
    assert not any("net_gini" in key for key in summary)


def test_extinction_reports_losses_for_all_ever_and_missing_active_income():
    sim = Simulation.initialize(simple_config(distributor_churn=1, entry_fee=.2), 1).run(4)
    data = participant_outcomes(participant_rows(sim.population))
    assert data["all_ever_cumulative_net_n"] == 1
    assert data["all_ever_cumulative_net_median"] == -.2
    assert data["all_ever_cumulative_net_loss_share"] == 1
    assert data["end_active_cumulative_net_n"] == 0
    assert data["end_active_cumulative_net_median"] is None
    assert data["all_ever_cumulative_gross_gini_reason"] == "all_gross_earnings_zero"


def test_monthly_enrichment_respects_cohort_and_denominators():
    sim = Simulation.initialize(simple_config(distributor_churn=1), 1).run(3)
    rows = enriched_monthly(sim)
    assert rows[0]["monthly_net_n"] == 1  # Exit at month-end is included.
    assert rows[1]["monthly_net_n"] == 0 and rows[1]["monthly_net_median"] is None
    assert rows[1]["external_retail_share_reason"] == "zero_total_units"
    assert rows[1]["distributor_churn_rate_reason"] == "zero_operating_distributors"
    assert rows[1]["repeat_contact_overlap"] == 0
    assert rows[1]["maximum_sponsor_depth"] == 0 and rows[1]["all_ever_participants"] == 1


WINDOWS = [{"name": "late", "start": 1, "end": 2}]


def monthly(external=(2, 3), distributors=(1, 2), net=(-1, -3)):
    return [{"month": m, "external_units": e, "total_units": e+1, "n_D": d,
             "median_net_cash": n, "new_recruits": 0}
            for m, (e, d, n) in enumerate(zip(external, distributors, net), 1)]


def test_paired_estimands_have_correct_sign_windows_and_negative_net_difference():
    control = monthly()
    shock = monthly(external=(4, 6), distributors=(1, 1), net=(-2, -4))
    effects = {r["outcome"]: r for r in paired_effects(control, shock, WINDOWS)}
    external = effects["external_units"]
    assert external["control"] == 5 and external["shock"] == 10 and external["difference"] == 5
    assert external["resilience_ratio"] == 2 and external["recruitment_dependence"] == -1
    assert external["low_control_external_volume"]
    assert effects["distributor_months"]["resilience_ratio"] == 2/3
    net = effects["mean_monthly_median_net_cash"]
    assert net["control"] == -2 and net["shock"] == -3 and net["difference"] == -1
    assert net["resilience_ratio"] is None and net["ratio_reason"] == "not_defined_for_net_earnings"


@pytest.mark.parametrize("shock_external", [(0, 0), (1, 5)])
def test_zero_control_denominator_is_undefined_even_with_positive_shock(shock_external):
    effect = paired_effects(monthly(external=(0, 0)), monthly(external=shock_external), WINDOWS)[0]
    assert effect["resilience_ratio"] is None
    assert effect["ratio_reason"] == "zero_control_denominator"
    assert effect["difference"] == sum(shock_external)


def test_low_control_flag_threshold_and_zero_numerator():
    effect = paired_effects(monthly(external=(6, 6)), monthly(external=(0, 0)), WINDOWS)[0]
    assert not effect["low_control_external_volume"] and effect["resilience_ratio"] == 0
    assert effect["recruitment_dependence"] == 1


def test_missing_monthly_income_does_not_become_zero_or_selected_month_mean():
    effects = paired_effects(monthly(), monthly(net=(None, -3)), WINDOWS)
    net = effects[2]
    assert net["shock"] is None and net["difference"] is None
    assert net["shock_net_valid_months"] == 1
    assert net["difference_reason"] == "empty_monthly_cohort"


@pytest.mark.parametrize("months", [[1], [1, 1], [2, 1]])
def test_window_rejects_missing_duplicate_or_disordered_months(months):
    source = monthly()
    with pytest.raises(ValueError):
        window_summary([source[m-1] for m in months], WINDOWS)


def test_replicate_summary_uses_pairs_and_reports_simulation_interval_separately():
    rows = []
    for i, delta in enumerate([2, 4, 6]):
        rows.append({"experiment_id": "e", "scenario_id": "s", "window": "late",
                     "outcome": "external_units", "pair_id": str(i), "difference": delta,
                     "resilience_ratio": None, "low_control_external_volume": True})
    result = summarize_pairs(rows)[0]
    assert result["pairs"] == result["difference_n"] == 3
    assert result["difference_mean"] == result["difference_median"] == 4
    assert result["difference_iqr"] == 2
    assert result["mean_difference_standard_error"] == pytest.approx(2/sqrt(3))
    assert result["undefined_ratios"] == 3
    assert result["percentile_interval_kind"] == "simulation_distribution_not_mean_CI"
    assert summarize_pairs(rows[:1])[0]["mean_difference_standard_error"] is None
    with pytest.raises(ValueError, match="Duplicate"):
        summarize_pairs(rows+rows[:1])
