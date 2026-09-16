"""Pytest configuration ensuring deterministic offline mock LLM provider during test runs."""

import os

# Ensure tests run with deterministic mock provider for speed (< 1s) and reproducibility
os.environ["LLM_PROVIDER"] = "mock"
