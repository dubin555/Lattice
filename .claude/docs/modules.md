# Module Reference

## lattice/api/ - API Layer

| File | Description |
|------|-------------|
| `server.py` | FastAPI app factory, OrchestratorManager singleton |
| `routes/workflow.py` | Workflow CRUD and execution endpoints |
| `routes/langgraph.py` | LangGraph task endpoints |
| `routes/worker.py` | Worker registration endpoints |
| `models/schemas.py` | Pydantic request/response models |

## lattice/core/ - Core Runtime

### orchestrator/orchestrator.py
- `Orchestrator` - Main controller, runs in main thread
  - `initialize()` - Create MessageBus and start Scheduler thread
  - `create_workflow(id)` - Create new Workflow object
  - `run_workflow(id)` - Submit workflow, create RunContext
  - `wait_workflow_complete(run_id)` - Wait for all tasks to complete
- `RunContext` - Tracks workflow execution state

### scheduler/scheduler.py
- `Scheduler` - Task scheduler, runs in background thread
  - `_run_loop()` - Main event loop
  - `_dispatch_pending_tasks()` - Allocate resources and submit to Executor
  - `_check_completed_tasks()` - Poll for done tasks

### scheduler/message_bus.py
- `MessageBus` - Thread-safe Queue communication
- `MessageType` - RUN_TASK, START_TASK, FINISH_TASK, TASK_EXCEPTION, etc.

### scheduler/batch_collector.py
- `BatchCollector` - Collect batchable tasks by size or timeout

### resource/manager.py
- `ResourceManager` - Track and allocate cluster resources
  - `select_node(requirements)` - Find suitable node for task
  - `release_task_resources()` - Release after completion

### resource/node.py
- `Node` - Node abstraction with CPU/GPU/memory
- `NodeResources`, `GpuResource`, `SelectedNode` - Data classes

### workflow/base.py
- `Workflow` - DAG using NetworkX
- `CodeTask` - Task definition with inputs, outputs, code, resources
- `LangGraphTask` - LangGraph task definition

### runtime/task.py
- `CodeTaskRuntime` / `LangGraphTaskRuntime` - Runtime state
- `TaskStatus` - PENDING, READY, RUNNING, COMPLETED, FAILED, CANCELLED

## lattice/client/ - Client SDK

### core/client.py
- `LatticeClient` - Main client, `create_workflow()` returns LatticeWorkflow

### core/workflow.py
- `LatticeWorkflow` - Workflow builder
  - `add_task(func, inputs)` - Add task, auto-detect dependencies
  - `run()` - Submit workflow, return run_id
  - `get_results(run_id)` - WebSocket to receive results

### core/decorator.py
- `@task(inputs, outputs, resources, batch_size, batch_timeout)`
- `TaskMetadata` - Stores func, code, inputs, outputs, resources

### langgraph/client.py
- `LangGraphClient` - `@client.task(resources)` for LangGraph nodes

## lattice/executor/ - Execution Layer

### base.py
- `ExecutorBackend` - Abstract base class
  - `submit(TaskSubmission)` -> `TaskHandle`
  - `get_result(handle)` -> result
  - `wait(handles, timeout)` -> (done, pending)
  - `cancel(handle)` -> bool

### ray_executor.py
- `RayExecutor` - Ray-based distributed executor
- Uses `NodeAffinitySchedulingStrategy` for node placement

### local_executor.py
- `LocalExecutor` - ThreadPoolExecutor-based local executor

### sandbox/
- `SandboxLevel` - NONE, SUBPROCESS, SECCOMP, DOCKER
- `SubprocessSandbox`, `DockerSandbox` - Isolation implementations
