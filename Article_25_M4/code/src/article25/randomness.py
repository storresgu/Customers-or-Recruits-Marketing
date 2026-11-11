"""Versioned event-keyed randomness, independent of branch and draw order.

SHA-256 keys produce a uniform value from their most significant 53 bits.
PCG64 is used only for seeded initialization distributions. This is research
randomness, not an encryption or security interface.
"""
from dataclasses import dataclass
from enum import Enum
import hashlib
import numpy as np
from .config import canonical_json, require_int, require_number

RNG_SCHEMA = "article25-event-rng-v1"


class Process(str, Enum):
    NETWORK = "init_network"
    ROOTS = "init_roots"
    PRODUCT_FIT = "init_product_fit"
    SELLING_SKILL = "init_selling_skill"
    RECRUITING_SKILL = "init_recruiting_skill"
    RETAIL_ORDER = "retail_order"
    RECRUITMENT_ORDER = "recruitment_order"
    RETAIL_TARGET = "retail_target"
    RECRUITMENT_TARGET = "recruitment_target"
    RETAIL_CONVERSION = "retail_conversion"
    RECRUITMENT_CONVERSION = "recruitment_conversion"
    REPURCHASE = "repurchase"
    PERSONAL_PURCHASE = "personal_purchase"
    CUSTOMER_EXIT = "customer_exit"
    DISTRIBUTOR_EXIT = "distributor_exit"
    SELLER_REASSIGNMENT = "seller_reassignment"


@dataclass(frozen=True, slots=True)
class EventRandom:
    seed: int

    def __post_init__(self):
        require_int("seed", self.seed)

    def key_digest(self, process: Process, month: int = 0, person_id: int = 0,
                   partner_id: int | None = None, opportunity_index: int = 0) -> bytes:
        if not isinstance(process, Process):
            raise ValueError("process must be a registered Process")
        for name, value in (("month", month), ("person_id", person_id),
                            ("opportunity_index", opportunity_index)):
            require_int(name, value)
        if partner_id is not None:
            require_int("partner_id", partner_id)
        key = [RNG_SCHEMA, self.seed, process.value, month, person_id,
               partner_id, opportunity_index]
        return hashlib.sha256(canonical_json(key).encode("utf-8")).digest()

    def seed_for(self, process: Process) -> int:
        return int.from_bytes(self.key_digest(process), "big")

    def uniform(self, process: Process, month: int, person_id: int,
                partner_id: int | None = None, opportunity_index: int = 0) -> float:
        value = int.from_bytes(self.key_digest(process, month, person_id,
                                              partner_id, opportunity_index), "big")
        return (value >> 203) / (1 << 53)

    def beta(self, process: Process, person_id: int, alpha: float, beta: float) -> float:
        require_number("alpha", alpha, strict_min=True)
        require_number("beta", beta, strict_min=True)
        key_seed = int.from_bytes(self.key_digest(process, person_id=person_id), "big")
        generator = np.random.Generator(np.random.PCG64(key_seed))
        return float(generator.beta(alpha, beta))

    def rank(self, candidates, process: Process, month: int = 0,
             person_id: int = 0, opportunity_index: int = 0) -> list[int]:
        self.key_digest(process, month, person_id, opportunity_index=opportunity_index)
        candidates = list(candidates)
        for person in candidates:
            require_int("candidate", person)
        if len(candidates) != len(set(candidates)):
            raise ValueError("Candidates must be unique")
        return sorted(candidates, key=lambda candidate: (
            self.key_digest(process, month, person_id, candidate, opportunity_index),
            candidate))
