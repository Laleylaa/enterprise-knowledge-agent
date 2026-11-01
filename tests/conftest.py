"""Only an explicit flag may enable paid/networked live smoke tests."""

import pytest

pytest_plugins = ["tests.support.retrieval", "tests.support.artifacts"]


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Enable real API smoke tests; requires locally configured credentials")
    parser.addoption("--examples-dir", default=None,
                     help="Export registered actual test runs by scope into inputs/outputs/traces/reports")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        for item in items:
            if "live" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="real API smoke requires --run-live"))
