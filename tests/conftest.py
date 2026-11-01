"""Only an explicit flag may enable paid/networked live smoke tests."""

import pytest


def pytest_addoption(parser):
    parser.addoption("--run-live", action="store_true", default=False,
                     help="Enable real API smoke tests; requires locally configured credentials")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-live"):
        for item in items:
            if "live" in item.keywords:
                item.add_marker(pytest.mark.skip(reason="real API smoke requires --run-live"))
