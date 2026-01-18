# 模块交互文档

本文档详细描述 Lattice 各模块之间的交互方式和数据流。

## 目录

- [1. 整体交互概览](#1-整体交互概览)
- [2. 工作流生命周期](#2-工作流生命周期)
- [3. 任务执行流程](#3-任务执行流程)
- [4. 消息通信机制](#4-消息通信机制)
- [5. 资源管理交互](#5-资源管理交互)
- [6. 分布式 Worker 交互](#6-分布式-worker-交互)
- [7. 批处理交互](#7-批处理交互)

---

## 1. 整体交互概览

```
┌─────────────────────────────────────────────────────────────────────────┐
│                              用户代码                                    │
│   from lattice import LatticeClient, task                               │
│   client = LatticeClient("http://localhost:8000")                       │
│   workflow = client.create_workflow()                                   │
│   task1 = workflow.add_task(my_func, inputs={...})                     │
│   run_id = workflow.run()                                               │
│   results = workflow.get_results(run_id)                                │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                    HTTP / WebSocket 请求
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           API Layer (FastAPI)                            │
│   routes/workflow.py, routes/langgraph.py, routes/worker.py             │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                          方法调用
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                    Orchestrator (主线程, asyncio)                        │
│   - 管理 Workflow 对象                                                   │
│   - 管理 RunContext                                                      │
│   - 监听 Scheduler 消息                                                  │
└───────────────────────────────┬─────────────────────────────────────────┘
                                │
                    MessageBus (queue.Queue)
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                      Scheduler (后台线程)                                │
│   - 任务调度                                                             │
│   - 资源分配                                                             │
│   - 执行追踪                                                             │
└─────────────┬─────────────────┬─────────────────┬───────────────────────┘
              │                 │                 │
              ▼                 ▼                 ▼
      ResourceManager    BatchCollector    WorkflowRuntimeManager
              │                                   │
              └─────────────┬─────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                        ExecutorBackend (Ray)                             │
└─────────────────────────────────────────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
          Worker 1      Worker 2      Worker N
```

---

## 2. 工作流生命周期

### 2.1 创建阶段

```
用户代码                    Client                     API                    Orchestrator
   │                         │                         │                          │
   │ client.create_workflow()│                         │                          │
   │────────────────────────>│                         │                          │
   │                         │ POST /create_workflow   │                          │
   │                         │────────────────────────>│                          │
   │                         │                         │ create_workflow(id)      │
   │                         │                         │─────────────────────────>│
   │                         │                         │                          │ 创建 Workflow 对象
   │                         │                         │                          │ 存入 _workflows 字典
   │                         │                         │<─────────────────────────│
   │                         │<────────────────────────│                          │
   │<────────────────────────│ LatticeWorkflow         │                          │
   │                         │                         │                          │
```

### 2.2 任务添加阶段

```
用户代码                    Client                     API                    Orchestrator        Workflow
   │                         │                         │                          │                   │
   │ workflow.add_task(func) │                         │                          │                   │
   │────────────────────────>│                         │                          │                   │
   │                         │ POST /add_task          │                          │                   │
   │                         │────────────────────────>│                          │                   │
   │                         │                         │ get_workflow(id)         │                   │
   │                         │                         │─────────────────────────>│                   │
   │                         │                         │                          │ add_task(task)    │
   │                         │                         │                          │──────────────────>│
   │                         │                         │                          │                   │ 添加到 DAG
   │                         │                         │<─────────────────────────│<──────────────────│
   │                         │<────────────────────────│                          │                   │
   │                         │                         │                          │                   │
   │                         │ POST /save_task_and_add_edge                       │                   │
   │                         │────────────────────────>│                          │                   │
   │                         │                         │ task.save(...)           │                   │
   │                         │                         │─────────────────────────>│──────────────────>│
   │                         │                         │ workflow.add_edge(...)   │                   │ 解析依赖
   │                         │                         │                          │                   │ 添加边
   │                         │<────────────────────────│<─────────────────────────│<──────────────────│
   │<────────────────────────│ LatticeTask             │                          │                   │
```

### 2.3 执行阶段

```
用户代码        Client              API            Orchestrator         Scheduler
   │              │                  │                  │                   │
   │ workflow.run()                  │                  │                   │
   │─────────────>│                  │                  │                   │
   │              │ POST /run_workflow                  │                   │
   │              │─────────────────>│                  │                   │
   │              │                  │ run_workflow(id) │                   │
   │              │                  │─────────────────>│                   │
   │              │                  │                  │ 创建 RunContext   │
   │              │                  │                  │ 获取入口任务       │
   │              │                  │                  │                   │
   │              │                  │                  │ RUN_TASK ────────>│
   │              │                  │                  │ (入口任务)         │
   │              │                  │<─────────────────│                   │
   │              │<─────────────────│ run_id           │                   │
   │<─────────────│                  │                  │                   │
```

### 2.4 结果获取阶段

```
用户代码        Client              API            Orchestrator         Scheduler
   │              │                  │                  │                   │
   │ get_results(run_id)             │                  │                   │
   │─────────────>│                  │                  │                   │
   │              │ WebSocket 连接    │                  │                   │
   │              │─────────────────>│                  │                   │
   │              │                  │ wait_complete()  │                   │
   │              │                  │─────────────────>│                   │
   │              │                  │                  │                   │
   │              │                  │                  │<── FINISH_TASK ───│
   │              │                  │                  │ 处理任务完成       │
   │              │                  │                  │ 触发后续任务       │
   │              │                  │                  │ RUN_TASK ────────>│
   │              │                  │                  │                   │
   │              │<─ WebSocket 消息 ─│<─────────────────│                   │
   │              │   (task status)  │                  │                   │
   │              │                  │                  │                   │
   │              │                  │                  │<── FINISH_TASK ───│
   │              │                  │                  │ (最后一个任务)     │
   │              │<─ WebSocket 消息 ─│<─────────────────│                   │
   │              │   (workflow done)│                  │                   │
   │<─────────────│ results          │                  │                   │
```

---

## 3. 任务执行流程

### 3.1 单任务执行

```
Scheduler                ResourceManager              Executor                Worker
    │                          │                         │                      │
    │ 从 pending_tasks 取任务   │                         │                      │
    │                          │                         │                      │
    │ select_node(requirements)│                         │                      │
    │─────────────────────────>│                         │                      │
    │                          │ 检查各节点资源           │                      │
    │                          │ 分配资源                 │                      │
    │<─────────────────────────│ SelectedNode             │                      │
    │                          │                         │                      │
    │ submit(TaskSubmission)   │                         │                      │
    │────────────────────────────────────────────────────>│                      │
    │                          │                         │ ray.remote()          │
    │                          │                         │─────────────────────>│
    │<────────────────────────────────────────────────────│ TaskHandle           │
    │                          │                         │                      │
    │ 记录 handle              │                         │                      │
    │ 发送 START_TASK          │                         │                      │
    │                          │                         │                      │
    │ ... 轮询 ...             │                         │                      │
    │                          │                         │                      │
    │ wait(handles)            │                         │                      │
    │────────────────────────────────────────────────────>│                      │
    │                          │                         │<─────────────────────│
    │<────────────────────────────────────────────────────│ (done, pending)      │ result
    │                          │                         │                      │
    │ get_result(handle)       │                         │                      │
    │────────────────────────────────────────────────────>│                      │
    │<────────────────────────────────────────────────────│ result               │
    │                          │                         │                      │
    │ release_task_resources   │                         │                      │
    │─────────────────────────>│                         │                      │
    │                          │ 释放节点资源             │                      │
    │<─────────────────────────│                         │                      │
    │                          │                         │                      │
    │ 发送 FINISH_TASK         │                         │                      │
```

### 3.2 依赖任务触发

```
Orchestrator                    RunContext                    MessageBus
     │                              │                              │
     │ 收到 FINISH_TASK             │                              │
     │─────────────────────────────>│                              │
     │                              │ on_task_finished()           │
     │                              │ 更新任务状态                  │
     │                              │                              │
     │                              │ workflow.get_ready_tasks()   │
     │                              │ 获取就绪的后续任务            │
     │                              │                              │
     │                              │ 对每个就绪任务:              │
     │                              │ send_to_scheduler(RUN_TASK)  │
     │                              │─────────────────────────────>│
     │                              │                              │
     │                              │ result_queue.put(result)     │
     │                              │ (供 get_results 消费)         │
```

---

## 4. 消息通信机制

### 4.1 MessageBus 结构

```
┌─────────────────────────────────────────────────────────────────┐
│                          MessageBus                              │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    to_scheduler                          │    │
│  │                   (queue.Queue)                          │    │
│  │  Orchestrator ────────────────────────────> Scheduler    │    │
│  │                                                          │    │
│  │  消息类型:                                                │    │
│  │  - RUN_TASK: 执行任务                                     │    │
│  │  - CLEAR_WORKFLOW: 清理工作流                             │    │
│  │  - STOP_WORKFLOW: 停止工作流                              │    │
│  │  - START_WORKER: 注册 Worker                              │    │
│  │  - STOP_WORKER: 注销 Worker                               │    │
│  │  - SHUTDOWN: 关闭调度器                                   │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                   from_scheduler                         │    │
│  │                   (queue.Queue)                          │    │
│  │  Scheduler ────────────────────────────> Orchestrator    │    │
│  │                                                          │    │
│  │  消息类型:                                                │    │
│  │  - START_TASK: 任务开始                                   │    │
│  │  - FINISH_TASK: 任务完成                                  │    │
│  │  - TASK_EXCEPTION: 任务异常                               │    │
│  │  - FINISH_LLM_INSTANCE_LAUNCH: LLM 实例就绪               │    │
│  └─────────────────────────────────────────────────────────┘    │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │                    ready_event                           │    │
│  │                (threading.Event)                         │    │
│  │                                                          │    │
│  │  用于 Orchestrator 等待 Scheduler 就绪                    │    │
│  └─────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 消息格式

```python
@dataclass
class Message:
    message_type: MessageType
    data: Dict[str, Any]

# 示例: RUN_TASK 消息
Message(
    message_type=MessageType.RUN_TASK,
    data={
        "task_type": "code",
        "workflow_id": "xxx",
        "task_id": "yyy",
        "task_name": "my_task",
        "task_input": {...},
        "task_output": {...},
        "resources": {"cpu": 2, "gpu": 1},
        "code_str": "def my_task(params): ...",
        "code_ser": "base64...",
    }
)

# 示例: FINISH_TASK 消息
Message(
    message_type=MessageType.FINISH_TASK,
    data={
        "workflow_id": "xxx",
        "task_id": "yyy",
        "result": {"output_key": "value"},
    }
)
```

### 4.3 线程安全

- `queue.Queue` 是线程安全的
- Orchestrator 在主线程通过 `asyncio.run_in_executor` 非阻塞接收消息
- Scheduler 在后台线程直接操作队列

---

## 5. 资源管理交互

### 5.1 资源分配流程

```
Scheduler                           ResourceManager                         Node
    │                                      │                                  │
    │ select_node(requirements)            │                                  │
    │─────────────────────────────────────>│                                  │
    │                                      │                                  │
    │                                      │ 遍历 _nodes                       │
    │                                      │────────────────────────────────>│
    │                                      │ can_run_task(cpu, mem, gpu)?    │
    │                                      │<────────────────────────────────│
    │                                      │                                  │
    │                                      │ 找到合适节点                      │
    │                                      │ allocate_resources()             │
    │                                      │────────────────────────────────>│
    │                                      │                                  │ 减少可用资源
    │                                      │<──────────────────────────────── │ 返回 gpu_id
    │<─────────────────────────────────────│ SelectedNode(node_id, gpu_id)   │
    │                                      │                                  │
```

### 5.2 资源释放流程

```
Scheduler                           ResourceManager                         Node
    │                                      │                                  │
    │ release_task_resources(             │                                  │
    │   node_id, requirements, gpu_id)    │                                  │
    │─────────────────────────────────────>│                                  │
    │                                      │ release_resources()              │
    │                                      │────────────────────────────────>│
    │                                      │                                  │ 增加可用资源
    │<─────────────────────────────────────│<────────────────────────────────│
```

### 5.3 节点健康检查

```
Scheduler                           ResourceManager                        Ray
    │                                      │                                │
    │ check_node_health()                  │                                │
    │─────────────────────────────────────>│                                │
    │                                      │ ray.nodes()                    │
    │                                      │───────────────────────────────>│
    │                                      │<───────────────────────────────│
    │                                      │                                │
    │                                      │ 比对 _nodes 和 ray.nodes       │
    │                                      │ 标记失效节点                    │
    │                                      │ 从 _nodes 移除                 │
    │<─────────────────────────────────────│ dead_nodes 列表                │
```

---

## 6. 分布式 Worker 交互

### 6.1 Worker 连接流程

```
Worker                              Head API                          Orchestrator          Scheduler
   │                                   │                                   │                    │
   │ 启动 Ray (连接到 Head Ray)         │                                   │                    │
   │                                   │                                   │                    │
   │ POST /connect_worker              │                                   │                    │
   │ {node_ip, node_id, resources}     │                                   │                    │
   │──────────────────────────────────>│                                   │                    │
   │                                   │ add_worker(...)                   │                    │
   │                                   │──────────────────────────────────>│                    │
   │                                   │                                   │ START_WORKER ─────>│
   │                                   │                                   │                    │
   │                                   │                                   │                    │ add_node()
   │                                   │<──────────────────────────────────│                    │
   │<──────────────────────────────────│ success                           │                    │
```

### 6.2 Worker 断开流程

```
Worker                              Head API                          Orchestrator          Scheduler
   │                                   │                                   │                    │
   │ POST /disconnect_worker           │                                   │                    │
   │ {node_id}                         │                                   │                    │
   │──────────────────────────────────>│                                   │                    │
   │                                   │ remove_worker(node_id)            │                    │
   │                                   │──────────────────────────────────>│                    │
   │                                   │                                   │ STOP_WORKER ──────>│
   │                                   │                                   │                    │
   │                                   │                                   │                    │ remove_node()
   │                                   │<──────────────────────────────────│                    │
   │<──────────────────────────────────│ success                           │                    │
   │                                   │                                   │                    │
   │ 停止本地 Ray                       │                                   │                    │
```

### 6.3 任务分发到 Worker

```
Scheduler              Executor (Ray)                   Worker
    │                       │                              │
    │ submit(TaskSubmission)│                              │
    │ node_id = worker_node │                              │
    │──────────────────────>│                              │
    │                       │ NodeAffinitySchedulingStrategy
    │                       │ 指定在 worker_node 执行       │
    │                       │                              │
    │                       │ ray.remote(...)              │
    │                       │─────────────────────────────>│
    │                       │                              │ 执行任务
    │                       │                              │
    │                       │<─────────────────────────────│
    │<──────────────────────│ result                       │
```

---

## 7. 批处理交互

### 7.1 批处理收集

```
Scheduler                          BatchCollector
    │                                   │
    │ 收到可批处理任务                    │
    │                                   │
    │ add_task(group_key, task, config) │
    │──────────────────────────────────>│
    │                                   │ 添加到对应 group
    │                                   │ 记录时间戳
    │                                   │
    │ ... 继续处理其他任务 ...            │
    │                                   │
    │ get_ready_batches()               │
    │──────────────────────────────────>│
    │                                   │ 检查每个 group:
    │                                   │ - 数量 >= batch_size?
    │                                   │ - 超时?
    │<──────────────────────────────────│ ready_batches
    │                                   │
```

### 7.2 批处理执行

```
Scheduler                          Executor                          Worker
    │                                 │                                 │
    │ 收集批处理输入                    │                                 │
    │ batched_inputs = [...]          │                                 │
    │                                 │                                 │
    │ submit(TaskSubmission(          │                                 │
    │   func=_run_batch_task,         │                                 │
    │   args=(code, batched_inputs),  │                                 │
    │ ))                              │                                 │
    │────────────────────────────────>│                                 │
    │                                 │ ray.remote()                    │
    │                                 │────────────────────────────────>│
    │                                 │                                 │ 批量执行
    │                                 │                                 │ 返回 [result1, result2, ...]
    │                                 │<────────────────────────────────│
    │<────────────────────────────────│ results (List)                  │
    │                                 │                                 │
    │ 分发结果到各任务                  │                                 │
    │ for i, task in enumerate(tasks):│                                 │
    │   task.result = results[i]      │                                 │
    │   send FINISH_TASK              │                                 │
```

### 7.3 批处理函数签名

```python
def _run_batch_task(
    code_str: Optional[str],
    serialized_code: Optional[str],
    batched_inputs: List[Dict[str, Any]],
) -> List[Any]:
    """
    批处理执行函数。

    Args:
        code_str: 代码字符串
        serialized_code: 序列化的函数
        batched_inputs: 输入列表，每个元素对应一个任务的输入

    Returns:
        结果列表，每个元素对应一个任务的输出
    """
```

---

## 附录: 关键数据结构流转

### 任务数据流转

```
1. 客户端定义 (@task 装饰器)
   TaskMetadata
   ├── func_name
   ├── code_str / serialized_code
   ├── inputs / outputs
   ├── resources
   └── batch_config

            │ HTTP POST
            ▼

2. API 接收并保存
   CodeTask (workflow/base.py)
   ├── task_id
   ├── workflow_id
   ├── task_input / task_output
   ├── code_str / serialized_code
   ├── resources
   └── batch_config

            │ MessageBus RUN_TASK
            ▼

3. Scheduler 创建运行时
   CodeTaskRuntime (runtime/task.py)
   ├── task_id
   ├── status: PENDING -> RUNNING -> COMPLETED
   ├── result
   ├── selected_node
   └── ... (继承自 CodeTask)

            │ Executor submit
            ▼

4. Worker 执行
   TaskSubmission (executor/base.py)
   ├── func
   ├── args
   ├── resources
   ├── node_id
   └── gpu_id

            │ 返回结果
            ▼

5. 结果返回
   Message(FINISH_TASK)
   └── data: {task_id, result}

            │ WebSocket
            ▼

6. 客户端接收
   Dict[str, Any]
   └── result
```
