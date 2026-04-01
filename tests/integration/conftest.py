# -*- coding: utf-8 -*-
"""pytest configuration for integration tests."""

import os
import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "integration: integration test requiring network or real tools (skip without AGENT_REACH_INTEGRATION=1)"
    )


def pytest_collection_modifyitems(config, items):
    """Skip all integration tests unless AGENT_REACH_INTEGRATION is set."""
    integration_mode = os.environ.get("AGENT_REACH_INTEGRATION", "")

    for item in items:
        if "integration" in item.keywords:
            if not integration_mode:
                item.add_marker(
                    pytest.mark.skip(
                        reason="Integration tests skipped. "
                               "Set AGENT_REACH_INTEGRATION=1 to run. "
                               "For live tests: AGENT_REACH_INTEGRATION=live"
                    )
                )
