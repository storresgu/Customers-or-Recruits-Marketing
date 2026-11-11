import pytest
from article25.agents import State, require_transition


@pytest.mark.parametrize("source", list(State))
@pytest.mark.parametrize("target", list(State))
def test_complete_state_transition_contract(source, target):
    expected = {("U", "C"), ("U", "D"), ("C", "U"), ("C", "D"), ("D", "I")}
    if (source.value, target.value) in expected:
        require_transition(source, target)
    else:
        with pytest.raises(ValueError):
            require_transition(source, target)


def structural_enrollment(pop):
    """Manual fixture only: no probability, transaction, or recruitment engine."""
    root = pop.root_ids[0]
    recruit = next(j for j in pop.social_graph.neighbors(root)
                   if j not in pop.root_ids)
    pop.month = 1
    person = pop.agents[recruit]
    person.state = State.DISTRIBUTOR
    person.state_since_month = 1
    person.enrollment_month = 1
    person.first_operating_month = 2
    person.sponsor_id = root
    pop.sponsor_graph.add_edge(root, recruit)
    return root, recruit


def test_future_participant_structure_and_next_month_activation(population):
    root, recruit = structural_enrollment(population)
    population.validate()
    assert recruit not in population.operating_ids(1)
    assert recruit in population.operating_ids(2)
    assert population.sponsor_graph.in_degree(recruit) == 1


def test_sponsor_history_survives_exit(population):
    root, recruit = structural_enrollment(population)
    population.agents[root].state = State.INACTIVE
    population.agents[root].state_since_month = 1
    population.agents[root].exit_month = 1
    population.validate()
    assert population.sponsor_graph.has_edge(root, recruit)
    assert root not in population.operating_ids(2)
    assert population.agents[recruit].sponsor_id == root


@pytest.mark.parametrize("damage", ["two_sponsors", "cycle", "self_sponsor",
                                  "graph_metadata_mismatch", "absent_participant",
                                  "early_sponsor", "exited_sponsor"])
def test_sponsor_corruption_rejected(population, damage):
    root, recruit = structural_enrollment(population)
    if damage == "two_sponsors":
        population.sponsor_graph.add_edge(population.root_ids[1], recruit)
    elif damage == "cycle":
        population.sponsor_graph.add_edge(recruit, root)
    elif damage == "self_sponsor":
        population.sponsor_graph.add_edge(recruit, recruit)
    elif damage == "graph_metadata_mismatch":
        population.agents[recruit].sponsor_id = population.root_ids[1]
    elif damage == "absent_participant":
        population.sponsor_graph.add_node(next(a.person_id for a in population.agents
                                              if a.state is State.PROSPECT))
    elif damage == "early_sponsor":
        population.agents[recruit].enrollment_month = 0
        population.agents[recruit].first_operating_month = 1
    elif damage == "exited_sponsor":
        population.month = 2
        population.agents[recruit].enrollment_month = 2
        population.agents[recruit].first_operating_month = 3
        population.agents[root].state = State.INACTIVE
        population.agents[root].exit_month = 1
    with pytest.raises(ValueError):
        population.validate()


def test_customer_and_participant_status_are_exclusive(population):
    root = population.root_ids[0]
    customer = next(j for j in population.social_graph.neighbors(root)
                    if j not in population.root_ids)
    population.month = 1
    person = population.agents[customer]
    person.state = State.CUSTOMER
    person.ever_customer = True
    person.seller_id = root
    person.customer_since_month = 1
    person.last_purchase_month = 1
    person.state_since_month = 1
    population.validate()
    assert customer not in population.sponsor_graph
    person.sponsor_id = root
    with pytest.raises(ValueError, match="Nonparticipants"):
        population.validate()

