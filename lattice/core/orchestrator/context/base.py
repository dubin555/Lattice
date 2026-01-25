"""
Base context class for workflow/task execution tracking.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any


class BaseContext(ABC):
    """Base class for workflow/task execution contexts."""

    @abstractmethod
    async def on_task_finished(self, msg_data: Dict[str, Any]) -> None:
        """Handle task completion."""
        pass

    @abstractmethod
    async def on_task_started(self, msg_data: Dict[str, Any]) -> None:
        """Handle task start notification."""
        pass

    @abstractmethod
    async def on_task_exception(self, msg_data: Dict[str, Any]) -> None:
        """Handle task exception."""
        pass
