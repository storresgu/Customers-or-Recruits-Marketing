"""Article 25: population foundation and monthly commercial dynamics."""

MODEL_VERSION = "0.3.0-m3"
SPEC_VERSION = "0.1"

from .config import ModelConfig
from .model import Population, initialize_population

__all__ = ["MODEL_VERSION", "SPEC_VERSION", "ModelConfig", "Population",
           "initialize_population"]
