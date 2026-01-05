"""
Scheduler module for Lattice task orchestration.
"""
from lattice.core.scheduler.message_bus import (
    Message,
    MessageType,
    MessageBus,
)

def __getattr__(name):
    if name in ("Scheduler", "run_scheduler_process"):
        from lattice.core.scheduler.scheduler import Scheduler, run_scheduler_process
        return locals()[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "Message",
    "MessageType",
    "MessageBus",
    "Scheduler",
    "run_scheduler_process",
]
