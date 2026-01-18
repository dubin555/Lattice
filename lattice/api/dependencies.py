"""
Shared dependencies for API routes.

This module provides a unified orchestrator access pattern used by all route modules.
"""
from typing import Optional

from lattice.exceptions import OrchestratorNotInitializedError

_orchestrator: Optional["Orchestrator"] = None


def set_orchestrator(orchestrator: "Orchestrator") -> None:
    """
    Set the global orchestrator instance.

    This should be called once during application startup from server.py.

    Args:
        orchestrator: The Orchestrator instance to use globally.
    """
    global _orchestrator
    _orchestrator = orchestrator


def get_orchestrator() -> "Orchestrator":
    """
    Get the global orchestrator instance.

    Returns:
        The global Orchestrator instance.

    Raises:
        OrchestratorNotInitializedError: If the orchestrator has not been set.
    """
    if _orchestrator is None:
        raise OrchestratorNotInitializedError()
    return _orchestrator
