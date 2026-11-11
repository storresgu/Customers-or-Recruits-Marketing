"""State and attribute contracts; stochastic commercial transitions belong to M2."""
from dataclasses import asdict, dataclass, field, fields
from enum import Enum
from .config import require_int, require_number


class State(str, Enum):
    PROSPECT = "U"
    CUSTOMER = "C"
    DISTRIBUTOR = "D"
    INACTIVE = "I"


ALLOWED_TRANSITIONS = frozenset({
    (State.PROSPECT, State.CUSTOMER),
    (State.PROSPECT, State.DISTRIBUTOR),
    (State.CUSTOMER, State.PROSPECT),
    (State.CUSTOMER, State.DISTRIBUTOR),
    (State.DISTRIBUTOR, State.INACTIVE),
})


def require_transition(source: State, target: State) -> None:
    """Check a transition contract; deliberately does not mutate an agent."""
    if not isinstance(source, State) or not isinstance(target, State):
        raise ValueError("Both states must be State values")
    if (source, target) not in ALLOWED_TRANSITIONS:
        raise ValueError(f"Transition {source.value} -> {target.value} is not permitted")


@dataclass(slots=True)
class Agent:
    person_id: int
    state: State
    product_fit: float
    selling_skill: float
    recruiting_skill: float
    sponsor_id: int | None = None
    seller_id: int | None = None
    enrollment_month: int | None = None
    first_operating_month: int | None = None
    last_purchase_month: int | None = None
    ever_customer: bool = False
    retail_exposures: int = 0
    recruitment_exposures: int = 0
    recent_net_income: list[float] = field(default_factory=list)
    cumulative_gross_earnings: float = 0.0
    cumulative_net_cash: float = 0.0
    exit_month: int | None = None
    customer_since_month: int | None = None
    state_since_month: int = 0

    def validate(self, month: int) -> None:
        require_int("month", month)
        require_int("person_id", self.person_id)
        if not isinstance(self.state, State):
            raise ValueError("Agent state must be a State enum")
        for name in ("product_fit", "selling_skill", "recruiting_skill"):
            require_number(name, getattr(self, name), maximum=1)
        for name in ("sponsor_id", "seller_id"):
            value = getattr(self, name)
            if value is not None:
                require_int(name, value)
        for name in ("retail_exposures", "recruitment_exposures", "state_since_month"):
            require_int(name, getattr(self, name))
        if self.state_since_month > month:
            raise ValueError("state_since_month is in the future")
        for name in ("enrollment_month", "last_purchase_month", "exit_month",
                     "customer_since_month"):
            value = getattr(self, name)
            if value is not None:
                require_int(name, value)
                if value > month:
                    raise ValueError(f"{name} is in the future")
        if self.first_operating_month is not None:
            require_int("first_operating_month", self.first_operating_month, 1)
            if self.enrollment_month is None or (
                self.first_operating_month != self.enrollment_month + 1
            ):
                raise ValueError("First operation must follow enrollment by one month")
        if type(self.ever_customer) is not bool:
            raise ValueError("ever_customer must be boolean")
        require_number("cumulative_gross_earnings", self.cumulative_gross_earnings)
        require_number("cumulative_net_cash", self.cumulative_net_cash, -float("inf"))
        if type(self.recent_net_income) is not list:
            raise ValueError("recent_net_income must be a list")
        for value in self.recent_net_income:
            require_number("recent_net_income value", value, -float("inf"))
        participant = self.state in (State.DISTRIBUTOR, State.INACTIVE)
        if participant:
            if self.enrollment_month is None or self.first_operating_month is None:
                raise ValueError("Participants need enrollment and activation dates")
        elif any(x is not None for x in
                 (self.sponsor_id, self.enrollment_month, self.first_operating_month)):
            raise ValueError("Nonparticipants cannot have participant metadata")
        if self.state is State.INACTIVE:
            if self.exit_month is None or self.exit_month < self.first_operating_month:
                raise ValueError("Inactive participants need a valid exit month")
        elif self.exit_month is not None:
            raise ValueError("Only inactive participants have an exit month")
        if self.state is State.CUSTOMER:
            if not self.ever_customer or self.customer_since_month is None:
                raise ValueError("Customers need relationship history")
            if self.last_purchase_month is None or (
                self.last_purchase_month < self.customer_since_month
            ):
                raise ValueError("Customer episode requires an acquisition purchase")
        elif self.seller_id is not None or self.customer_since_month is not None:
            raise ValueError("Only current customers can have a current seller relationship")

    def can_operate(self, month: int) -> bool:
        require_int("month", month)
        return (self.state is State.DISTRIBUTOR
                and self.first_operating_month is not None
                and self.first_operating_month <= month)

    def to_dict(self) -> dict:
        result = asdict(self)
        result["state"] = self.state.value
        return result

    @classmethod
    def from_dict(cls, data: dict) -> "Agent":
        if not isinstance(data, dict) or set(data) != {f.name for f in fields(cls)}:
            raise ValueError("Agent snapshot has missing or unknown fields")
        values = dict(data)
        try:
            values["state"] = State(values["state"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Unknown agent state") from exc
        return cls(**values)

