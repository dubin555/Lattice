"""
pytest configuration for lattice tests.
"""
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires running server)"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("-m") and "integration" in config.getoption("-m"):
        return
    
    skip_integration = pytest.mark.skip(reason="use -m integration to run integration tests")
    for item in items:
        if "integration" in item.keywords:
            item.add_marker(skip_integration)
