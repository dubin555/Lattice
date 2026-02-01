# Testing Reference

## Test Structure

```
tests/
├── unit/              # No server required
│   ├── core/          # Core module tests
│   ├── client/        # Client SDK tests
│   └── executor/      # Executor tests
└── integration/       # Requires running server
```

## Running Tests

```bash
# All unit tests
pytest tests/unit/ -v

# Specific test file
pytest tests/unit/core/test_scheduler.py -v

# Specific test method
pytest tests/unit/client/test_client.py::TestClassName::test_method -v -s

# With coverage
pytest tests/unit/ --cov=lattice --cov-report=html

# Integration tests (start server first)
lattice start --head --port 8000 &
pytest tests/integration/ -v
```

## Test Patterns

### Mocking the Orchestrator
```python
from unittest.mock import MagicMock, patch

@patch('lattice.api.routes.workflow.get_orchestrator')
def test_workflow_endpoint(mock_get_orch):
    mock_orch = MagicMock()
    mock_get_orch.return_value = mock_orch
    # ...
```

### Async Tests
```python
import asyncio

def test_async_function(self):
    loop = asyncio.get_event_loop()
    result = loop.run_until_complete(async_function())
    assert result == expected
```

### Testing with MessageBus
```python
from lattice.core.scheduler.message_bus import MessageBus, Message, MessageType

def test_message_flow():
    bus = MessageBus()
    msg = Message(MessageType.RUN_TASK, {"task_id": "task-1"})
    bus.send_to_scheduler(msg)
    received = bus.receive_in_scheduler(timeout=1.0)
    assert received.message_type == MessageType.RUN_TASK
```

## Pre-commit Checks

Before each commit, these checks run automatically:
1. **ruff** - Code quality (warnings only)
2. **pytest tests/unit/** - All unit tests must pass
3. **commit-msg** - Validates Conventional Commits format
