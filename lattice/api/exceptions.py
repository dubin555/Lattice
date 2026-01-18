"""
Unified exception handling for API routes.

This module provides a decorator that handles exceptions consistently across all
API route handlers, mapping Lattice exceptions to appropriate HTTP status codes.
"""
import functools
from typing import Callable, TypeVar

from fastapi import HTTPException

from lattice.exceptions import (
    LatticeError,
    ClientError,
    ServerError,
    ExecutorError,
    ValidationError,
    WorkflowNotFoundError,
    TaskNotFoundError,
    OrchestratorNotInitializedError,
    TaskExecutionError,
    TaskCancelledError,
    NodeFailedError,
    CyclicDependencyError,
)

F = TypeVar("F", bound=Callable)


def handle_route_exceptions(func: F) -> F:
    """
    Decorator that provides unified exception handling for API route handlers.

    Maps Lattice exceptions to appropriate HTTP status codes:
    - 404: WorkflowNotFoundError, TaskNotFoundError (resource not found)
    - 400: ValidationError, CyclicDependencyError (bad request / invalid input)
    - 503: OrchestratorNotInitializedError (service unavailable)
    - 500: All other exceptions (internal server error)

    HTTPException instances are re-raised as-is to preserve custom status codes
    set within route handlers (e.g., for specific validation errors).

    Usage:
        @router.post("/my_endpoint")
        @handle_route_exceptions
        async def my_endpoint():
            ...

    Args:
        func: The async route handler function to wrap.

    Returns:
        The wrapped function with exception handling.
    """
    @functools.wraps(func)
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except (WorkflowNotFoundError, TaskNotFoundError) as e:
            # Resource not found errors
            raise HTTPException(status_code=404, detail=str(e))
        except OrchestratorNotInitializedError as e:
            # Service not ready / unavailable
            raise HTTPException(status_code=503, detail=str(e))
        except (ValidationError, CyclicDependencyError) as e:
            # Client-side validation errors
            raise HTTPException(status_code=400, detail=str(e))
        except (TaskExecutionError, TaskCancelledError, NodeFailedError) as e:
            # Executor errors - treated as internal server errors
            raise HTTPException(status_code=500, detail=str(e))
        except HTTPException:
            # Re-raise HTTPExceptions as-is (preserve custom status codes)
            raise
        except Exception as e:
            # Catch-all for unexpected errors
            raise HTTPException(status_code=500, detail=str(e))

    return wrapper
