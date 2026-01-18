"""
Unified code execution utilities for Lattice.

This module provides centralized functions for:
- Deserializing cloudpickle-serialized functions
- Executing serialized functions with arguments
- Executing code strings via AST parsing

These utilities are used by:
- lattice/executor/runner.py
- lattice/core/scheduler/scheduler.py

Note: The embedded scripts in sandbox.py (RUNNER_TEMPLATE, DOCKER_RUNNER_SCRIPT)
contain similar logic but must remain self-contained since they run in isolated
environments. Those scripts are derived from the logic defined here.
"""
import ast
import base64
from typing import Any, Callable, Dict, Optional

import cloudpickle


def deserialize_function(serialized_code: str) -> Callable:
    """
    Deserialize a base64-encoded cloudpickle function.

    Args:
        serialized_code: Base64-encoded cloudpickle serialized function.

    Returns:
        The deserialized callable function.

    Raises:
        ValueError: If deserialization fails.
    """
    try:
        return cloudpickle.loads(base64.b64decode(serialized_code))
    except Exception as e:
        raise ValueError(f"Failed to deserialize function: {e}") from e


def execute_serialized(serialized_code: str, *args, **kwargs) -> Any:
    """
    Deserialize and execute a cloudpickle-serialized function.

    Args:
        serialized_code: Base64-encoded cloudpickle serialized function.
        *args: Positional arguments to pass to the function.
        **kwargs: Keyword arguments to pass to the function.

    Returns:
        The result of executing the function.
    """
    func = deserialize_function(serialized_code)
    return func(*args, **kwargs)


def execute_serialized_with_serialized_args(
    serialized_code: str,
    serialized_args: str,
    serialized_kwargs: str,
) -> Any:
    """
    Deserialize and execute a function with serialized arguments.

    This is used for LangGraph tasks where both the function and its
    arguments are serialized.

    Args:
        serialized_code: Base64-encoded cloudpickle serialized function.
        serialized_args: Base64-encoded cloudpickle serialized args tuple.
        serialized_kwargs: Base64-encoded cloudpickle serialized kwargs dict.

    Returns:
        The result of executing the function.
    """
    func = deserialize_function(serialized_code)
    args = cloudpickle.loads(base64.b64decode(serialized_args))
    kwargs = cloudpickle.loads(base64.b64decode(serialized_kwargs))
    return func(*args, **kwargs)


def execute_code_string(code_str: str, task_input_data: Dict[str, Any]) -> Any:
    """
    Execute a code string containing a function definition via AST parsing.

    The code string should contain a function definition. The function will
    be extracted, compiled, and executed with the provided input data.

    Args:
        code_str: Python code string containing a function definition.
        task_input_data: Dictionary of input data to pass to the function.

    Returns:
        The result of executing the function with the input data.

    Raises:
        ValueError: If no function definition is found in the code.
    """
    tree = ast.parse(code_str)

    func_node = None
    import_nodes = []

    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            func_node = node
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            import_nodes.append(node)

    if func_node is None:
        raise ValueError("No function definition found in code")

    # Build namespace with imports
    namespace: Dict[str, Any] = {}
    for imp in import_nodes:
        module = ast.Module(body=[imp], type_ignores=[])
        exec(compile(module, '<string>', 'exec'), namespace)

    # Compile and execute function definition
    module = ast.Module(body=[func_node], type_ignores=[])
    exec(compile(module, '<string>', 'exec'), namespace)

    # Call the function with input data
    return namespace[func_node.name](task_input_data)


def execute_task(
    code_str: Optional[str] = None,
    serialized_code: Optional[str] = None,
    task_input_data: Optional[Dict[str, Any]] = None,
) -> Any:
    """
    Execute a task using either serialized code or a code string.

    This is the main entry point for task execution, handling both
    cloudpickle-serialized functions and AST-based code string execution.

    Args:
        code_str: Python code string containing a function definition.
        serialized_code: Base64-encoded cloudpickle serialized function.
        task_input_data: Dictionary of input data to pass to the function.

    Returns:
        The result of executing the task.

    Raises:
        ValueError: If neither code_str nor serialized_code is provided.
    """
    task_input_data = task_input_data or {}

    if serialized_code is not None:
        return execute_serialized(serialized_code, task_input_data)
    elif code_str is not None:
        return execute_code_string(code_str, task_input_data)
    else:
        raise ValueError("Either code_str or serialized_code must be provided")
