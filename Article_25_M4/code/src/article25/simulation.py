"""Atomic monthly schedule, complete audit traces and restartable checkpoints."""
import copy
import hashlib
import json
from pathlib import Path
from . import MODEL_VERSION
from .agents import State
from .config import canonical_json, read_json, require_int
from .model import Population, initialize_population
from .ledger import MonthContext
from .demand import resolve_sellers, retail_contacts, repurchases, customer_exits
from .recruitment import recruitment_contacts, participant_purchases, distributor_exits
from .accounting import settle_month
from .metrics import summarize_month

SIMULATION_SCHEMA = "article25-simulation-v1"


def graph_hash(population):
    edges = sorted([min(u,v), max(u,v)] for u,v in population.social_graph.edges)
    return hashlib.sha256(canonical_json(edges).encode()).hexdigest()


class Simulation:
    def __init__(self, population: Population):
        self.population = population.clone()
        self.start_month = population.month
        self.social_hash = graph_hash(population)
        self.monthly = []
        self.events = []
        self.transactions = []
        self.earnings = []

    @classmethod
    def initialize(cls, config, seed):
        return cls(initialize_population(config, seed))

    def validate(self):
        self.population.validate()
        require_int("start_month", self.start_month)
        if self.start_month > self.population.month:
            raise ValueError("Checkpoint start month is after its current month")
        if graph_hash(self.population) != self.social_hash:
            raise ValueError("The social graph must remain static")
        if [row["month"] for row in self.monthly] != list(range(self.start_month+1, self.population.month+1)):
            raise ValueError("Monthly history is incomplete or duplicated")
        for records in (self.events, self.transactions, self.earnings):
            if any(type(r) is not dict or not self.start_month < r.get("month", -1) <= self.population.month
                   for r in records):
                raise ValueError("Audit record month is outside checkpoint history")
        for field in (self.monthly, self.events, self.transactions, self.earnings):
            canonical_json(field)  # Reject nonfinite numbers and non-JSON objects.

    def step(self):
        # Copy-on-step: on a failure no partial month is committed.
        self.population.validate()
        if graph_hash(self.population) != self.social_hash:
            raise ValueError("The social graph must remain static")
        p = self.population.clone()
        t = p.month + 1
        if t > p.config.horizon_months:
            raise ValueError("Cannot step beyond the configured horizon")
        operating = p.operating_ids(t)
        customers = tuple(a.person_id for a in p.agents if a.state is State.CUSTOMER)
        multiplier = p.config.recruitment_multiplier if t >= p.config.shock_start_month else 1.0
        ctx = MonthContext(p, t, operating, customers, p.counts(), multiplier)
        p.month = t
        resolve_sellers(ctx)
        retail_contacts(ctx)
        recruitment_contacts(ctx)
        repurchases(ctx)
        participant_purchases(ctx)
        settle_month(ctx)
        customer_exits(ctx)
        distributor_exits(ctx)
        p.validate()
        row = summarize_month(ctx)
        self.population = p
        self.monthly.append(row)
        self.events.extend(ctx.events)
        self.transactions.extend(tx.to_dict() for tx in ctx.transactions)
        self.earnings.extend(ctx.earnings)
        return copy.deepcopy(row)

    def run(self, through_month: int | None = None):
        target = self.population.config.horizon_months if through_month is None else through_month
        require_int("through_month", target)
        if target < self.population.month or target > self.population.config.horizon_months:
            raise ValueError("Requested end month is outside the remaining horizon")
        while self.population.month < target:
            self.step()
        return self

    def clone(self):
        self.validate()
        return copy.deepcopy(self)

    def to_dict(self):
        self.validate()
        payload = {
            "population": self.population.to_dict(), "start_month": self.start_month,
            "social_hash": self.social_hash, "monthly": self.monthly,
            "events": self.events, "transactions": self.transactions, "earnings": self.earnings}
        # Detach returned containers so callers cannot mutate the running model.
        payload = copy.deepcopy(payload)
        return {"schema": SIMULATION_SCHEMA, "model_version": MODEL_VERSION, "payload": payload,
                "sha256": hashlib.sha256(canonical_json(payload).encode()).hexdigest()}

    @classmethod
    def from_dict(cls, data):
        if (not isinstance(data, dict) or set(data) != {"schema","model_version","payload","sha256"}
                or data["schema"] != SIMULATION_SCHEMA
                or data["model_version"] not in (MODEL_VERSION, "0.2.0-m2")):
            raise ValueError("Unsupported simulation checkpoint")
        payload = data["payload"]
        if (not isinstance(payload,dict) or set(payload) != {
            "population","start_month","social_hash","monthly","events","transactions","earnings"}):
            raise ValueError("Incomplete simulation checkpoint")
        if hashlib.sha256(canonical_json(payload).encode()).hexdigest() != data["sha256"]:
            raise ValueError("Simulation checkpoint checksum mismatch")
        simulation = cls(Population.from_dict(payload["population"]))
        for key in ("start_month","social_hash","monthly","events","transactions","earnings"):
            setattr(simulation, key, copy.deepcopy(payload[key]))
        simulation.validate()
        return simulation

    def save_json(self, path):
        data = self.to_dict()
        with Path(path).open("x", encoding="utf-8") as stream:
            json.dump(data, stream, indent=2, sort_keys=True, allow_nan=False)
            stream.write("\n")

    @classmethod
    def load_json(cls, path):
        return cls.from_dict(read_json(path))
