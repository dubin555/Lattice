# Core 模块文档

本文档详细描述 `lattice/core/` 模块的设计和实现。

## 目录

- [1. 概述](#1-概述)
- [2. Orchestrator 模块](#2-orchestrator-模块)
- [3. Scheduler 模块](#3-scheduler-模块)
- [4. Resource 模块](#4-resource-模块)
- [5. Workflow 模块](#5-workflow-模块)
- [6. Runtime 模块](#6-runtime-模块)
- [7. Worker 模块](#7-worker-模块)

---

## 1. 概述

Core 模块是 Lattice 的核心运行时层，包含：

| 子模块 | 职责 |
|--------|------|
| `orchestrator/` | 工作流生命周期管理 |
| `scheduler/` | 任务调度和消息传递 |
| `resource/` | 集群资源管理 |
| `workflow/` | 工作流和任务定义 |
| `runtime/` | 任务运行时状态 |
| `worker/` | 分布式工作节点 |

---

## 2. Orchestrator 模块

### 2.1 Orchestrator 类

位置：`core/orchestrator/orchestrator.py`

Orchestrator 是工作流编排的核心，运行在 **主线程**，负责：

1. **工作流管理** - 创建、存储、查询工作流
2. **执行协调** - 启动工作流执行，管理执行上下文
3. **消息监听** - 监听 Scheduler 发送的任务状态更新
4. **Worker 管理** - 注册和注销分布式 Worker 节点

#### 核心方法

```python
class Orchestrator:
    def __init__(self, ray_head_port: int = 6379):
        self._message_bus: MessageBus = None
        self._scheduler: Scheduler = None
        self._workflows: Dict[str, Workflow] = {}
        self._run_contexts: Dict[str, RunContext] = {}

    def initialize(self) -> None:
        """
        初始化编排器：
        1. 创建 MessageBus
        2. 创建并启动 Scheduler（后台线程）
        3. 等待 Scheduler 就绪
        """

    async def start_monitor(self) -> None:
        """启动消息监听循环"""

    def create_workflow(self, workflow_id: str) -> Workflow:
        """创建新的工作流对象"""

    def run_workflow(self, workflow_id: str) -> str:
        """
        执行工作流：
        1. 深拷贝工作流定义
        2. 创建 RunContext
        3. 提交入口任务到 Scheduler
        4. 返回 run_id
        """

    async def wait_workflow_complete(self, run_id: str) -> List[Dict]:
        """等待工作流完成，返回所有结果"""

    async def run_langgraph_task(self, workflow_id, task_id, args, kwargs) -> Any:
        """执行单个 LangGraph 任务"""

    def add_worker(self, node_ip, node_id, resources) -> None:
        """注册 Worker 节点"""

    def remove_worker(self, node_id) -> None:
        """注销 Worker 节点"""

    def cleanup(self) -> None:
        """清理资源，停止 Scheduler"""
```

#### 消息监听循环

```python
async def _monitor_loop(self) -> None:
    """
    持续监听来自 Scheduler 的消息：
    - FINISH_TASK: 任务完成，触发后续任务
    - START_TASK: 任务开始执行
    - TASK_EXCEPTION: 任务异常
    - FINISH_LLM_INSTANCE_LAUNCH: LLM 实例就绪
    """
    while True:
        message = await self._receive_from_scheduler()
        if message:
            await self._handle_scheduler_message(message)
```

### 2.2 RunContext 类

执行上下文，追踪单次工作流执行的状态。

```python
class RunContext(BaseContext):
    def __init__(self, run_id: str, workflow: Workflow, message_bus: MessageBus):
        self.run_id = run_id
        self.workflow = workflow
        self.result_queue: asyncio.Queue = asyncio.Queue()

    def submit_start_tasks(self) -> None:
        """提交无依赖的入口任务"""

    async def on_task_finished(self, msg_data: Dict) -> None:
        """
        任务完成回调：
        1. 将结果放入 result_queue
        2. 获取就绪的后续任务
        3. 提交后续任务到 Scheduler
        """

    async def wait_complete(self) -> List[Dict]:
        """等待所有任务完成"""
```

### 2.3 SingleTaskContext 类

单任务执行上下文，用于 LangGraph 任务。

```python
class SingleTaskContext(BaseContext):
    def __init__(self, task_id: str):
        self.task_id = task_id
        self.result_queue: asyncio.Queue = asyncio.Queue()

    async def on_task_finished(self, msg_data: Dict) -> None:
        """将任务结果放入队列"""

    async def wait_result(self) -> Any:
        """等待并返回任务结果"""
```

---

## 3. Scheduler 模块

### 3.1 Scheduler 类

位置：`core/scheduler/scheduler.py`

Scheduler 是任务调度的核心，运行在 **后台线程**，负责：

1. **任务队列管理** - 维护待执行任务列表
2. **资源调度** - 选择合适的节点执行任务
3. **执行管理** - 提交任务到 Executor，追踪执行状态
4. **批处理** - 收集和分发批处理任务

#### 线程模型

```
Main Thread                    Background Thread
    │                               │
    │                               │
Orchestrator                   Scheduler
    │                               │
    │─── send_to_scheduler ────────>│
    │                               │
    │<── receive_from_scheduler ────│
    │                               │
```

#### 核心方法

```python
class Scheduler:
    def __init__(
        self,
        message_bus: MessageBus,
        executor_type: ExecutorType = ExecutorType.RAY,
        ray_head_port: int = 6379,
        batch_rules: List[BatchRule] = None,
    ):
        self._message_bus = message_bus
        self._executor: ExecutorBackend = None
        self._resource_manager = ResourceManager()
        self._batch_collector = BatchCollector(rules=batch_rules)
        self._pending_tasks: List[BaseTaskRuntime] = []
        self._task_handles: Dict[str, TaskHandle] = {}

    def start(self) -> None:
        """启动后台线程"""

    def _run_loop(self) -> None:
        """
        主事件循环：
        1. 接收来自 Orchestrator 的消息
        2. 分发待执行任务
        3. 分发批处理任务
        4. 检查已完成任务
        5. 检查节点健康状态
        """

    def _dispatch_pending_tasks(self) -> None:
        """
        分发待执行任务：
        1. 对于可批处理任务，收集到 BatchCollector
        2. 对于普通任务，选择节点并提交执行
        """

    def _submit_task(self, task: BaseTaskRuntime, node: SelectedNode) -> None:
        """
        提交单个任务：
        1. 构造 TaskSubmission
        2. 调用 Executor.submit()
        3. 记录 TaskHandle
        4. 发送 START_TASK 消息
        """

    def _check_completed_tasks(self) -> None:
        """
        检查已完成任务：
        1. 调用 Executor.wait() 获取已完成的 handles
        2. 获取任务结果
        3. 释放资源
        4. 发送 FINISH_TASK 消息
        """
```

#### 消息处理

```python
def _handle_message(self, message: Message) -> None:
    handlers = {
        MessageType.RUN_TASK: self._add_pending_task,
        MessageType.CLEAR_WORKFLOW: self._clear_workflow,
        MessageType.STOP_WORKFLOW: self._cancel_workflow,
        MessageType.START_WORKER: self._add_worker,
        MessageType.STOP_WORKER: self._remove_worker,
        MessageType.SHUTDOWN: self._shutdown,
    }
```

### 3.2 MessageBus 类

位置：`core/scheduler/message_bus.py`

线程安全的消息总线，使用 Python `queue.Queue` 实现。

```python
class MessageBus:
    def __init__(self):
        self._to_scheduler: queue.Queue = queue.Queue()
        self._from_scheduler: queue.Queue = queue.Queue()
        self._ready_event: threading.Event = threading.Event()

    # Orchestrator 端
    def send_to_scheduler(self, message: Message) -> None
    def receive_from_scheduler(self, timeout: float = None) -> Optional[Message]

    # Scheduler 端
    def send_from_scheduler(self, message: Message) -> None
    def receive_in_scheduler(self, timeout: float = None) -> Optional[Message]

    # 同步
    def signal_ready(self) -> None
    def wait_ready(self, timeout: float = None) -> bool
```

### 3.3 Message 和 MessageType

```python
class MessageType(Enum):
    # 任务相关
    RUN_TASK = "run_task"
    START_TASK = "start_task"
    FINISH_TASK = "finish_task"
    TASK_EXCEPTION = "task_exception"

    # 工作流相关
    CLEAR_WORKFLOW = "clear_workflow"
    STOP_WORKFLOW = "stop_workflow"
    FINISH_WORKFLOW = "finish_workflow"

    # Worker 相关
    START_WORKER = "start_worker"
    STOP_WORKER = "stop_worker"

    # LLM 实例相关
    START_LLM_INSTANCE = "start_llm_instance"
    STOP_LLM_INSTANCE = "stop_llm_instance"
    FINISH_LLM_INSTANCE_LAUNCH = "finish_llm_instance_launch"

    # 系统
    SHUTDOWN = "shutdown"

@dataclass
class Message:
    message_type: MessageType
    data: Dict[str, Any]
```

### 3.4 BatchCollector 类

位置：`core/scheduler/batch_collector.py`

批处理任务收集器，支持：

- **按大小触发** - 收集够 batch_size 个任务后执行
- **按超时触发** - 超过 batch_timeout 后执行
- **分组** - 相同 task_name 的任务会被分到同一组

```python
class BatchCollector:
    def __init__(self, rules: List[BatchRule] = None):
        self._groups: Dict[str, List[CodeTaskRuntime]] = {}
        self._timestamps: Dict[str, float] = {}

    def add_task(self, group_key: str, task: CodeTaskRuntime, config: BatchConfig = None):
        """添加任务到收集器"""

    def get_ready_batches(self) -> Dict[str, List[CodeTaskRuntime]]:
        """获取就绪的批次（满足大小或超时条件）"""

    def pending_count(self) -> int:
        """待处理任务数量"""
```

---

## 4. Resource 模块

### 4.1 ResourceManager 类

位置：`core/resource/manager.py`

集群资源管理器，负责：

1. **节点追踪** - 维护节点列表和资源状态
2. **资源分配** - 为任务选择合适的节点
3. **资源释放** - 任务完成后释放资源
4. **健康检查** - 检测失效节点

```python
class ResourceManager:
    def __init__(self):
        self._nodes: Dict[str, Node] = {}
        self._head_node_id: str = None

    def initialize_with_ray(self) -> None:
        """从 Ray 集群初始化资源信息"""

    def initialize_local(self) -> None:
        """本地模式初始化"""

    def add_node(self, node_id: str, node_ip: str, resources: Dict) -> None:
        """添加节点"""

    def remove_node(self, node_id: str) -> None:
        """移除节点"""

    def select_node(self, requirements: TaskResourceRequirements) -> Optional[SelectedNode]:
        """
        选择满足资源需求的节点：
        1. 遍历所有节点
        2. 检查是否满足 CPU/GPU/内存需求
        3. 分配资源并返回 SelectedNode
        """

    def release_task_resources(
        self,
        node_id: str,
        requirements: TaskResourceRequirements,
        gpu_id: int = None,
    ) -> None:
        """释放任务占用的资源"""

    def check_node_health(self) -> List[str]:
        """检查节点健康状态，返回失效节点列表"""
```

### 4.2 Node 类

位置：`core/resource/node.py`

节点抽象，包含资源信息和状态。

```python
@dataclass
class Node:
    node_id: str
    node_ip: str
    available_resources: NodeResources  # 可用资源
    total_resources: NodeResources      # 总资源
    status: NodeStatus                   # ALIVE / DEAD

    def can_run_task(self, cpu, memory, gpu, gpu_memory) -> bool:
        """检查是否有足够资源"""

    def allocate_resources(self, cpu, memory, gpu, gpu_memory) -> Optional[int]:
        """分配资源，返回 GPU ID（如果需要）"""

    def release_resources(self, cpu, memory, gpu, gpu_memory, gpu_id) -> None:
        """释放资源"""

@dataclass
class NodeResources:
    cpu_count: float
    memory_bytes: int
    gpu_resources: Dict[int, GpuResource]

@dataclass
class GpuResource:
    gpu_id: int
    gpu_memory_total: int
    gpu_memory_available: int
    gpu_count: int

@dataclass
class SelectedNode:
    node_id: str
    node_ip: str
    gpu_id: Optional[int] = None
```

### 4.3 TaskResourceRequirements

```python
@dataclass
class TaskResourceRequirements:
    cpu: float = 1.0
    memory_bytes: int = 0
    gpu: int = 0
    gpu_memory: int = 0

    @classmethod
    def from_dict(cls, data: Dict) -> "TaskResourceRequirements":
        """从字典创建"""
```

---

## 5. Workflow 模块

位置：`core/workflow/base.py`

### 5.1 BaseTask 抽象类

```python
@dataclass
class BaseTask(ABC):
    workflow_id: str
    task_id: str
    task_name: str
    completed: bool = False

    @property
    @abstractmethod
    def task_type(self) -> TaskType:
        pass

    @abstractmethod
    def to_dict(self) -> Dict[str, Any]:
        pass
```

### 5.2 CodeTask 类

普通代码任务定义。

```python
@dataclass
class CodeTask(BaseTask):
    resources: Dict[str, Any] = None
    task_input: Dict[str, Any] = None   # 输入参数配置
    task_output: Dict[str, Any] = None  # 输出参数配置
    code_str: str = None                 # 源代码字符串
    serialized_code: str = None          # 序列化的函数
    batch_config: Dict[str, Any] = None  # 批处理配置

    @property
    def task_type(self) -> TaskType:
        return TaskType.CODE

    def save(self, task_input, task_output, code_str, serialized_code, resources, batch_config):
        """保存任务配置"""

    def to_dict(self) -> Dict[str, Any]:
        """序列化为字典"""
```

### 5.3 LangGraphTask 类

LangGraph 任务定义。

```python
@dataclass
class LangGraphTask(BaseTask):
    serialized_code: str = ""
    resources: Dict[str, Any] = field(default_factory=dict)
    serialized_args: str = None
    serialized_kwargs: str = None

    @property
    def task_type(self) -> TaskType:
        return TaskType.LANGGRAPH

    def set_args(self, args: str) -> None:
        """设置序列化的参数"""

    def set_kwargs(self, kwargs: str) -> None:
        """设置序列化的关键字参数"""
```

### 5.4 Workflow 类

工作流定义，使用 NetworkX 管理 DAG。

```python
class Workflow(BaseWorkflow):
    def __init__(self, workflow_id: str):
        self.workflow_id = workflow_id
        self._tasks: Dict[str, CodeTask] = {}
        self._graph: nx.DiGraph = nx.DiGraph()

    def add_task(self, task_id: str, task: CodeTask) -> None:
        """添加任务到工作流"""

    def add_edge(self, source_task_id: str, target_task_id: str) -> None:
        """
        添加依赖边：
        1. 检查是否会形成循环
        2. 如果会，回滚并抛出异常
        """

    def get_start_tasks(self) -> List[CodeTask]:
        """获取入口任务（入度为 0 的节点）"""

    def get_ready_tasks_after_completion(self, completed_task_id: str) -> List[CodeTask]:
        """
        获取任务完成后就绪的后续任务：
        1. 标记当前任务为已完成
        2. 检查所有后继节点
        3. 如果后继的所有前驱都已完成，则该后继就绪
        """

    def get_graph_edges(self) -> List[tuple]:
        """获取所有边"""
```

---

## 6. Runtime 模块

### 6.1 TaskRuntime 类

位置：`core/runtime/task.py`

任务运行时状态，扩展 Task 定义。

```python
class TaskStatus(Enum):
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BaseTaskRuntime(ABC):
    task_id: str
    workflow_id: str
    task_name: str
    status: TaskStatus
    result: Any = None
    selected_node: SelectedNode = None

class CodeTaskRuntime(BaseTaskRuntime):
    code_str: str
    serialized_code: str
    task_input: Dict
    task_output: Dict
    resources: Dict
    batch_config: Dict

    @property
    def is_batchable(self) -> bool:
        """是否可批处理"""

class LangGraphTaskRuntime(BaseTaskRuntime):
    serialized_code: str
    serialized_args: str
    serialized_kwargs: str
    resources: Dict
```

### 6.2 WorkflowRuntimeManager

位置：`core/runtime/workflow.py`

工作流运行时管理器，在 Scheduler 中使用。

```python
class WorkflowRuntimeManager:
    def __init__(self):
        self._workflows: Dict[str, WorkflowRuntime] = {}

    def add_task(self, task: BaseTaskRuntime) -> None:
        """添加任务到工作流运行时"""

    def run_task(self, task: BaseTaskRuntime, handle_id: Any, node: SelectedNode) -> None:
        """标记任务为运行中"""

    def set_task_result(self, task: BaseTaskRuntime, result: Any) -> None:
        """设置任务结果"""

    def get_task_result_value(self, workflow_id: str, ref: str) -> Any:
        """
        获取任务输出值，支持 "task_id.output_key" 格式
        """

    def cancel_workflow(self, workflow_id: str) -> List[BaseTaskRuntime]:
        """取消工作流，返回所有运行中的任务"""

    def clear_workflow(self, workflow_id: str) -> None:
        """清理工作流数据"""
```

---

## 7. Worker 模块

位置：`core/worker/worker.py`

分布式工作节点实现。

```python
class Worker:
    def __init__(self, head_ip: str, head_port: int):
        self.head_ip = head_ip
        self.head_port = head_port
        self.node_id: str = None
        self.node_ip: str = None

    def connect_to_head(self) -> None:
        """
        连接到 Head 节点：
        1. 启动本地 Ray（连接到 Head 的 Ray 集群）
        2. 收集本地资源信息
        3. 调用 /connect_worker API 注册
        """

    def start(self) -> None:
        """启动 Worker，保持运行"""

    def stop(self) -> None:
        """
        停止 Worker：
        1. 调用 /disconnect_worker API 注销
        2. 停止本地 Ray
        """

    def _collect_resources(self) -> Dict[str, Any]:
        """收集本地资源信息（CPU/GPU/内存）"""
```

### Worker 生命周期

```
1. 启动 Worker
   $ lattice start --worker --addr HEAD_IP:HEAD_PORT

2. Worker.connect_to_head()
   - ray start --address HEAD_IP:RAY_PORT
   - 收集资源信息
   - POST /connect_worker

3. Head 节点处理
   - Orchestrator.add_worker()
   - MessageBus.send_to_scheduler(START_WORKER)
   - Scheduler -> ResourceManager.add_node()

4. Worker 运行
   - Ray 任务在 Worker 上执行

5. Worker 停止
   - POST /disconnect_worker
   - Orchestrator.remove_worker()
   - ResourceManager.remove_node()
```
