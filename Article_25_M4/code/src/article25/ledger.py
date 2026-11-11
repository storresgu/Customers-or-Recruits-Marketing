"""Exclusive purchase categories and monthly event context."""
from dataclasses import asdict, dataclass, field
from enum import Enum
from collections import Counter
from .agents import State, require_transition
from .config import require_int


class Category(str, Enum):
    EXTERNAL_FIRST = "external_first"
    EXTERNAL_REACQUISITION = "external_reacquisition"
    EXTERNAL_REPEAT = "external_repeat"
    PARTICIPANT_PERSONAL = "participant_personal"
    PARTICIPANT_ENTRY = "participant_entry"
    PARTICIPANT_QUALIFICATION = "participant_qualification"


EXTERNAL = frozenset({Category.EXTERNAL_FIRST, Category.EXTERNAL_REACQUISITION,
                      Category.EXTERNAL_REPEAT})


@dataclass(frozen=True, slots=True)
class Transaction:
    month: int
    buyer_id: int
    distributor_id: int
    category: Category
    units: int
    unit_price: float
    buyer_state: str
    new_entrant_purchase: bool

    def to_dict(self):
        row = asdict(self)
        row["category"] = self.category.value
        return row


@dataclass
class MonthContext:
    population: object
    month: int
    operating: tuple[int, ...]
    customers_start: tuple[int, ...]
    counts_start: dict
    multiplier: float
    contacted: dict[int, set[int]] = field(default_factory=dict)
    new_customers: set[int] = field(default_factory=set)
    entrants: set[int] = field(default_factory=set)
    unserved: set[int] = field(default_factory=set)
    repeat_eligible: list[int] = field(default_factory=list)
    transactions: list[Transaction] = field(default_factory=list)
    events: list[dict] = field(default_factory=list)
    flows: Counter = field(default_factory=Counter)
    contact_counts: Counter = field(default_factory=Counter)
    buyers: set[int] = field(default_factory=set)
    earnings: list[dict] = field(default_factory=list)

    @property
    def config(self):
        return self.population.config

    @property
    def rng(self):
        return self.population.random

    def event(self, event: str, actor: int, target: int | None = None, **data):
        self.events.append({"month": self.month, "event": event, "actor": actor,
                            "target": target, **data})

    def transition(self, person, target: State):
        require_transition(person.state, target)
        self.flows[person.state.value + target.value] += 1
        person.state = target
        person.state_since_month = self.month

    def purchase(self, buyer_id: int, distributor_id: int, category: Category, units: int = 1):
        require_int("purchase units", units, 1)
        if buyer_id in self.buyers:
            raise ValueError("A person cannot purchase twice during the same month")
        buyer = self.population.agents[buyer_id]
        if category in EXTERNAL:
            if buyer.state not in (State.PROSPECT, State.CUSTOMER):
                raise ValueError("External purchases must originate from nonparticipants")
            if distributor_id not in self.operating:
                raise ValueError("External sale requires an operating distributor")
            price, entrant = self.config.retail_price, False
        else:
            if category is Category.PARTICIPANT_QUALIFICATION:
                raise ValueError("Qualification purchasing remains disabled")
            if buyer.state is not State.DISTRIBUTOR or buyer_id != distributor_id:
                raise ValueError("Participant purchase requires a distributor buyer")
            price = self.config.wholesale_price
            # Seed roots' first commercial month is 1 despite their month-0 stamp.
            start = max(1, buyer.enrollment_month)
            entrant = 0 <= self.month - start < self.config.new_entrant_window
        transaction = Transaction(self.month, buyer_id, distributor_id, category,
                                  units, price, buyer.state.value, entrant)
        self.transactions.append(transaction)
        self.buyers.add(buyer_id)
        buyer.last_purchase_month = self.month

    def verify_flows(self):
        before, end, f = self.counts_start, self.population.counts(), self.flows
        expected = {
            "U": before["U"] - f["UC"] - f["UD"] + f["CU"],
            "C": before["C"] + f["UC"] - f["CD"] - f["CU"],
            "D": before["D"] + f["UD"] + f["CD"] - f["DI"],
            "I": before["I"] + f["DI"],
        }
        if end != expected or sum(end.values()) != self.config.population_size:
            raise ValueError("Monthly population stock-flow reconciliation failed")
        if len(self.buyers) != len(self.transactions):
            raise ValueError("Duplicate transaction buyers")
        if self.month >= self.config.shock_start_month and self.multiplier == 0 and self.entrants:
            raise ValueError("Enrollment occurred under a complete recruitment interruption")
