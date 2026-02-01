# CLAUDE.md

Lattice: Task-level distributed framework for LLM agents. Enables LangGraph workflows to automatically gain task-level parallelism.

## Quick Commands

```bash
pip install -e .                              # Install
lattice start --head --port 8000              # Start server
pytest tests/unit/ -v                         # Run unit tests
```

## Architecture

```
Client (LatticeClient/LangGraphClient)
    ↓ HTTP/WebSocket
API Layer (FastAPI)
    ↓
Orchestrator (main thread) ←→ Scheduler (background thread)
    ↓ MessageBus (Queue)
Executor (Ray/Local)
    ↓
Workers [Sandbox]
```

## Core Concepts

| Concept | Location | Description |
|---------|----------|-------------|
| Task | `lattice/core/workflow/base.py` | Minimal execution unit with DAG dependencies |
| Orchestrator | `lattice/core/orchestrator/` | Workflow lifecycle, runs in main thread |
| Scheduler | `lattice/core/scheduler/` | Task dispatch, runs in background thread |
| Executor | `lattice/executor/` | Ray/Local execution backends |

## Key Design Decisions

1. **Thread Model**: Orchestrator (main/async) + Scheduler (background) via Queue - avoids blocking FastAPI
2. **Pluggable Executors**: Abstract `ExecutorBackend` for Ray/Local/future backends
3. **Multi-level Sandbox**: NONE → SUBPROCESS → SECCOMP → DOCKER

## Detailed Documentation

For detailed module documentation, read files in `.claude/docs/`:
- `.claude/docs/modules.md` - Module structure and key classes
- `.claude/docs/message-flow.md` - Request lifecycle and message flow
- `.claude/docs/testing.md` - Testing guidelines

## Git Workflow

- **Branch**: `feature/`, `fix/`, `refactor/`, `docs/`
- **Commits**: Conventional Commits format (`feat:`, `fix:`, `refactor:`, etc.)
- **Pre-commit**: ruff + pytest + commit message validation
