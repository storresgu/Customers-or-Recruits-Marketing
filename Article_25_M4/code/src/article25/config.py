"""Strict, explicit configuration. Behavioral parameters are reserved for M2/M3."""
from dataclasses import asdict, dataclass, fields
import hashlib
import json
import math
from pathlib import Path


def require_int(name: str, value: object, minimum: int = 0) -> None:
    if type(value) is not int or value < minimum:
        raise ValueError(f"{name} must be an integer >= {minimum}, not {value!r}")


def require_number(name: str, value: object, minimum: float = 0.0,
                   maximum: float | None = None, strict_min: bool = False) -> None:
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < minimum or (strict_min and value == minimum):
        raise ValueError(f"{name} is below its permitted bound")
    if maximum is not None and value > maximum:
        raise ValueError(f"{name} must be <= {maximum}")


def canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def read_json(path: str | Path):
    return json.loads(Path(path).read_text(encoding="utf-8"),
                      object_pairs_hook=_unique_object)


@dataclass(frozen=True, slots=True)
class ModelConfig:
    population_size: int = 2000
    initial_distributors: int = 10
    initial_customers: int = 0
    horizon_months: int = 120
    social_degree: int = 10
    rewiring_p: float = 0.10
    contact_budget: int = 10
    recruitment_share: float = 0.50
    p_retail: float = 0.08
    p_repurchase: float = 0.60
    p_recruit: float = 0.04
    customer_churn: float = 0.02
    unserved_churn_increment: float = 0.05
    distributor_churn: float = 0.01
    loss_exit_weight: float = 0.04
    loss_scale: float = 0.30
    income_window: int = 3
    fatigue: float = 0.10
    heterogeneity_alpha: float = 2.0
    heterogeneity_beta: float = 2.0
    homogeneous_agents: bool = False
    fit_weight: float = 1.0
    selling_weight: float = 1.0
    recruiting_weight: float = 1.0
    p_personal: float = 0.30
    entry_units: int = 1
    new_entrant_window: int = 3
    retail_price: float = 1.00
    wholesale_price: float = 0.70
    commission_rate: float = 0.10
    fixed_operating_cost: float = 0.05
    cost_per_contact: float = 0.005
    entry_fee: float = 0.20
    qualification_enabled: bool = False
    shock_start_month: int = 61
    recruitment_multiplier: float = 1.0

    def __post_init__(self):
        for name in ("population_size", "horizon_months", "income_window",
                     "new_entrant_window", "shock_start_month"):
            require_int(name, getattr(self, name), 1)
        for name in ("initial_distributors", "initial_customers", "social_degree",
                     "contact_budget", "entry_units"):
            require_int(name, getattr(self, name))
        if self.initial_distributors > self.population_size:
            raise ValueError("initial_distributors exceeds population_size")
        if self.initial_customers != 0:
            raise ValueError("v0.1 requires initial_customers = 0")
        if self.social_degree % 2 or self.social_degree >= self.population_size:
            raise ValueError("social_degree must be even and smaller than population_size")
        if self.shock_start_month > self.horizon_months + 1:
            raise ValueError("shock_start_month must be <= horizon_months + 1")
        for name in ("rewiring_p", "recruitment_share", "p_retail", "p_repurchase",
                     "p_recruit", "customer_churn", "unserved_churn_increment",
                     "distributor_churn", "loss_exit_weight", "p_personal",
                     "commission_rate", "recruitment_multiplier"):
            require_number(name, getattr(self, name), maximum=1)
        for name in ("loss_scale", "heterogeneity_alpha", "heterogeneity_beta",
                     "retail_price"):
            require_number(name, getattr(self, name), strict_min=True)
        for name in ("fatigue", "fit_weight", "selling_weight", "recruiting_weight",
                     "wholesale_price", "fixed_operating_cost", "cost_per_contact",
                     "entry_fee"):
            require_number(name, getattr(self, name))
        if self.wholesale_price > self.retail_price:
            raise ValueError("wholesale_price cannot exceed retail_price")
        if type(self.homogeneous_agents) is not bool:
            raise ValueError("homogeneous_agents must be boolean")
        if self.qualification_enabled is not False:
            raise ValueError("Qualification purchasing is not implemented in v0.1")

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "ModelConfig":
        if not isinstance(data, dict):
            raise ValueError("Configuration must be a JSON object")
        unknown = set(data) - {f.name for f in fields(cls)}
        if unknown:
            raise ValueError(f"Unknown configuration fields: {sorted(unknown)}")
        return cls(**data)

    @classmethod
    def from_json(cls, path: str | Path) -> "ModelConfig":
        return cls.from_dict(read_json(path))

    @property
    def config_hash(self) -> str:
        return hashlib.sha256(canonical_json(self.to_dict()).encode()).hexdigest()

