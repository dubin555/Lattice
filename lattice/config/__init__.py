"""
Configuration module for Lattice.
"""
from lattice.config.logging import setup_logging
from lattice.config.batch import BatchConfig

__all__ = ["setup_logging", "BatchConfig"]
