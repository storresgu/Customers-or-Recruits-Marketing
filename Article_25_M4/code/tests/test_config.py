import json
import pytest
from article25 import ModelConfig


def test_specification_defaults():
    c = ModelConfig()
    assert (c.population_size, c.initial_distributors, c.initial_customers) == (2000, 10, 0)
    assert (c.social_degree, c.rewiring_p) == (10, 0.10)
    assert (c.horizon_months, c.shock_start_month) == (120, 61)
    assert (c.heterogeneity_alpha, c.heterogeneity_beta) == (2, 2)
    assert c.recruitment_multiplier == 1
    assert not c.qualification_enabled


@pytest.mark.parametrize("field,value", [
    ("population_size", 0), ("population_size", True), ("population_size", 20.5),
    ("initial_distributors", -1), ("initial_distributors", 2001),
    ("initial_customers", 1), ("social_degree", 3), ("social_degree", 2000),
    ("rewiring_p", -0.1), ("rewiring_p", 1.1), ("p_retail", float("nan")),
    ("p_repurchase", float("inf")), ("p_recruit", True), ("loss_scale", 0),
    ("heterogeneity_alpha", 0), ("heterogeneity_beta", -1),
    ("homogeneous_agents", 1), ("horizon_months", 0), ("shock_start_month", 122),
    ("wholesale_price", 1.1), ("entry_units", 0.5), ("entry_fee", -1),
    ("qualification_enabled", True), ("qualification_enabled", 0),
    ("contact_budget", -1), ("income_window", 0),
])
def test_invalid_config_is_rejected(field, value):
    with pytest.raises(ValueError):
        ModelConfig(**{field: value})


def test_extreme_valid_configuration():
    c = ModelConfig(population_size=1, social_degree=0, initial_distributors=0,
                    p_retail=0, p_repurchase=1, p_recruit=0, rewiring_p=1,
                    contact_budget=0, entry_units=0, commission_rate=0)
    assert c.population_size == 1


def test_config_json_roundtrip_and_stable_hash(tmp_path):
    config = ModelConfig()
    path = tmp_path / "config.json"
    path.write_text(json.dumps(config.to_dict()))
    reverse_order = dict(reversed(list(config.to_dict().items())))
    assert ModelConfig.from_json(path) == config
    assert ModelConfig.from_dict(reverse_order).config_hash == config.config_hash
    assert ModelConfig(p_retail=0.09).config_hash != config.config_hash


def test_unknown_and_duplicate_parameters_rejected(tmp_path):
    with pytest.raises(ValueError, match="Unknown"):
        ModelConfig.from_dict({"population_szie": 100})
    path = tmp_path / "duplicate.json"
    path.write_text('{"p_retail": 0.1, "p_retail": 0.2}')
    with pytest.raises(ValueError, match="Duplicate"):
        ModelConfig.from_json(path)

