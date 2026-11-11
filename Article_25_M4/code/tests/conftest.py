import pytest
from article25 import ModelConfig, initialize_population


@pytest.fixture
def config():
    return ModelConfig(population_size=60, social_degree=6, initial_distributors=3)


@pytest.fixture
def population(config):
    return initialize_population(config, seed=1701)

