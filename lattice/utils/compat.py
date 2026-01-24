"""
Compatibility utilities for handling legacy field names.
"""
from typing import Any, Dict, Optional


def get_serialized_code(data: Dict[str, Any], default: Optional[str] = None) -> Optional[str]:
    """Get serialized_code with legacy code_ser fallback.

    Args:
        data: Dictionary that may contain serialized_code or code_ser
        default: Default value to return if neither key is present

    Returns:
        The serialized code value, or default if not found
    """
    return data.get("serialized_code") or data.get("code_ser") or default
