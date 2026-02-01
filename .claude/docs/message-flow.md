# Message Flow Reference

## Complete Request Lifecycle

```
1. User calls workflow.run()
2. API calls Orchestrator.run_workflow()
3. Orchestrator creates RunContext, sends RUN_TASK for start tasks
4. Scheduler receives RUN_TASK, selects node, submits to Executor
5. Scheduler sends START_TASK back to Orchestrator
6. Worker executes task, returns result
7. Scheduler detects completion, sends FINISH_TASK to Orchestrator
8. RunContext.on_task_finished() triggers downstream tasks (back to step 3)
9. When all tasks done, results returned via WebSocket
```

## Message Types

| Type | Direction | Purpose |
|------|-----------|---------|
| `RUN_TASK` | Orchestrator → Scheduler | Submit task for execution |
| `START_TASK` | Scheduler → Orchestrator | Task started running |
| `FINISH_TASK` | Scheduler → Orchestrator | Task completed |
| `TASK_EXCEPTION` | Scheduler → Orchestrator | Task failed with error |
| `STOP_WORKFLOW` | Orchestrator → Scheduler | Cancel workflow |
| `FINISH_WORKFLOW` | Scheduler → Orchestrator | All tasks complete |
| `SHUTDOWN` | Orchestrator → Scheduler | Stop scheduler thread |

## Thread Communication

```
┌─────────────────────┐        ┌─────────────────────┐
│    Orchestrator     │        │     Scheduler       │
│   (Main Thread)     │        │ (Background Thread) │
│                     │        │                     │
│  send_to_scheduler()├───────►│ receive_in_scheduler│
│                     │ Queue  │                     │
│ receive_from_sched()│◄───────┤ send_from_scheduler │
└─────────────────────┘        └─────────────────────┘
```

## Task State Transitions

```
PENDING → READY → RUNNING → COMPLETED
                        ↘ FAILED
                        ↘ CANCELLED
```

## WebSocket Event Stream

When client calls `get_results(run_id)`:
1. Connect to `/ws/results/{run_id}`
2. Receive events: `{"type": "task_started", "task_id": "..."}`
3. Receive events: `{"type": "task_completed", "task_id": "...", "result": ...}`
4. Final event: `{"type": "workflow_completed", "results": [...]}`
