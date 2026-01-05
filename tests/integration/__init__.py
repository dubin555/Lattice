"""
Integration tests for lattice.

These tests require a running Lattice server at localhost:8000.
Run with: pytest tests/integration/ -v -m integration
"""
import pytest

pytest.register_marker = lambda *args, **kwargs: None
