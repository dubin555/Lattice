# Client 模块文档

本文档详细描述 `lattice/client/` 模块的设计和实现。

## 目录

- [1. 概述](#1-概述)
- [2. LatticeClient](#2-latticeclient)
- [3. LatticeWorkflow](#3-latticeworkflow)
- [4. @task 装饰器](#4-task-装饰器)
- [5. LatticeTask 和 TaskOutput](#5-latticetask-和-taskoutput)
- [6. LangGraphClient](#6-langgraphclient)
- [7. 使用示例](#7-使用示例)

---

## 1. 概述

Client 模块是 Lattice 的用户 SDK，提供 Python API 用于：

- 连接 Lattice 服务器
- 定义和构建工作流
- 声明任务及其依赖
- 执行工作流并获取结果
- 集成 LangGraph 工作流

### 模块结构

```
client/
├── __init__.py           # 公开导出
├── core/
│   ├── __init__.py
│   ├── client.py         # LatticeClient
│   ├── workflow.py       # LatticeWorkflow
│   ├── decorator.py      # @task 装饰器
│   └── models.py         # LatticeTask, TaskOutput
└── langgraph/
    ├── __init__.py
    └── client.py         # LangGraphClient
```

---

## 2. LatticeClient

位置：`client/core/client.py`

### 2.1 概述

`LatticeClient` 是与 Lattice 服务器通信的主客户端。

```python
from lattice import LatticeClient

client = LatticeClient("http://localhost:8000")
workflow = client.create_workflow()
```

### 2.2 API

```python
class LatticeClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        创建客户端实例。

        Args:
            server_url: Lattice 服务器地址
        """

    def create_workflow(self) -> LatticeWorkflow:
        """
        创建新工作流。

        Returns:
            LatticeWorkflow 实例

        Raises:
            Exception: 创建失败
        """

    def get_workflow(self, workflow_id: str) -> LatticeWorkflow:
        """
        获取已存在的工作流。

        Args:
            workflow_id: 工作流 ID

        Returns:
            LatticeWorkflow 实例
        """

    def get_ray_head_port(self) -> int:
        """
        获取 Ray Head 节点端口。

        Returns:
            Ray 端口号
        """
```

### 2.3 HTTP 通信

客户端使用 `requests` 库与服务器通信：

| 方法 | 端点 | 说明 |
|------|------|------|
| POST | `/create_workflow` | 创建工作流 |
| POST | `/get_head_ray_port` | 获取 Ray 端口 |

---

## 3. LatticeWorkflow

位置：`client/core/workflow.py`

### 3.1 概述

`LatticeWorkflow` 是工作流构建器，用于添加任务、定义依赖、执行工作流。

```python
workflow = client.create_workflow()

# 添加任务
task1 = workflow.add_task(process_data, inputs={"data": raw_data})
task2 = workflow.add_task(analyze, inputs={"data": task1.outputs["result"]})

# 执行
run_id = workflow.run()
results = workflow.get_results(run_id)
```

### 3.2 API

```python
class LatticeWorkflow:
    def __init__(self, workflow_id: str, server_url: str):
        self.workflow_id = workflow_id
        self.server_url = server_url
        self._tasks: Dict[str, LatticeTask] = {}

    def add_task(
        self,
        task_func: Callable,
        inputs: Dict[str, Any] = None,
        task_name: str = None,
    ) -> LatticeTask:
        """
        添加任务到工作流。

        Args:
            task_func: 被 @task 装饰的函数
            inputs: 输入参数字典
                - 可以是直接值
                - 也可以是 TaskOutput 对象（表示依赖）
            task_name: 任务名称（可选，默认用函数名）

        Returns:
            LatticeTask 实例

        Raises:
            ValueError: task_func 未被 @task 装饰
        """

    def add_edge(self, source_task: LatticeTask, target_task: LatticeTask) -> None:
        """
        显式添加依赖边。

        通常不需要调用，add_task 会自动通过 TaskOutput 建立依赖。
        """

    def run(self) -> str:
        """
        执行工作流。

        Returns:
            run_id: 执行 ID

        Raises:
            Exception: 执行失败
        """

    def get_results(self, run_id: str, verbose: bool = True) -> List[Dict]:
        """
        获取工作流执行结果。

        通过 WebSocket 连接获取实时结果。

        Args:
            run_id: 执行 ID
            verbose: 是否打印结果

        Returns:
            结果列表，每个元素包含任务状态和输出
        """
```

### 3.3 内部实现

#### 任务输入构建

```python
def _build_task_input(self, inputs: Dict[str, Any], metadata) -> Dict:
    """
    构建任务输入配置。

    输入参数有两种来源：
    1. from_user: 直接值
    2. from_task: 来自其他任务的输出

    返回格式：
    {
        "input_params": {
            "1": {
                "key": "param_name",
                "input_schema": "from_user" | "from_task",
                "data_type": "str",
                "value": <直接值> | "task_id.output_key"
            }
        }
    }
    """
```

#### 依赖推断

当 `inputs` 中的值是 `TaskOutput` 对象时，自动建立依赖：

```python
if isinstance(input_value, TaskOutput):
    source_task_id = input_value.task_id
    workflow.add_edge(source_task_id, current_task_id)
```

### 3.4 HTTP/WebSocket 通信

| 协议 | 端点 | 说明 |
|------|------|------|
| POST | `/add_task` | 添加任务 |
| POST | `/save_task_and_add_edge` | 保存任务配置和依赖 |
| POST | `/add_edge` | 显式添加边 |
| POST | `/run_workflow` | 执行工作流 |
| WebSocket | `/get_workflow_res/{workflow_id}/{run_id}` | 获取结果 |

---

## 4. @task 装饰器

位置：`client/core/decorator.py`

### 4.1 概述

`@task` 装饰器用于声明 Lattice 任务的元数据。

```python
from lattice import task

@task(
    inputs=["query", "context"],
    outputs=["answer", "confidence"],
    resources={"cpu": 2, "gpu": 1, "gpu_mem": 4096},
    batch_size=10,
    batch_timeout=1.0,
)
def process(params):
    query = params["query"]
    context = params["context"]
    # ... 处理逻辑 ...
    return {"answer": result, "confidence": 0.95}
```

### 4.2 参数说明

| 参数 | 类型 | 说明 |
|------|------|------|
| `inputs` | `List[str]` | 输入参数名列表 |
| `outputs` | `List[str]` | 输出参数名列表 |
| `resources` | `Dict[str, Any]` | 资源需求 |
| `data_types` | `Dict[str, str]` | 数据类型提示（可选） |
| `batch_size` | `int` | 批处理大小（0 表示不批处理） |
| `batch_timeout` | `float` | 批处理超时（秒） |

#### resources 格式

```python
resources = {
    "cpu": 2,        # CPU 核心数
    "cpu_mem": 4096, # CPU 内存（MB）
    "gpu": 1,        # GPU 数量
    "gpu_mem": 8192, # GPU 显存（MB）
}
```

### 4.3 TaskMetadata

装饰器会在函数上附加 `_lattice_task_metadata` 属性：

```python
@dataclass
class TaskMetadata:
    func: Callable           # 原始函数
    func_name: str           # 函数名
    code_str: str            # 源代码字符串
    serialized_code: str     # cloudpickle 序列化的函数（base64）
    inputs: List[str]        # 输入参数名
    outputs: List[str]       # 输出参数名
    resources: Dict[str, Any]  # 资源需求
    data_types: Dict[str, str] # 数据类型
    batch_config: BatchConfig  # 批处理配置
```

### 4.4 BatchConfig

```python
@dataclass
class BatchConfig:
    enabled: bool = False      # 是否启用批处理
    batch_size: int = 1        # 批大小
    batch_timeout: float = 0.0 # 超时（秒）
```

批处理功能允许将多个相同类型的任务合并执行，适用于：
- GPU 推理任务
- 批量 API 调用
- 数据库批量操作

### 4.5 资源规范化

```python
def normalize_resources(resources: Dict) -> Dict:
    """
    规范化资源配置：
    1. 使用默认值填充缺失字段
    2. CPU 最小为 1
    3. 如果指定了 gpu_mem，gpu 至少为 1
    """
```

### 4.6 函数序列化

装饰器使用 `cloudpickle` 序列化函数：

```python
serialized_code = base64.b64encode(cloudpickle.dumps(func)).decode("utf-8")
```

这允许在分布式环境中传输和执行函数。

---

## 5. LatticeTask 和 TaskOutput

位置：`client/core/models.py`

### 5.1 LatticeTask

表示工作流中的一个任务。

```python
class LatticeTask:
    def __init__(
        self,
        task_id: str,
        workflow_id: str,
        server_url: str,
        task_name: str,
        output_keys: List[str],
    ):
        self.task_id = task_id
        self.workflow_id = workflow_id
        self.task_name = task_name
        self.outputs = {key: TaskOutput(task_id, key) for key in output_keys}
```

### 5.2 TaskOutput

表示任务的某个输出，用于建立依赖。

```python
class TaskOutput:
    def __init__(self, task_id: str, output_key: str):
        self.task_id = task_id
        self.output_key = output_key

    def to_reference_string(self) -> str:
        """返回 'task_id.output_key' 格式的引用字符串"""
        return f"{self.task_id}.{self.output_key}"
```

### 5.3 使用方式

```python
# task1 定义了输出 ["result", "metadata"]
task1 = workflow.add_task(process, inputs={"data": raw_data})

# task1.outputs 是一个字典：
# {
#     "result": TaskOutput(task1.task_id, "result"),
#     "metadata": TaskOutput(task1.task_id, "metadata")
# }

# 使用 TaskOutput 建立依赖
task2 = workflow.add_task(analyze, inputs={
    "data": task1.outputs["result"],  # TaskOutput 对象
    "meta": task1.outputs["metadata"],
})
```

---

## 6. LangGraphClient

位置：`client/langgraph/client.py`

### 6.1 概述

`LangGraphClient` 让 LangGraph 工作流无缝迁移到 Lattice，自动获得：
- 任务级并行
- 资源管理
- 分布式执行

```python
from lattice import LangGraphClient

client = LangGraphClient("http://localhost:8000")

@client.task(resources={"cpu": 2, "gpu": 1})
def process_node(state):
    # LangGraph 节点逻辑
    return {"processed": True}

# 在 LangGraph 工作流中使用
# process_node 会在 Lattice 上执行
```

### 6.2 API

```python
class LangGraphClient:
    def __init__(self, server_url: str = "http://localhost:8000"):
        """
        创建客户端并初始化工作流。

        自动调用 /create_workflow 创建一个 LangGraph 工作流。
        """

    def task(
        self,
        func_or_resources=None,
        *,
        resources: Dict[str, Any] = None,
    ):
        """
        装饰 LangGraph 节点函数。

        可以直接装饰：
            @client.task
            def my_node(state): ...

        或指定资源：
            @client.task(resources={"cpu": 2})
            def my_node(state): ...

        被装饰的函数在调用时会：
        1. 序列化参数
        2. 发送到 Lattice 服务器
        3. 在 Worker 上执行
        4. 返回结果
        """
```

### 6.3 工作原理

```
1. 客户端创建时
   POST /create_workflow
   -> workflow_id

2. 装饰函数时
   POST /add_langgraph_task
   {
       workflow_id,
       task_name: func.__name__,
       code_ser: base64(cloudpickle(func)),
       resources,
   }
   -> task_id

3. 调用函数时
   POST /run_langgraph_task
   {
       workflow_id,
       task_id,
       args: base64(cloudpickle(args)),
       kwargs: base64(cloudpickle(kwargs)),
   }
   -> result
```

### 6.4 同步设计

LangGraphClient 使用 **同步阻塞调用**，这是有意为之的设计：

- **外层 FastAPI 是异步的** - 多个请求可以并发处理
- **执行引擎 Ray 是异步的** - 任务在 Worker 上并行执行
- **LangGraph 调用点同步等待** - 符合正常函数调用语义

异步回调模式会增加复杂度（状态机、回调注册、结果拼装），而真正的并发已在上下两层解决。

---

## 7. 使用示例

### 7.1 基本工作流

```python
from lattice import LatticeClient, task

@task(inputs=["x"], outputs=["y"])
def double(params):
    return {"y": params["x"] * 2}

@task(inputs=["x"], outputs=["y"])
def square(params):
    return {"y": params["x"] ** 2}

@task(inputs=["a", "b"], outputs=["sum"])
def add(params):
    return {"sum": params["a"] + params["b"]}

# 创建客户端和工作流
client = LatticeClient("http://localhost:8000")
workflow = client.create_workflow()

# 添加任务（并行执行 double 和 square）
t1 = workflow.add_task(double, inputs={"x": 5})
t2 = workflow.add_task(square, inputs={"x": 5})

# 添加依赖任务
t3 = workflow.add_task(add, inputs={
    "a": t1.outputs["y"],  # 来自 double
    "b": t2.outputs["y"],  # 来自 square
})

# 执行
run_id = workflow.run()
results = workflow.get_results(run_id)
# 结果: sum = 10 + 25 = 35
```

### 7.2 带资源需求的任务

```python
@task(
    inputs=["text"],
    outputs=["embedding"],
    resources={"cpu": 2, "gpu": 1, "gpu_mem": 4096},
)
def embed(params):
    from transformers import AutoModel
    model = AutoModel.from_pretrained("bert-base")
    return {"embedding": model.encode(params["text"])}
```

### 7.3 批处理任务

```python
@task(
    inputs=["text"],
    outputs=["embedding"],
    resources={"gpu": 1},
    batch_size=32,        # 收集 32 个任务后批量执行
    batch_timeout=0.5,    # 或等待 0.5 秒后执行
)
def batch_embed(params):
    # params 是单个输入或输入列表（取决于是否批处理）
    return {"embedding": model.encode(params["text"])}
```

### 7.4 LangGraph 集成

```python
from lattice import LangGraphClient
from langgraph.graph import StateGraph

client = LangGraphClient("http://localhost:8000")

@client.task(resources={"cpu": 2})
def research(state):
    # 搜索相关信息
    return {"research_results": search(state["query"])}

@client.task(resources={"cpu": 2})
def analyze(state):
    # 分析数据
    return {"analysis": analyze_data(state["data"])}

@client.task(resources={"cpu": 1})
def synthesize(state):
    # 综合结果
    return {"answer": combine(state["research_results"], state["analysis"])}

# 构建 LangGraph 工作流
graph = StateGraph(State)
graph.add_node("research", research)
graph.add_node("analyze", analyze)
graph.add_node("synthesize", synthesize)
# ... 添加边 ...

# 执行时，research 和 analyze 会在 Lattice 上并行执行
app = graph.compile()
result = app.invoke({"query": "...", "data": "..."})
```
