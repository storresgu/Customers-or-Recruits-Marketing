"""Numerically stable, bounded probability rules from specification v0.1."""
import math
from .config import require_number


def adjusted_probability(base: float, adjustment: float) -> float:
    require_number("base probability", base, maximum=1)
    require_number("behavioral adjustment", adjustment, -float("inf"))
    if base in (0, 1):
        return float(base)
    z = math.log(base) - math.log1p(-base) + adjustment
    if z >= 0:
        return 1 / (1 + math.exp(-z))
    exp_z = math.exp(z)
    return exp_z / (1 + exp_z)


def retail_probability(config, seller, customer) -> float:
    return adjusted_probability(config.p_retail,
        config.fit_weight * (2 * customer.product_fit - 1)
        + config.selling_weight * (2 * seller.selling_skill - 1)
        - config.fatigue * customer.retail_exposures)


def recruitment_probability(config, recruiter, prospect, multiplier: float) -> float:
    require_number("recruitment multiplier", multiplier, maximum=1)
    return multiplier * adjusted_probability(config.p_recruit,
        config.fit_weight * (2 * prospect.product_fit - 1)
        + config.recruiting_weight * (2 * recruiter.recruiting_skill - 1)
        - config.fatigue * prospect.recruitment_exposures)


def repurchase_probability(config, customer) -> float:
    return adjusted_probability(config.p_repurchase,
                                config.fit_weight * (2 * customer.product_fit - 1))


def personal_probability(config, participant) -> float:
    return adjusted_probability(config.p_personal,
                                config.fit_weight * (2 * participant.product_fit - 1))


def customer_exit_probability(config, unserved: bool) -> float:
    if type(unserved) is not bool:
        raise ValueError("unserved must be boolean")
    return min(1.0, config.customer_churn + config.unserved_churn_increment * unserved)


def distributor_exit_probability(config, history: list[float]) -> float:
    if not history:
        raise ValueError("Distributor exit requires current-month net cash history")
    for value in history:
        require_number("net cash", value, -float("inf"))
    recent = math.fsum(history[-config.income_window:]) / min(len(history), config.income_window)
    loss = min(1.0, max(0.0, -recent / config.loss_scale))
    return min(1.0, config.distributor_churn + config.loss_exit_weight * loss)
