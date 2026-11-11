import json
import os
import subprocess
import sys
import pytest
from article25.randomness import EventRandom, Process


def test_event_order_and_unrelated_draws_do_not_change_variates():
    rng = EventRandom(83)
    people = list(range(100))
    expected = {p: rng.uniform(Process.REPURCHASE, 61, p) for p in people}
    for p in range(10):
        rng.uniform(Process.RECRUITMENT_CONVERSION, 61, p, partner_id=300)
    actual = {p: rng.uniform(Process.REPURCHASE, 61, p) for p in reversed(people)}
    assert expected == actual
    assert len(set(expected.values())) == 100
    assert all(0 <= value < 1 for value in expected.values())


def test_process_month_person_and_seed_separate_keys():
    a = EventRandom(83)
    values = {
        a.uniform(Process.REPURCHASE, 61, 4),
        a.uniform(Process.CUSTOMER_EXIT, 61, 4),
        a.uniform(Process.REPURCHASE, 62, 4),
        a.uniform(Process.REPURCHASE, 61, 5),
        EventRandom(84).uniform(Process.REPURCHASE, 61, 4),
        a.uniform(Process.REPURCHASE, 61, 4, partner_id=3),
        a.uniform(Process.REPURCHASE, 61, 4, opportunity_index=1),
    }
    assert len(values) == 7


def test_candidate_ranking_is_order_independent_and_stable_under_filtering():
    rng = EventRandom(83)
    order = rng.rank([2, 4, 7, 9], Process.RETAIL_TARGET, 11, 1)
    assert order == rng.rank([9, 7, 4, 2], Process.RETAIL_TARGET, 11, 1)
    assert rng.rank([2, 7, 9], Process.RETAIL_TARGET, 11, 1) == [p for p in order if p != 4]
    with pytest.raises(ValueError):
        rng.rank([1, 1], Process.ROOTS)


def test_beta_is_person_keyed_and_uses_separate_attribute_streams():
    rng = EventRandom(83)
    first = rng.beta(Process.PRODUCT_FIT, 7, 2, 2)
    rng.beta(Process.PRODUCT_FIT, 8, 2, 2)
    assert rng.beta(Process.PRODUCT_FIT, 7, 2, 2) == first
    assert rng.beta(Process.SELLING_SKILL, 7, 2, 2) != first


@pytest.mark.parametrize("seed", [-1, True, 1.2, "42"])
def test_invalid_seed_rejected(seed):
    with pytest.raises(ValueError):
        EventRandom(seed)


def test_invalid_event_key_rejected_even_for_empty_ranking():
    rng = EventRandom(1)
    with pytest.raises(ValueError):
        rng.uniform(Process.REPURCHASE, -1, 0)
    with pytest.raises(ValueError):
        rng.rank([], "unregistered")


def test_python_hash_randomization_does_not_change_randomness():
    code = """import json
from article25.randomness import EventRandom, Process
r = EventRandom(901)
print(json.dumps([r.uniform(Process.REPURCHASE, 61, 4),
                 r.beta(Process.PRODUCT_FIT, 4, 2, 2),
                 r.rank([4, 3, 2, 1], Process.ROOTS)]))
"""
    outputs = []
    for hash_seed in ("1", "987"):
        env = dict(os.environ, PYTHONHASHSEED=hash_seed)
        outputs.append(subprocess.check_output([sys.executable, "-c", code],
                                               env=env, text=True).strip())
    assert json.loads(outputs[0]) == json.loads(outputs[1])

