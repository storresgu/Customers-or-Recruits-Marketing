from dataclasses import replace
import networkx as nx
import numpy as np
import pytest
from article25 import ModelConfig, initialize_population
from article25.agents import State
import article25.model as model_module


def test_reference_population_and_graph_contract():
    pop = initialize_population(ModelConfig(), 20260925)
    assert pop.counts() == {"U": 1990, "C": 0, "D": 10, "I": 0}
    assert set(pop.social_graph) == set(range(2000))
    assert pop.social_graph.number_of_edges() == 10000
    assert not pop.social_graph.is_directed()
    assert nx.number_of_selfloops(pop.social_graph) == 0
    assert len(pop.root_ids) == 10
    assert all(pop.social_graph.degree(x) > 0 for x in pop.root_ids)
    assert set(pop.sponsor_graph) == set(pop.root_ids)
    assert pop.sponsor_graph.number_of_edges() == 0
    assert pop.operating_ids(0) == ()
    assert pop.operating_ids(1) == pop.root_ids
    assert all(a.sponsor_id is None for a in pop.agents)
    assert all(a.cumulative_net_cash == 0 for a in pop.agents)


def test_seed_reproducibility_and_seed_variation(config):
    one = initialize_population(config, 71)
    two = initialize_population(config, 71)
    three = initialize_population(config, 72)
    assert one.to_dict() == two.to_dict()
    assert one.state_hash != three.state_hash
    assert one.root_ids != three.root_ids
    assert [a.product_fit for a in one.agents] != [a.product_fit for a in three.agents]
    assert set(one.social_graph.edges) != set(three.social_graph.edges)


def test_heterogeneity_bounds_and_distribution_diagnostics():
    pop = initialize_population(ModelConfig(), 91)
    matrix = np.array([[a.product_fit, a.selling_skill, a.recruiting_skill]
                       for a in pop.agents])
    assert np.all((matrix >= 0) & (matrix <= 1))
    assert np.all(np.abs(matrix.mean(axis=0) - 0.5) < 0.04)
    assert np.all(np.abs(matrix.var(axis=0) - 0.05) < 0.015)
    assert np.max(np.abs(np.corrcoef(matrix.T) - np.eye(3))) < 0.15


def test_homogeneous_variant_preserves_graph_and_roots(config):
    heterogeneous = initialize_population(config, 51)
    homogeneous = initialize_population(replace(config, homogeneous_agents=True), 51)
    assert homogeneous.root_ids == heterogeneous.root_ids
    assert set(homogeneous.social_graph.edges) == set(heterogeneous.social_graph.edges)
    assert all((a.product_fit, a.selling_skill, a.recruiting_skill) == (0.5, 0.5, 0.5)
               for a in homogeneous.agents)


def test_attributes_do_not_depend_on_initial_commercial_role(config):
    one = initialize_population(config, 51)
    two = initialize_population(replace(config, initial_distributors=0), 51)
    assert [(a.product_fit, a.selling_skill, a.recruiting_skill) for a in one.agents] == [
        (a.product_fit, a.selling_skill, a.recruiting_skill) for a in two.agents]


def test_ring_lattice_at_zero_rewiring():
    config = ModelConfig(population_size=20, social_degree=4, initial_distributors=2,
                         rewiring_p=0)
    pop = initialize_population(config, 7)
    for person in range(20):
        assert set(pop.social_graph.neighbors(person)) == {
            (person + offset) % 20 for offset in (-2, -1, 1, 2)}


@pytest.mark.parametrize("root_count", [0, 20])
def test_no_distributors_and_fully_enrolled_population(root_count):
    config = ModelConfig(population_size=20, social_degree=4,
                         initial_distributors=root_count)
    pop = initialize_population(config, 7)
    assert pop.counts() == {"U": 20-root_count, "C": 0, "D": root_count, "I": 0}
    assert len(pop.sponsor_graph) == root_count


def test_isolated_population_allowed_without_roots_but_not_with_roots():
    config = ModelConfig(population_size=1, social_degree=0, initial_distributors=0)
    pop = initialize_population(config, 8)
    assert pop.summary()["social"]["component_count"] == 1
    assert pop.summary()["social"]["isolated_nodes"] == 1
    with pytest.raises(ValueError, match="nonisolated"):
        initialize_population(replace(config, initial_distributors=1), 8)


def test_disconnected_realization_is_preserved_without_retry(monkeypatch):
    # Two triangles satisfy N=6, k=2 and provide a deliberate disconnected graph.
    graph = nx.disjoint_union(nx.cycle_graph(3), nx.cycle_graph(3))
    calls = []
    def generator(config, rng):
        calls.append(1)
        return graph.copy()
    monkeypatch.setattr(model_module, "generate_social_graph", generator)
    pop = initialize_population(ModelConfig(population_size=6, social_degree=2,
                                           initial_distributors=2), 7)
    assert calls == [1]
    assert pop.summary()["social"]["component_sizes"] == [3, 3]
    assert set(pop.social_graph.edges) == set(graph.edges)


@pytest.mark.parametrize("damage", ["missing_person", "duplicate_id", "invalid_state",
                                  "missing_social_node", "social_self_loop",
                                  "duplicate_roots", "nonfinite_attribute",
                                  "premature_revenue", "early_activation"])
def test_corrupted_initial_state_rejected(population, damage):
    root = population.root_ids[0]
    if damage == "missing_person":
        population.agents.pop()
    elif damage == "duplicate_id":
        population.agents[1].person_id = 0
    elif damage == "invalid_state":
        population.agents[1].state = "unknown"
    elif damage == "missing_social_node":
        population.social_graph.remove_node(0)
    elif damage == "social_self_loop":
        population.social_graph.add_edge(0, 0)
    elif damage == "duplicate_roots":
        population.root_ids = (root, root, root)
    elif damage == "nonfinite_attribute":
        population.agents[0].product_fit = float("nan")
    elif damage == "premature_revenue":
        population.agents[root].cumulative_gross_earnings = 1
    elif damage == "early_activation":
        population.agents[root].first_operating_month = 0
    with pytest.raises(ValueError):
        population.validate()


def test_clone_has_no_shared_mutable_structures(population):
    cloned = population.clone()
    assert cloned.to_dict() == population.to_dict()
    cloned.agents[0].recent_net_income.append(-1)
    cloned.social_graph.remove_edge(*next(iter(cloned.social_graph.edges)))
    cloned.sponsor_graph.add_node(999)
    assert population.agents[0].recent_net_income == []
    assert population.social_graph.number_of_edges() == 180
    assert 999 not in population.sponsor_graph
    population.validate()

