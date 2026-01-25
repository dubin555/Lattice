"""
Task reference parsing utilities.

Provides structured parsing of task output references to avoid issues
with task_ids that contain dots.
"""
from dataclasses import dataclass
from typing import Optional


@dataclass
class TaskReference:
    """Represents a reference to a task output.

    Format: "{task_id}.output.{output_key}"
    The separator ".output." is used to reliably split task_id and output_key,
    even when task_id contains dots.
    """

    task_id: str
    output_key: str

    SEPARATOR = ".output."

    def to_string(self) -> str:
        """Convert to reference string format."""
        return f"{self.task_id}{self.SEPARATOR}{self.output_key}"

    @classmethod
    def from_string(cls, ref: str) -> Optional["TaskReference"]:
        """Parse a reference string.

        Returns None if the string is not a valid task reference.
        """
        if cls.SEPARATOR not in ref:
            return None

        idx = ref.find(cls.SEPARATOR)
        task_id = ref[:idx]
        output_key = ref[idx + len(cls.SEPARATOR) :]

        if not task_id or not output_key:
            return None

        return cls(task_id=task_id, output_key=output_key)

    @classmethod
    def is_valid_reference(cls, ref: str) -> bool:
        """Check if a string is a valid task reference."""
        return cls.from_string(ref) is not None
