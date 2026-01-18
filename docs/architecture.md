# Lattice 系统架构文档

本文档详细描述 Lattice 分布式框架的整体架构设计、各模块职责以及模块间的交互方式。

## 目录

- [1. 系统概述](#1-系统概述)
- [2. 整体架构](#2-整体架构)
- [3. 核心模块详解](#3-核心模块详解)
- [4. 模块交互流程](#4-模块交互流程)
- [5. 数据流](#5-数据流)
- [6. 设计决策](#6-设计决策)

---

## 1. 系统概述

Lattice 是一个任务级分布式框架，专为 LLM Agent 工作流设计。其核心目标是：

- **自动并行化**：分析任务依赖关系，自动并行执行独立任务
- **资源管理**：精细化的 CPU/GPU/内存资源分配与调度
- **分布式执行**：支持单机和多节点分布式部署
- **安全隔离**：提供多级沙箱执行环境

### 核心概念

| 概念 | 说明 |
|------|------|
| **Task** | 最小执行单元，包含输入、输出、代码和资源需求 |
| **Workflow** | 任务的 DAG（有向无环图），定义任务间的依赖关系 |
| **Orchestrator** | 工作流生命周期管理器，运行在主线程 |
| **Scheduler** | 任务调度器，运行在后台线程 |
| **Executor** | 任务执行后端（Ray / Local） |
| **Worker** | 分布式工作节点 |

---

## 2. 整体架构

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Client Layer                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │  LatticeClient  │  │ LatticeWorkflow │  │      LangGraphClient        │  │
│  │  (HTTP Client)  │  │  (Workflow API) │  │ (LangGraph Integration)     │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────────┬──────────────┘  │
└───────────┼────────────────────┼──────────────────────────┼─────────────────┘
            │                    │                          │
            │              HTTP / WebSocket                 │
            ▼                    ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              API Layer (FastAPI)                             │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────────────┐  │
│  │ workflow routes │  │ langgraph routes│  │      worker routes          │  │
│  │  /create_workflow│  │ /run_langgraph_task│  │ /connect_worker          │  │
│  │  /add_task       │  │ /add_langgraph_task│  │ /disconnect_worker       │  │
│  │  /run_workflow   │  │                 │  │                           │  │
│  └────────┬────────┘  └────────┬────────┘  └──────────────┬──────────────┘  │
└───────────┼────────────────────┼──────────────────────────┼─────────────────┘
            │                    │                          │
            ▼                    ▼                          ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Core Layer                                      │
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                         Orchestrator (Main Thread)                   │    │
│  │  - 工作流生命周期管理                                                  │    │
│  │  - 接收 API 请求                                                     │    │
│  │  - 管理 RunContext                                                   │    │
│  │  - 监听 Scheduler 消息                                               │    │
│  └───────────────────────────────┬─────────────────────────────────────┘    │
│                                  │                                           │
│                          MessageBus (Queue)                                  │
│                         (线程安全消息传递)                                    │
│                                  │                                           │
│  ┌───────────────────────────────┴─────────────────────────────────────┐    │
│  │                         Scheduler (Background Thread)                │    │
│  │  - 任务调度与分发                                                     │    │
│  │  - 资源分配决策                                                       │    │
│  │  - 执行状态追踪                                                       │    │
│  │  - 批处理任务收集                                                     │    │
│  └───────────────────────────────┬─────────────────────────────────────┘    │
│                                  │                                           │
│  ┌───────────────────────────────┴─────────────────────────────────────┐    │
│  │                       Resource Manager                               │    │
│  │  - 节点资源追踪 (CPU/GPU/Memory)                                     │    │
│  │  - 资源分配与释放                                                     │    │
│  │  - 节点健康检查                                                       │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                              │
└───────────────────────────────────┬─────────────────────────────────────────┘
                                    │
                           ExecutorBackend (Ray)
                                    │
            ┌───────────────────────┼───────────────────────┐
            ▼                       ▼                       ▼
     ┌─────────────┐         ┌─────────────┐         ┌─────────────┐
     │   Worker 1  │         │   Worker 2  │         │   Worker N  │
     │  ┌────────┐ │         │  ┌────────┐ │         │  ┌────────┐ │
     │  │Sandbox │ │         │  │Sandbox │ │         │  │Sandbox │ │
     │  └────────┘ │         │  └────────┘ │         │  └────────┘ │
     └─────────────┘         └─────────────┘         └─────────────┘
```

---

## 3. 核心模块详解

### 3.1 Client 层 (`lattice/client/`)

客户端 SDK，为用户提供 Python API。

#### 3.1.1 LatticeClient (`client/core/client.py`)

主客户端入口，负责与服务器通信。

```python
class LatticeClient:
    def __init__(self, server_url: str)
    def create_workflow(self) -> LatticeWorkflow  # 创建新工作流
    def get_workflow(self, workflow_id: str) -> LatticeWorkflow
    def get_ray_head_port(self) -> int
```

#### 3.1.2 LatticeWorkflow (`client/core/workflow.py`)

工作流构建器，支持添加任务和定义依赖。

```python
class LatticeWorkflow:
    def add_task(task_func, inputs, task_name) -> LatticeTask  # 添加任务
    def add_edge(source_task, target_task)  # 显式添加依赖
    def run() -> str  # 提交执行，返回 run_id
    def get_results(run_id) -> List[Dict]  # 获取结果（WebSocket）
```

#### 3.1.3 @task 装饰器 (`client/core/decorator.py`)

任务定义装饰器，声明输入输出和资源需求。

```python
@task(
    inputs=["query"],           # 输入参数名
    outputs=["result"],         # 输出参数名
    resources={"cpu": 2, "gpu": 1},  # 资源需求
    batch_size=10,              # 批处理大小（可选）
    batch_timeout=1.0,          # 批处理超时（可选）
)
def my_task(params):
    return {"result": process(params["query"])}
```

#### 3.1.4 LangGraphClient (`client/langgraph/client.py`)

LangGraph 集成客户端，让 LangGraph 节点自动获得并行能力。

```python
class LangGraphClient:
    def task(resources=None)  # 装饰 LangGraph 节点
    # 使用示例:
    # @client.task(cpu=2)
    # def process_node(state): ...
```

---

### 3.2 API 层 (`lattice/api/`)

基于 FastAPI 的 REST/WebSocket API 服务。

#### 3.2.1 Server (`api/server.py`)

应用工厂和生命周期管理。

```python
def create_app(ray_head_port, metrics_enabled, ...) -> FastAPI
# - 初始化 Orchestrator
# - 注册路由
# - 配置 CORS、Metrics 中间件
# - 注册信号处理
```

#### 3.2.2 Routes

| 路由模块 | 端点 | 功能 |
|---------|------|------|
| `workflow.py` | `/create_workflow` | 创建工作流 |
| | `/add_task` | 添加任务 |
| | `/save_task_and_add_edge` | 保存任务并添加依赖边 |
| | `/run_workflow` | 执行工作流 |
| | `/get_workflow_res/{id}/{run_id}` | WebSocket 获取结果 |
| `langgraph.py` | `/add_langgraph_task` | 添加 LangGraph 任务 |
| | `/run_langgraph_task` | 执行单个 LangGraph 任务 |
| `worker.py` | `/connect_worker` | 连接 Worker 节点 |
| | `/disconnect_worker` | 断开 Worker 节点 |

---

### 3.3 Core 层 (`lattice/core/`)

核心运行时组件。

#### 3.3.1 Orchestrator (`core/orchestrator/orchestrator.py`)

工作流编排器，运行在主线程，管理工作流生命周期。

**职责**：
- 创建和管理 Workflow 对象
- 启动和协调 Scheduler
- 通过 MessageBus 与 Scheduler 通信
- 管理 RunContext（执行上下文）
- 接收任务完成事件，触发后续任务

```python
class Orchestrator:
    def initialize(self)  # 初始化 MessageBus 和 Scheduler
    def create_workflow(workflow_id) -> Workflow
    def run_workflow(workflow_id) -> str  # 返回 run_id
    async def wait_workflow_complete(run_id) -> List[Dict]
    def add_worker(node_ip, node_id, resources)
    def remove_worker(node_id)
```

#### 3.3.2 Scheduler (`core/scheduler/scheduler.py`)

任务调度器，运行在后台线程，负责任务调度和执行。

**职责**：
- 接收待执行任务
- 资源分配决策
- 提交任务到 Executor
- 追踪任务执行状态
- 处理批处理任务

```python
class Scheduler:
    def start(self)  # 启动后台线程
    def _run_loop(self)  # 主事件循环
    def _dispatch_pending_tasks(self)  # 分发待执行任务
    def _dispatch_batched_tasks(self)  # 分发批处理任务
    def _check_completed_tasks(self)  # 检查已完成任务
```

#### 3.3.3 MessageBus (`core/scheduler/message_bus.py`)

线程安全的消息总线，用于 Orchestrator 和 Scheduler 之间的通信。

```python
class MessageBus:
    def send_to_scheduler(message: Message)  # Orchestrator -> Scheduler
    def receive_from_scheduler() -> Message  # Scheduler -> Orchestrator
    def send_from_scheduler(message: Message)
    def receive_in_scheduler() -> Message
    def signal_ready()  # Scheduler 就绪信号
    def wait_ready(timeout) -> bool
```

**消息类型** (`MessageType`):
- `RUN_TASK` - 执行任务
- `START_TASK` - 任务开始
- `FINISH_TASK` - 任务完成
- `TASK_EXCEPTION` - 任务异常
- `CLEAR_WORKFLOW` - 清理工作流
- `STOP_WORKFLOW` - 停止工作流
- `START_WORKER` / `STOP_WORKER` - Worker 管理
- `SHUTDOWN` - 关闭调度器

#### 3.3.4 ResourceManager (`core/resource/manager.py`)

资源管理器，追踪和分配集群资源。

```python
class ResourceManager:
    def initialize_with_ray(self)  # 从 Ray 初始化资源信息
    def add_node(node_id, node_ip, resources)  # 添加节点
    def remove_node(node_id)
    def select_node(requirements) -> SelectedNode  # 选择合适节点
    def release_task_resources(node_id, requirements, gpu_id)
    def check_node_health() -> List[str]  # 检查节点健康状态
```

#### 3.3.5 Workflow (`core/workflow/base.py`)

工作流定义，使用 NetworkX 管理 DAG。

```python
class Workflow:
    def add_task(task_id, task: CodeTask)
    def add_edge(source_task_id, target_task_id)
    def get_start_tasks() -> List[CodeTask]  # 获取入口任务
    def get_ready_tasks_after_completion(task_id) -> List[CodeTask]
```

#### 3.3.6 BatchCollector (`core/scheduler/batch_collector.py`)

批处理任务收集器，支持按大小或超时触发批处理。

---

### 3.4 Executor 层 (`lattice/executor/`)

任务执行后端，支持多种执行引擎。

#### 3.4.1 ExecutorBackend (`executor/base.py`)

执行器抽象基类。

```python
class ExecutorBackend(ABC):
    def initialize(self)
    def submit(submission: TaskSubmission) -> TaskHandle
    def get_result(handle: TaskHandle) -> Any
    def wait(handles, timeout) -> (done, pending)
    def cancel(handle: TaskHandle) -> bool
    def shutdown(self)
```

#### 3.4.2 RayExecutor (`executor/ray_executor.py`)

基于 Ray 的分布式执行器。

**特性**：
- 节点亲和性调度
- GPU 资源分配
- 任务取消支持

#### 3.4.3 LocalExecutor (`executor/local_executor.py`)

本地执行器，使用 `concurrent.futures.ThreadPoolExecutor`。

#### 3.4.4 Sandbox (`executor/sandbox.py`)

安全沙箱执行环境。

| 隔离级别 | 实现方式 | 特性 |
|---------|---------|------|
| `NONE` | 直接执行 | 最快，无隔离 |
| `SUBPROCESS` | 独立进程 + 资源限制 | 跨平台 |
| `SECCOMP` | 系统调用过滤 | Linux，高安全性 |
| `DOCKER` | 容器隔离 | 最强隔离 |

---

### 3.5 Worker 层 (`lattice/core/worker/`)

分布式工作节点实现。

```python
class Worker:
    def connect_to_head(head_ip, head_port)  # 连接 Head 节点
    def start(self)  # 启动 Worker
    def stop(self)  # 停止 Worker
```

---

### 3.6 Observability 层 (`lattice/observability/`)

可观测性组件（可选）。

- **Metrics** (`metrics.py`) - OpenTelemetry 指标收集
- **Middleware** (`middleware.py`) - HTTP 请求指标中间件

支持的导出器：
- Prometheus
- OTLP (gRPC/HTTP)
- Console

---

## 4. 模块交互流程

### 4.1 工作流创建和执行流程

```
┌──────────┐     ┌─────────┐     ┌─────────────┐     ┌───────────┐
│  Client  │     │   API   │     │ Orchestrator│     │ Scheduler │
└────┬─────┘     └────┬────┘     └──────┬──────┘     └─────┬─────┘
     │                │                 │                  │
     │ create_workflow│                 │                  │
     │───────────────>│                 │                  │
     │                │ create_workflow │                  │
     │                │────────────────>│                  │
     │                │                 │ (创建 Workflow)  │
     │<───────────────│<────────────────│                  │
     │   workflow_id  │                 │                  │
     │                │                 │                  │
     │ add_task       │                 │                  │
     │───────────────>│                 │                  │
     │                │ add_task        │                  │
     │                │────────────────>│                  │
     │                │                 │ (添加到 DAG)     │
     │<───────────────│<────────────────│                  │
     │   task_id      │                 │                  │
     │                │                 │                  │
     │ run_workflow   │                 │                  │
     │───────────────>│                 │                  │
     │                │ run_workflow    │                  │
     │                │────────────────>│                  │
     │                │                 │ RUN_TASK (入口)  │
     │                │                 │─────────────────>│
     │                │                 │                  │ (调度任务)
     │<───────────────│<────────────────│                  │
     │   run_id       │                 │                  │
```

### 4.2 任务执行流程

```
┌───────────┐     ┌───────────────┐     ┌──────────┐     ┌────────┐
│ Scheduler │     │ResourceManager│     │ Executor │     │ Worker │
└─────┬─────┘     └───────┬───────┘     └────┬─────┘     └───┬────┘
      │                   │                  │               │
      │ select_node       │                  │               │
      │──────────────────>│                  │               │
      │ SelectedNode      │                  │               │
      │<──────────────────│                  │               │
      │                   │                  │               │
      │ submit(TaskSubmission)               │               │
      │─────────────────────────────────────>│               │
      │                   │                  │ execute       │
      │                   │                  │──────────────>│
      │ TaskHandle        │                  │               │
      │<─────────────────────────────────────│               │
      │                   │                  │               │
      │ ... (轮询检查) ...│                  │               │
      │                   │                  │               │
      │ wait(handles)     │                  │               │
      │─────────────────────────────────────>│               │
      │ (done, pending)   │                  │<──────────────│
      │<─────────────────────────────────────│   result      │
      │                   │                  │               │
      │ release_resources │                  │               │
      │──────────────────>│                  │               │
```

### 4.3 消息流向

```
                    Orchestrator (主线程)
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              │              ▼
    ┌─────────────┐        │      ┌─────────────────┐
    │ RunContext  │        │      │ SingleTaskContext│
    │ (工作流执行) │        │      │ (LangGraph 任务) │
    └──────┬──────┘        │      └────────┬────────┘
           │               │               │
           │   ┌───────────┴───────────┐   │
           │   │      MessageBus       │   │
           │   │  ┌─────────────────┐  │   │
           └──>│  │ to_scheduler    │──┼───┘
               │  │ (Orchestrator   │  │
               │  │  -> Scheduler)  │  │
               │  └─────────────────┘  │
               │  ┌─────────────────┐  │
               │  │ from_scheduler  │  │
               │  │ (Scheduler      │  │
               │  │  -> Orchestrator)│ │
               │  └─────────────────┘  │
               └───────────┬───────────┘
                           │
                           ▼
                    Scheduler (后台线程)
                           │
            ┌──────────────┼──────────────┐
            ▼              ▼              ▼
    ┌─────────────┐ ┌─────────────┐ ┌─────────────┐
    │ BatchCollector│ResourceManager│WorkflowRuntimeManager│
    └─────────────┘ └─────────────┘ └─────────────┘
```

---

## 5. 数据流

### 5.1 任务数据结构

```python
# 任务定义（客户端）
TaskMetadata:
    func: Callable           # 原始函数
    func_name: str           # 函数名
    code_str: str            # 源代码字符串
    serialized_code: str     # cloudpickle 序列化的函数
    inputs: List[str]        # 输入参数名列表
    outputs: List[str]       # 输出参数名列表
    resources: Dict          # 资源需求 {cpu, gpu, cpu_mem, gpu_mem}
    batch_config: BatchConfig # 批处理配置

# 任务定义（服务端）
CodeTask:
    workflow_id: str
    task_id: str
    task_name: str
    task_input: Dict         # 输入参数配置
    task_output: Dict        # 输出参数配置
    code_str: str
    serialized_code: str
    resources: Dict
    batch_config: Dict

# 任务运行时状态
CodeTaskRuntime:
    task_id: str
    status: TaskStatus       # PENDING, READY, RUNNING, COMPLETED, FAILED
    result: Any              # 执行结果
    selected_node: SelectedNode  # 分配的节点
```

### 5.2 输入参数解析

```python
task_input = {
    "input_params": {
        "1": {
            "key": "query",              # 参数名
            "input_schema": "from_user", # from_user | from_task
            "data_type": "str",
            "value": "hello"             # 直接值或 "task_id.output_key"
        }
    }
}
```

当 `input_schema` 为 `from_task` 时，`value` 格式为 `{source_task_id}.{output_key}`，调度器会在运行时解析依赖任务的输出。

---

## 6. 设计决策

### 6.1 线程模型

**决策**：Orchestrator 在主线程，Scheduler 在后台线程，使用 Queue 通信。

**原因**：
- FastAPI 是异步框架，需要非阻塞的请求处理
- Scheduler 需要持续轮询任务状态，适合在独立线程运行
- Queue 提供线程安全的消息传递，避免锁竞争

### 6.2 LangGraph 同步调用

**决策**：LangGraphClient 使用同步阻塞调用。

**原因**：
- 外层 FastAPI 已是异步，多请求可并发处理
- 执行引擎 Ray 本身是异步的，任务在 Worker 上并行执行
- LangGraph 调用点同步等待，符合正常函数调用语义
- 异步回调会增加复杂度（状态机、回调注册、结果拼装）

### 6.3 DAG 依赖管理

**决策**：使用 NetworkX 管理任务 DAG。

**原因**：
- NetworkX 提供成熟的图算法
- 内置环检测（防止循环依赖）
- 支持拓扑排序、前驱/后继查询

### 6.4 资源管理

**决策**：ResourceManager 独立于 Scheduler，但由 Scheduler 调用。

**原因**：
- 职责分离：资源追踪 vs 任务调度
- 支持多种执行后端（Ray/Local）的统一资源抽象
- 便于扩展新的资源类型

### 6.5 沙箱执行

**决策**：提供多级沙箱，默认不启用。

**原因**：
- 不同场景有不同的安全需求
- 沙箱会带来性能开销
- 用户可根据代码可信度选择隔离级别

---

## 附录：目录结构

```
lattice/
├── __init__.py           # 公开 API 导出
├── exceptions.py         # 异常定义
├── api/                  # API 层
│   ├── server.py         # FastAPI 应用工厂
│   ├── models/           # Pydantic 模型
│   │   └── schemas.py
│   └── routes/           # 路由处理器
│       ├── workflow.py
│       ├── langgraph.py
│       └── worker.py
├── cli/                  # 命令行接口
│   └── cli.py
├── client/               # 客户端 SDK
│   ├── core/
│   │   ├── client.py     # LatticeClient
│   │   ├── workflow.py   # LatticeWorkflow
│   │   ├── decorator.py  # @task 装饰器
│   │   └── models.py     # LatticeTask, TaskOutput
│   └── langgraph/
│       └── client.py     # LangGraphClient
├── config/               # 配置
│   ├── defaults.py       # 默认配置
│   └── logging.py        # 日志配置
├── core/                 # 核心运行时
│   ├── orchestrator/
│   │   └── orchestrator.py
│   ├── scheduler/
│   │   ├── scheduler.py
│   │   ├── message_bus.py
│   │   └── batch_collector.py
│   ├── resource/
│   │   ├── manager.py
│   │   └── node.py
│   ├── runtime/
│   │   ├── task.py       # 任务运行时状态
│   │   └── workflow.py   # 工作流运行时管理
│   ├── workflow/
│   │   └── base.py       # Workflow, CodeTask 定义
│   └── worker/
│       └── worker.py
├── executor/             # 执行器
│   ├── base.py           # ExecutorBackend 抽象
│   ├── factory.py        # 执行器工厂
│   ├── ray_executor.py   # Ray 执行器
│   ├── local_executor.py # 本地执行器
│   ├── sandbox.py        # 沙箱执行环境
│   └── runner.py         # 代码运行器
├── llm/                  # LLM 实例管理
│   └── manager.py
├── observability/        # 可观测性
│   ├── metrics.py        # OpenTelemetry 指标
│   └── middleware.py     # HTTP 中间件
└── utils/                # 工具函数
    ├── network.py
    └── gpu.py
```
