"""
Lattice API module.
"""

def __getattr__(name):
    if name in ("app", "create_app", "get_orchestrator"):
        from lattice.api.server import app, create_app, get_orchestrator
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = ["app", "create_app", "get_orchestrator"]
