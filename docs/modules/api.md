# API 模块文档

本文档详细描述 `lattice/api/` 模块的设计和实现。

## 目录

- [1. 概述](#1-概述)
- [2. Server](#2-server)
- [3. Routes](#3-routes)
- [4. Models (Schemas)](#4-models-schemas)
- [5. API 参考](#5-api-参考)

---

## 1. 概述

API 模块基于 FastAPI 实现，提供：

- RESTful API 端点
- WebSocket 实时通信
- 请求/响应模型验证
- CORS 支持
- 可观测性集成

### 模块结构

```
api/
├── __init__.py
├── server.py         # 应用工厂和生命周期
├── models/
│   ├── __init__.py
│   └── schemas.py    # Pydantic 模型
└── routes/
    ├── __init__.py
    ├── workflow.py   # 工作流 API
    ├── langgraph.py  # LangGraph API
    └── worker.py     # Worker API
```

---

## 2. Server

位置：`api/server.py`

### 2.1 OrchestratorManager

单例管理器，确保 Orchestrator 全局唯一。

```python
class OrchestratorManager:
    _instance: Optional[Orchestrator] = None

    @classmethod
    def initialize(cls, ray_head_port: int = 6379) -> Orchestrator:
        """初始化 Orchestrator（如果尚未初始化）"""
        if cls._instance is None:
            cls._instance = Orchestrator(ray_head_port=ray_head_port)
            cls._instance.initialize()
        return cls._instance

    @classmethod
    def get(cls) -> Orchestrator:
        """获取 Orchestrator 实例"""
        if cls._instance is None:
            raise RuntimeError("Orchestrator not initialized")
        return cls._instance

    @classmethod
    def cleanup(cls) -> None:
        """清理 Orchestrator"""
        if cls._instance is not None:
            cls._instance.cleanup()
            cls._instance = None
```

### 2.2 应用工厂

```python
def create_app(
    ray_head_port: int = 6379,
    metrics_enabled: bool = True,
    metrics_exporter: str = "prometheus",
    metrics_endpoint: Optional[str] = None,
) -> FastAPI:
    """
    创建和配置 FastAPI 应用。

    Args:
        ray_head_port: Ray head 节点端口
        metrics_enabled: 是否启用指标收集
        metrics_exporter: 指标导出器类型 ("prometheus", "otlp", "otlp_http", "console")
        metrics_endpoint: OTLP 端点 URL

    Returns:
        配置好的 FastAPI 应用

    功能：
    1. 初始化 Orchestrator
    2. 设置路由到各路由模块
    3. 注册路由
    4. 配置指标中间件
    5. 注册信号处理器
    """
```

### 2.3 应用配置

```python
app = FastAPI(
    title="Lattice API",
    description="Task-level distributed framework for LLM agents",
    version="2.0.0",
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2.4 生命周期管理

```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    orchestrator = OrchestratorManager.get()
    await orchestrator.start_monitor()  # 启动消息监听
    yield
    OrchestratorManager.cleanup()       # 清理资源
    shutdown_metrics()                   # 关闭指标

# 事件处理器
app.add_event_handler("startup", startup_event)
app.add_event_handler("shutdown", shutdown_event)
```

### 2.5 信号处理

```python
def signal_handler(signum, frame):
    """处理 SIGTERM 和 SIGINT"""
    OrchestratorManager.cleanup()
    shutdown_metrics()

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)
```

---

## 3. Routes

### 3.1 Workflow Routes

位置：`api/routes/workflow.py`

工作流管理 API。

```python
router = APIRouter(tags=["workflow"])

# 全局 Orchestrator 引用
_orchestrator = None

def set_orchestrator(orchestrator):
    """由 create_app 调用，设置 Orchestrator"""
    global _orchestrator
    _orchestrator = orchestrator

def get_orchestrator():
    """获取 Orchestrator，如果未设置则抛出异常"""
```

#### 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/create_workflow` | 创建工作流 |
| POST | `/add_task` | 添加任务 |
| POST | `/save_task` | 保存任务配置 |
| POST | `/save_task_and_add_edge` | 保存任务并添加依赖边 |
| POST | `/add_edge` | 添加依赖边 |
| POST | `/del_edge` | 删除依赖边 |
| POST | `/del_task` | 删除任务 |
| GET | `/get_workflow_tasks/{workflow_id}` | 获取工作流任务列表 |
| POST | `/run_workflow` | 执行工作流 |
| WebSocket | `/get_workflow_res/{workflow_id}/{run_id}` | 获取执行结果 |

### 3.2 LangGraph Routes

位置：`api/routes/langgraph.py`

LangGraph 集成 API。

```python
router = APIRouter(tags=["langgraph"])
```

#### 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/add_langgraph_task` | 添加 LangGraph 任务 |
| POST | `/run_langgraph_task` | 执行 LangGraph 任务 |

### 3.3 Worker Routes

位置：`api/routes/worker.py`

Worker 节点管理 API。

```python
router = APIRouter(tags=["worker"])
```

#### 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | `/connect_worker` | 注册 Worker 节点 |
| POST | `/disconnect_worker` | 注销 Worker 节点 |
| POST | `/get_head_ray_port` | 获取 Ray head 端口 |

---

## 4. Models (Schemas)

位置：`api/models/schemas.py`

使用 Pydantic 定义请求/响应模型。

### 4.1 工作流相关

```python
class CreateWorkflowResponse(BaseModel):
    status: str
    workflow_id: str

class AddTaskRequest(BaseModel):
    workflow_id: str
    task_type: str
    task_name: str

class AddTaskResponse(BaseModel):
    status: str
    task_id: str

class SaveTaskRequest(BaseModel):
    workflow_id: str
    task_id: str
    task_input: Dict[str, Any]
    task_output: Dict[str, Any]
    code_str: Optional[str] = None
    code_ser: Optional[str] = None
    resources: Optional[Dict[str, Any]] = None

class SaveTaskResponse(BaseModel):
    status: str

class AddEdgeRequest(BaseModel):
    workflow_id: str
    source_task_id: str
    target_task_id: str

class AddEdgeResponse(BaseModel):
    status: str

class RunWorkflowRequest(BaseModel):
    workflow_id: str

class RunWorkflowResponse(BaseModel):
    status: str
    run_id: str

class GetTasksResponse(BaseModel):
    status: str
    tasks: List[Dict[str, str]]
```

### 4.2 LangGraph 相关

```python
class AddLangGraphTaskRequest(BaseModel):
    workflow_id: str
    task_type: str
    task_name: str
    code_ser: str
    resources: Optional[Dict[str, Any]] = None

class RunLangGraphTaskRequest(BaseModel):
    workflow_id: str
    task_id: str
    args: str    # base64 序列化的参数
    kwargs: str  # base64 序列化的关键字参数

class RunLangGraphTaskResponse(BaseModel):
    status: str
    result: Any
```

### 4.3 Worker 相关

```python
class ConnectWorkerRequest(BaseModel):
    node_ip: str
    node_id: str
    resources: Dict[str, Any]

class DisconnectWorkerRequest(BaseModel):
    node_id: str

class GetRayPortResponse(BaseModel):
    port: int
```

---

## 5. API 参考

### 5.1 POST /create_workflow

创建新工作流。

**请求**：无

**响应**：
```json
{
    "status": "success",
    "workflow_id": "uuid"
}
```

### 5.2 POST /add_task

添加任务到工作流。

**请求**：
```json
{
    "workflow_id": "uuid",
    "task_type": "code",
    "task_name": "my_task"
}
```

**响应**：
```json
{
    "status": "success",
    "task_id": "uuid"
}
```

### 5.3 POST /save_task_and_add_edge

保存任务配置并根据输入自动添加依赖边。

**请求**：
```json
{
    "workflow_id": "uuid",
    "task_id": "uuid",
    "task_name": "my_task",
    "code_str": "def my_task(params): ...",
    "code_ser": "base64_serialized_function",
    "task_input": {
        "input_params": {
            "1": {
                "key": "data",
                "input_schema": "from_task",
                "data_type": "str",
                "value": "source_task_id.output_key"
            }
        }
    },
    "task_output": {
        "output_params": {
            "1": {
                "key": "result",
                "data_type": "str"
            }
        }
    },
    "resources": {
        "cpu": 2,
        "gpu": 1
    },
    "batch_config": {
        "enabled": true,
        "batch_size": 10,
        "batch_timeout": 1.0
    }
}
```

**响应**：
```json
{
    "status": "success"
}
```

### 5.4 POST /run_workflow

执行工作流。

**请求**：
```json
{
    "workflow_id": "uuid"
}
```

**响应**：
```json
{
    "status": "success",
    "run_id": "uuid"
}
```

### 5.5 WebSocket /get_workflow_res/{workflow_id}/{run_id}

通过 WebSocket 获取工作流执行结果。

**消息格式**：

任务开始：
```json
{
    "type": "start_task",
    "data": {
        "workflow_id": "uuid",
        "task_id": "uuid",
        "node_ip": "192.168.1.1",
        "node_id": "node-xxx"
    }
}
```

任务完成：
```json
{
    "type": "finish_task",
    "data": {
        "workflow_id": "uuid",
        "task_id": "uuid",
        "result": { "output_key": "value" }
    }
}
```

工作流完成：
```json
{
    "type": "finish_workflow",
    "data": {
        "run_id": "uuid"
    }
}
```

### 5.6 POST /add_langgraph_task

添加 LangGraph 任务。

**请求**：
```json
{
    "workflow_id": "uuid",
    "task_type": "langgraph",
    "task_name": "process_node",
    "code_ser": "base64_serialized_function",
    "resources": {
        "cpu": 2,
        "gpu": 1
    }
}
```

**响应**：
```json
{
    "status": "success",
    "task_id": "uuid"
}
```

### 5.7 POST /run_langgraph_task

执行 LangGraph 任务。

**请求**：
```json
{
    "workflow_id": "uuid",
    "task_id": "uuid",
    "args": "base64_serialized_args",
    "kwargs": "base64_serialized_kwargs"
}
```

**响应**：
```json
{
    "status": "success",
    "result": { "processed": true }
}
```

### 5.8 POST /connect_worker

注册 Worker 节点。

**请求**：
```json
{
    "node_ip": "192.168.1.100",
    "node_id": "node-xxx",
    "resources": {
        "cpu": 8,
        "cpu_mem": 16384,
        "gpu_resource": {
            "0": {
                "gpu_id": 0,
                "gpu_mem": 8192,
                "gpu_num": 1
            }
        }
    }
}
```

**响应**：
```json
{
    "status": "success"
}
```

### 5.9 POST /disconnect_worker

注销 Worker 节点。

**请求**：
```json
{
    "node_id": "node-xxx"
}
```

**响应**：
```json
{
    "status": "success"
}
```

### 5.10 POST /get_head_ray_port

获取 Ray head 节点端口。

**请求**：无

**响应**：
```json
{
    "port": 6379
}
```

---

## 6. 错误处理

所有端点在出错时返回 HTTP 错误码和详细信息：

```python
# 404 - 资源不存在
raise HTTPException(status_code=404, detail="Workflow not found")

# 400 - 请求错误
raise HTTPException(status_code=400, detail="Invalid task type")

# 500 - 服务器错误
raise HTTPException(status_code=500, detail=str(e))
```

### 自定义异常

```python
class WorkflowNotFoundError(Exception):
    def __init__(self, workflow_id: str):
        super().__init__(f"Workflow {workflow_id} not found")

class TaskNotFoundError(Exception):
    def __init__(self, task_id: str, workflow_id: str):
        super().__init__(f"Task {task_id} not found in workflow {workflow_id}")

class OrchestratorNotInitializedError(Exception):
    def __init__(self):
        super().__init__("Orchestrator not initialized")
```
