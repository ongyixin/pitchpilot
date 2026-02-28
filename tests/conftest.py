"""
Shared pytest configuration and fixtures.

Ensures PITCHPILOT_MOCK_MODE=true for all tests so no model backends are needed.
"""

import os

import pytest


def pytest_configure(config):
    """Force mock mode for the entire test session."""
    os.environ["PITCHPILOT_MOCK_MODE"] = "true"
