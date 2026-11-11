"""Population initialization, invariants, snapshots, and independent cloning.

Population retains structural responsibilities. Monthly behavior is implemented
by Simulation in simulation.py.
"""
from collections import Counter
from dataclasses import dataclass, fields
import copy
import hashlib
import json
from pathlib import Path
import networkx as nx
from . import MODEL_VERSION, SPEC_VERSION
from .agents import Agent, State
from .config import ModelConfig, canonical_json, read_json, require_int
from .networks import generate_social_graph, initialize_sponsor_graph, select_roots, social_summary
from .randomness import EventRandom, Process, RNG_SCHEMA

SNAPSHOT_SCHEMA = "article25-population-v1"


@dataclass
class Population:
    config: ModelConfig
    seed: int
    agents: list[Agent]
    social_graph: nx.Graph
    sponsor_graph: nx.DiGraph
    root_ids: tuple[int, ...]
    month: int = 0

    @property
    def random(self) -> EventRandom:
        return EventRandom(self.seed)

    def counts(self) -> dict[str, int]:
        counts = Counter(agent.state for agent in self.agents)
        return {state.value: counts[state] for state in State}

    def operating_ids(self, month: int) -> tuple[int, ...]:
        return tuple(a.person_id for a in self.agents if a.can_operate(month))

    def validate(self) -> None:
        """Raise ValueError for a structural violation; do not repair silently."""
        if not isinstance(self.config, ModelConfig):
            raise ValueError("config must be a ModelConfig")
        self.config.__post_init__()
        require_int("seed", self.seed)
        require_int("month", self.month)
        if self.month > self.config.horizon_months:
            raise ValueError("month exceeds the configured horizon")
        n = self.config.population_size
        if len(self.agents) != n or any(not isinstance(a, Agent) for a in self.agents):
            raise ValueError("Population must contain exactly N Agent instances")
        for agent in self.agents:
            agent.validate(self.month)
        if [a.person_id for a in self.agents] != list(range(n)):
            raise ValueError("Agents must have unique, consecutive, ordered IDs 0..N-1")
        if type(self.social_graph) is not nx.Graph:
            raise ValueError("social_graph must be a simple undirected Graph")
        if type(self.sponsor_graph) is not nx.DiGraph:
            raise ValueError("sponsor_graph must be a simple directed DiGraph")
        if any(type(node) is not int for node in self.social_graph):
            raise ValueError("Social node IDs must be integers")
        if set(self.social_graph) != set(range(n)):
            raise ValueError("Social graph must contain exactly the population")
        if nx.number_of_selfloops(self.social_graph):
            raise ValueError("Social graph cannot have self-loops")
        # The social graph is static; rewiring preserves its edge count.
        if self.social_graph.number_of_edges() != n * self.config.social_degree // 2:
            raise ValueError("Social edge count disagrees with the static WS configuration")
        if (type(self.root_ids) is not tuple
                or any(type(x) is not int or x not in range(n) for x in self.root_ids)
                or self.root_ids != tuple(sorted(set(self.root_ids)))
                or len(self.root_ids) != self.config.initial_distributors):
            raise ValueError("Initial root registry is invalid")
        if any(self.social_graph.degree(root) == 0 for root in self.root_ids):
            raise ValueError("Initial roots must not be isolated")
        participants = {a.person_id for a in self.agents
                        if a.state in (State.DISTRIBUTOR, State.INACTIVE)}
        if any(type(node) is not int for node in self.sponsor_graph):
            raise ValueError("Sponsor node IDs must be integers")
        if set(self.sponsor_graph) != participants:
            raise ValueError("Sponsor graph must contain all and only ever-enrolled participants")
        if not set(self.root_ids) <= participants:
            raise ValueError("Every initial root must remain in participant history")
        if (nx.number_of_selfloops(self.sponsor_graph)
                or not nx.is_directed_acyclic_graph(self.sponsor_graph)):
            raise ValueError("Sponsor network must be acyclic and free of self-links")
        for agent in self.agents:
            if len(agent.recent_net_income) > self.config.income_window:
                raise ValueError("Recent income exceeds the configured rolling window")
            if agent.person_id in self.root_ids:
                if (agent.sponsor_id is not None
                        or self.sponsor_graph.in_degree(agent.person_id) != 0
                        or agent.enrollment_month != 0
                        or agent.first_operating_month != 1):
                    raise ValueError("Initial roots require no sponsor and operation from month 1")
            elif agent.person_id in participants:
                sponsor = agent.sponsor_id
                if sponsor not in participants or sponsor == agent.person_id:
                    raise ValueError("A nonroot participant requires one valid sponsor")
                if set(self.sponsor_graph.predecessors(agent.person_id)) != {sponsor}:
                    raise ValueError("Sponsor metadata and graph must match exactly")
                parent = self.agents[sponsor]
                if not self.social_graph.has_edge(sponsor, agent.person_id):
                    raise ValueError("Enrollment requires a social-neighbor sponsor")
                if parent.first_operating_month > agent.enrollment_month:
                    raise ValueError("Sponsor was not operating when this person enrolled")
                if parent.exit_month is not None and parent.exit_month < agent.enrollment_month:
                    raise ValueError("Sponsor had already exited before enrollment")
            if agent.seller_id is not None:
                if (agent.seller_id not in participants
                        or agent.seller_id == agent.person_id
                        or not self.social_graph.has_edge(agent.person_id, agent.seller_id)):
                    raise ValueError("Customer seller must be a neighboring ever-participant")
            if self.month == 0:
                expected = State.DISTRIBUTOR if agent.person_id in self.root_ids else State.PROSPECT
                if (agent.state is not expected or agent.ever_customer
                        or agent.last_purchase_month is not None
                        or agent.retail_exposures != 0 or agent.recruitment_exposures != 0
                        or agent.recent_net_income or agent.cumulative_gross_earnings != 0
                        or agent.cumulative_net_cash != 0 or agent.state_since_month != 0):
                    raise ValueError("Initialization must have no commercial events or financial flows")
        if sum(self.counts().values()) != n:
            raise ValueError("Population conservation failed")

    def clone(self) -> "Population":
        self.validate()
        result = copy.deepcopy(self)
        result.validate()
        return result

    def payload(self) -> dict:
        self.validate()
        return {
            "config": self.config.to_dict(), "seed": self.seed, "month": self.month,
            "root_ids": list(self.root_ids), "agents": [a.to_dict() for a in self.agents],
            "social_edges": sorted([min(u, v), max(u, v)]
                                   for u, v in self.social_graph.edges),
            "sponsor_nodes": sorted(self.sponsor_graph.nodes),
            "sponsor_edges": sorted([u, v] for u, v in self.sponsor_graph.edges),
        }

    def to_dict(self) -> dict:
        payload = self.payload()
        return {
            "schema": SNAPSHOT_SCHEMA, "model_version": MODEL_VERSION,
            "spec_version": SPEC_VERSION, "rng_schema": RNG_SCHEMA,
            "payload": payload,
            "sha256": hashlib.sha256(canonical_json(payload).encode()).hexdigest(),
        }

    @property
    def state_hash(self) -> str:
        return self.to_dict()["sha256"]

    def save_json(self, path: str | Path) -> None:
        text = json.dumps(self.to_dict(), indent=2, sort_keys=True, allow_nan=False) + "\n"
        # Exclusive creation protects an already generated snapshot.
        with Path(path).open("x", encoding="utf-8") as stream:
            stream.write(text)

    @classmethod
    def from_dict(cls, data: dict) -> "Population":
        required = {"schema", "model_version", "spec_version", "rng_schema",
                    "payload", "sha256"}
        if not isinstance(data, dict) or set(data) != required:
            raise ValueError("Snapshot envelope has missing or unknown fields")
        # M2 population/behavior contracts are unchanged; M1 is month-zero only.
        accepted_version = data["model_version"] in (MODEL_VERSION, "0.2.0-m2") or (
            data["model_version"] == "0.1.0-m1"
            and isinstance(data.get("payload"), dict)
            and data["payload"].get("month") == 0)
        if (data["schema"] != SNAPSHOT_SCHEMA or not accepted_version
                or data["spec_version"] != SPEC_VERSION or data["rng_schema"] != RNG_SCHEMA):
            raise ValueError("Unsupported snapshot/model/randomness version")
        value = data["payload"]
        if not isinstance(value, dict) or set(value) != {
            "config", "seed", "month", "root_ids", "agents",
            "social_edges", "sponsor_nodes", "sponsor_edges"
        }:
            raise ValueError("Snapshot payload has missing or unknown fields")
        digest = hashlib.sha256(canonical_json(value).encode()).hexdigest()
        if data["sha256"] != digest:
            raise ValueError("Snapshot checksum mismatch")
        if (not isinstance(value["config"], dict)
                or set(value["config"]) != {f.name for f in fields(ModelConfig)}):
            raise ValueError("Snapshot must contain the full configuration")
        config = ModelConfig.from_dict(value["config"])
        for name in ("agents", "root_ids", "social_edges", "sponsor_nodes", "sponsor_edges"):
            if type(value[name]) is not list:
                raise ValueError(f"{name} must be a list")
        for name in ("social_edges", "sponsor_edges"):
            edges = value[name]
            for edge in edges:
                if (type(edge) is not list or len(edge) != 2
                        or any(type(x) is not int for x in edge)):
                    raise ValueError(f"Malformed edge in {name}")
            if len(set(map(tuple, edges))) != len(edges) or edges != sorted(edges):
                raise ValueError(f"{name} must contain sorted unique edges")
        if any(u >= v for u, v in value["social_edges"]):
            raise ValueError("Social edges must use canonical u < v ordering")
        nodes = value["sponsor_nodes"]
        if any(type(x) is not int for x in nodes) or nodes != sorted(set(nodes)):
            raise ValueError("Sponsor nodes must be sorted and unique")
        social = nx.Graph()
        social.add_nodes_from(range(config.population_size))
        social.add_edges_from(value["social_edges"])
        sponsor = nx.DiGraph()
        sponsor.add_nodes_from(nodes)
        sponsor.add_edges_from(value["sponsor_edges"])
        # Do not allow edge endpoints to silently add unlisted sponsor nodes.
        if set(sponsor.nodes) != set(nodes):
            raise ValueError("Sponsor edge endpoint not present in node registry")
        result = cls(config, value["seed"],
                     [Agent.from_dict(a) for a in value["agents"]],
                     social, sponsor, tuple(value["root_ids"]), value["month"])
        result.validate()
        return result

    @classmethod
    def load_json(cls, path: str | Path) -> "Population":
        return cls.from_dict(read_json(path))

    def summary(self) -> dict:
        self.validate()
        return {
            "module": "M3", "model_version": MODEL_VERSION, "month": self.month,
            "seed": self.seed, "config_hash": self.config.config_hash,
            "state_counts": self.counts(),
            "operating_distributors_current_month": len(self.operating_ids(self.month)),
            "operating_distributors_next_month": len(self.operating_ids(self.month + 1)),
            "root_ids": list(self.root_ids), "social": social_summary(self.social_graph),
            "sponsor_nodes": self.sponsor_graph.number_of_nodes(),
            "sponsor_edges": self.sponsor_graph.number_of_edges(),
            "state_hash": self.state_hash,
            "monthly_simulation_implemented": True,
        }


def initialize_population(config: ModelConfig, seed: int) -> Population:
    if not isinstance(config, ModelConfig):
        raise ValueError("config must be a ModelConfig")
    rng = EventRandom(seed)
    graph = generate_social_graph(config, rng)
    roots = select_roots(graph, config.initial_distributors, rng)
    root_set = set(roots)
    people = []
    for person_id in range(config.population_size):
        attributes = [
            0.5 if config.homogeneous_agents else rng.beta(
                process, person_id, config.heterogeneity_alpha, config.heterogeneity_beta)
            for process in (Process.PRODUCT_FIT, Process.SELLING_SKILL, Process.RECRUITING_SKILL)
        ]
        root = person_id in root_set
        people.append(Agent(
            person_id, State.DISTRIBUTOR if root else State.PROSPECT, *attributes,
            enrollment_month=0 if root else None,
            first_operating_month=1 if root else None))
    population = Population(config, seed, people, graph,
                            initialize_sponsor_graph(roots), roots)
    population.validate()
    return population
