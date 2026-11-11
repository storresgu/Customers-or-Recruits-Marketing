"""Generate one finite social graph without connectivity retries."""
import networkx as nx
from .config import ModelConfig, require_int
from .randomness import EventRandom, Process


def generate_social_graph(config: ModelConfig, rng: EventRandom) -> nx.Graph:
    return nx.watts_strogatz_graph(config.population_size, config.social_degree,
                                   config.rewiring_p, seed=rng.seed_for(Process.NETWORK))


def select_roots(graph: nx.Graph, count: int, rng: EventRandom) -> tuple[int, ...]:
    require_int("root count", count)
    eligible = sorted(node for node, degree in graph.degree if degree > 0)
    if len(eligible) < count:
        raise ValueError(f"Need {count} initial distributors but only "
                         f"{len(eligible)} nonisolated people are eligible")
    return tuple(sorted(rng.rank(eligible, Process.ROOTS)[:count]))


def initialize_sponsor_graph(root_ids: tuple[int, ...]) -> nx.DiGraph:
    graph = nx.DiGraph()
    graph.add_nodes_from(root_ids)
    return graph


def social_summary(graph: nx.Graph) -> dict:
    sizes = sorted((len(c) for c in nx.connected_components(graph)), reverse=True)
    n = graph.number_of_nodes()
    return {
        "nodes": n,
        "edges": graph.number_of_edges(),
        "mean_degree": 2 * graph.number_of_edges() / n,
        "component_count": len(sizes),
        "component_sizes": sizes,
        "largest_component_share": sizes[0] / n,
        "isolated_nodes": nx.number_of_isolates(graph),
    }
