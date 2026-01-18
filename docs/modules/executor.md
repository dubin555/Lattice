# Executor 模块文档

本文档详细描述 `lattice/executor/` 模块的设计和实现。

## 目录

- [1. 概述](#1-概述)
- [2. ExecutorBackend 抽象](#2-executorbackend-抽象)
- [3. RayExecutor](#3-rayexecutor)
- [4. LocalExecutor](#4-localexecutor)
- [5. Sandbox 沙箱执行](#5-sandbox-沙箱执行)
- [6. CodeRunner](#6-coderunner)

---

## 1. 概述

Executor 模块负责任务的实际执行，提供：

- **可插拔的执行后端** - 支持 Ray 分布式和本地执行
- **安全沙箱** - 多级隔离保护
- **代码运行器** - 执行用户代码

### 模块结构

```
executor/
├── __init__.py
├── base.py           # ExecutorBackend 抽象
├── factory.py        # 执行器工厂
├── ray_executor.py   # Ray 执行器
├── local_executor.py # 本地执行器
├── sandbox.py        # 沙箱执行环境
└── runner.py         # 代码运行器
```

---

## 2. ExecutorBackend 抽象

位置：`executor/base.py`

### 2.1 抽象基类

```python
class ExecutorBackend(ABC):
    @abstractmethod
    def initialize(self) -> None:
        """初始化执行器"""
        pass

    @abstractmethod
    def submit(self, submission: TaskSubmission) -> TaskHandle:
        """
        提交任务执行。

        Args:
            submission: 任务提交对象

        Returns:
            TaskHandle: 任务句柄，用于后续操作
        """
        pass

    @abstractmethod
    def get_result(self, handle: TaskHandle) -> Any:
        """
        获取任务结果（阻塞）。

        Args:
            handle: 任务句柄

        Returns:
            任务执行结果

        Raises:
            TaskError: 任务执行失败
            TaskCancelledError: 任务被取消
            NodeFailedError: 执行节点失效
        """
        pass

    @abstractmethod
    def wait(
        self,
        handles: List[TaskHandle],
        timeout: float = 0,
    ) -> tuple[List[TaskHandle], List[TaskHandle]]:
        """
        等待任务完成。

        Args:
            handles: 任务句柄列表
            timeout: 超时时间（0 表示不等待，立即返回）

        Returns:
            (done, pending): 已完成和待处理的句柄列表
        """
        pass

    @abstractmethod
    def cancel(self, handle: TaskHandle) -> bool:
        """
        取消任务。

        Args:
            handle: 任务句柄

        Returns:
            是否取消成功
        """
        pass

    @abstractmethod
    def shutdown(self) -> None:
        """关闭执行器"""
        pass

    @abstractmethod
    def get_available_resources(self) -> Dict[str, Any]:
        """获取可用资源信息"""
        pass
```

### 2.2 TaskSubmission

任务提交数据结构。

```python
@dataclass
class TaskSubmission:
    func: Callable              # 要执行的函数
    args: tuple = ()            # 位置参数
    kwargs: Dict[str, Any] = None  # 关键字参数
    resources: Dict[str, Any] = None  # 资源需求
    node_id: Optional[str] = None  # 目标节点 ID
    gpu_id: Optional[int] = None   # 目标 GPU ID
```

### 2.3 TaskHandle

任务句柄，用于追踪和操作任务。

```python
@dataclass
class TaskHandle:
    handle_id: Any              # 底层句柄（如 Ray ObjectRef）
    executor_type: ExecutorType # 执行器类型
```

### 2.4 ExecutorType

```python
class ExecutorType(Enum):
    RAY = "ray"
    LOCAL = "local"
```

### 2.5 异常类型

```python
class TaskError(Exception):
    """任务执行失败"""
    pass

class TaskCancelledError(Exception):
    """任务被取消"""
    pass

class NodeFailedError(Exception):
    """执行节点失效"""
    pass
```

---

## 3. RayExecutor

位置：`executor/ray_executor.py`

### 3.1 概述

基于 Ray 的分布式执行器，特性：

- 分布式任务执行
- 节点亲和性调度
- GPU 资源分配
- 任务取消支持

### 3.2 实现

```python
@ray.remote(max_retries=0)
def _execute_task(func, args, kwargs, cuda_visible_devices: Optional[str] = None):
    """Ray remote 函数，在 Worker 上执行"""
    if cuda_visible_devices:
        os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
    return func(*args, **kwargs)


class RayExecutor(ExecutorBackend):
    def __init__(self, ray_head_port: int = 6379, start_ray: bool = True):
        self._ray_head_port = ray_head_port
        self._start_ray = start_ray
        self._initialized = False

    def initialize(self) -> None:
        """
        初始化 Ray 执行器：
        1. 启动 Ray head（如果需要）
        2. 连接到 Ray 集群
        """
        if self._start_ray:
            self._launch_ray_head()
        ray.init(address="auto", ignore_reinit_error=True)
        self._initialized = True

    def _launch_ray_head(self) -> None:
        """启动 Ray head 节点"""
        subprocess.run(
            ["ray", "start", "--head", "--port", str(self._ray_head_port)],
            check=True,
        )

    def submit(self, submission: TaskSubmission) -> TaskHandle:
        """
        提交任务到 Ray：
        1. 解析资源需求（CPU/GPU/内存）
        2. 配置节点亲和性（如果指定）
        3. 设置 CUDA_VISIBLE_DEVICES（如果指定 GPU）
        4. 提交 remote 函数
        """
        resources = submission.resources or {}
        options = {
            "num_cpus": resources.get("cpu", 1),
        }

        if resources.get("cpu_mem", 0) > 0:
            options["memory"] = resources["cpu_mem"]

        if resources.get("gpu", 0) > 0:
            options["num_gpus"] = resources["gpu"]

        if submission.node_id:
            options["scheduling_strategy"] = (
                ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
                    node_id=submission.node_id,
                    soft=False,  # 硬亲和性
                )
            )

        cuda_devices = str(submission.gpu_id) if submission.gpu_id is not None else None

        ref = _execute_task.options(**options).remote(
            submission.func,
            submission.args,
            submission.kwargs,
            cuda_devices,
        )

        return TaskHandle(handle_id=ref, executor_type=ExecutorType.RAY)

    def get_result(self, handle: TaskHandle) -> Any:
        """获取 Ray 任务结果"""
        try:
            return ray.get(handle.handle_id)
        except ray.exceptions.RayTaskError as e:
            raise TaskError(str(e)) from e
        except ray.exceptions.TaskCancelledError as e:
            raise TaskCancelledError(str(e)) from e
        except (ray.exceptions.NodeDiedError, ray.exceptions.ObjectLostError) as e:
            raise NodeFailedError(str(e)) from e

    def wait(
        self,
        handles: List[TaskHandle],
        timeout: float = 0,
    ) -> tuple[List[TaskHandle], List[TaskHandle]]:
        """等待 Ray 任务完成"""
        refs = [h.handle_id for h in handles]
        ref_to_handle = {h.handle_id: h for h in handles}

        done_refs, pending_refs = ray.wait(
            refs,
            num_returns=len(refs),
            timeout=timeout if timeout > 0 else None,
        )

        done = [ref_to_handle[r] for r in done_refs]
        pending = [ref_to_handle[r] for r in pending_refs]
        return done, pending

    def cancel(self, handle: TaskHandle) -> bool:
        """取消 Ray 任务"""
        try:
            ray.cancel(handle.handle_id, force=True)
            return True
        except Exception:
            return False

    def shutdown(self) -> None:
        """停止 Ray"""
        subprocess.run(["ray", "stop"], check=True)

    def get_available_resources(self) -> Dict[str, Any]:
        """获取 Ray 集群资源"""
        resources = {"nodes": []}
        for node in ray.nodes():
            if node["Alive"]:
                resources["nodes"].append({
                    "node_id": node["NodeID"],
                    "node_ip": node["NodeManagerAddress"],
                    "cpu": node["Resources"].get("CPU", 0),
                    "memory": node["Resources"].get("memory", 0),
                    "gpu": node["Resources"].get("GPU", 0),
                })
        return resources
```

### 3.3 节点亲和性调度

Ray 支持将任务调度到指定节点：

```python
scheduling_strategy = ray.util.scheduling_strategies.NodeAffinitySchedulingStrategy(
    node_id="node-xxx",
    soft=False,  # soft=False 表示硬亲和性，必须在该节点执行
)
```

### 3.4 GPU 分配

通过设置 `CUDA_VISIBLE_DEVICES` 环境变量控制 GPU 可见性：

```python
# 在 remote 函数内
if cuda_visible_devices:
    os.environ["CUDA_VISIBLE_DEVICES"] = cuda_visible_devices
```

---

## 4. LocalExecutor

位置：`executor/local_executor.py`

### 4.1 概述

本地执行器，使用 `concurrent.futures.ThreadPoolExecutor`，适用于：

- 开发和测试
- 单机部署
- 不需要分布式的场景

### 4.2 实现

```python
class LocalExecutor(ExecutorBackend):
    def __init__(self, max_workers: int = None):
        self._max_workers = max_workers
        self._executor: ThreadPoolExecutor = None
        self._futures: Dict[int, Future] = {}
        self._counter = 0

    def initialize(self) -> None:
        self._executor = ThreadPoolExecutor(max_workers=self._max_workers)

    def submit(self, submission: TaskSubmission) -> TaskHandle:
        future = self._executor.submit(
            submission.func,
            *submission.args,
            **(submission.kwargs or {}),
        )
        handle_id = self._counter
        self._counter += 1
        self._futures[handle_id] = future
        return TaskHandle(handle_id=handle_id, executor_type=ExecutorType.LOCAL)

    def get_result(self, handle: TaskHandle) -> Any:
        future = self._futures.get(handle.handle_id)
        if future is None:
            raise TaskError("Task not found")
        try:
            return future.result()
        except Exception as e:
            raise TaskError(str(e)) from e

    def wait(
        self,
        handles: List[TaskHandle],
        timeout: float = 0,
    ) -> tuple[List[TaskHandle], List[TaskHandle]]:
        done, pending = [], []
        for handle in handles:
            future = self._futures.get(handle.handle_id)
            if future and future.done():
                done.append(handle)
            else:
                pending.append(handle)
        return done, pending

    def cancel(self, handle: TaskHandle) -> bool:
        future = self._futures.get(handle.handle_id)
        if future:
            return future.cancel()
        return False

    def shutdown(self) -> None:
        if self._executor:
            self._executor.shutdown(wait=False)

    def get_available_resources(self) -> Dict[str, Any]:
        import multiprocessing
        return {
            "nodes": [{
                "node_id": "local",
                "node_ip": "127.0.0.1",
                "cpu": multiprocessing.cpu_count(),
            }]
        }
```

---

## 5. Sandbox 沙箱执行

位置：`executor/sandbox.py`

### 5.1 概述

沙箱执行环境提供多级隔离，保护系统免受不可信代码影响。

### 5.2 隔离级别

| 级别 | 说明 | 平台 | 隔离性 | 性能 |
|------|------|------|--------|------|
| `NONE` | 直接执行 | 全平台 | 无 | 最快 |
| `SUBPROCESS` | 独立进程 + 资源限制 | 全平台 | 低 | 快 |
| `SECCOMP` | 系统调用过滤 | Linux | 高 | 快 |
| `DOCKER` | 容器隔离 | 全平台 | 最高 | 较慢 |

```python
class SandboxLevel(Enum):
    NONE = "none"
    SUBPROCESS = "subprocess"
    SECCOMP = "seccomp"
    DOCKER = "docker"
```

### 5.3 SandboxConfig

```python
@dataclass
class SandboxConfig:
    level: SandboxLevel = SandboxLevel.SUBPROCESS
    timeout: int = 300                    # 执行超时（秒）
    max_memory_mb: int = 2048             # 最大内存（MB）
    max_cpu_time: int = 300               # 最大 CPU 时间（秒）
    allowed_imports: List[str] = None     # 允许的 import（未实现）
    docker_image: str = "python:3.11-slim"  # Docker 镜像
    network_enabled: bool = False         # 是否允许网络
    mount_paths: Dict[str, str] = field(default_factory=dict)  # 挂载路径
    allowed_syscalls: List[int] = None    # 允许的系统调用
```

### 5.4 SubprocessSandbox

使用独立子进程执行代码，提供：

- **进程隔离** - 独立地址空间
- **资源限制** - 通过 `resource` 模块限制内存和 CPU
- **超时控制** - 通过 `signal.alarm` 实现

```python
class SubprocessSandbox:
    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        在子进程中执行代码：
        1. 创建临时 Python 脚本
        2. 通过 stdin 传递输入数据
        3. 设置资源限制
        4. 执行并获取结果
        """
```

#### SECCOMP 模式

在 Linux 上，SECCOMP 模式额外提供：

- **系统调用过滤** - 只允许白名单中的系统调用
- **进程/文件数限制** - 限制子进程和打开文件数

```python
SYSCALL_WHITELIST = {
    "x86_64": [0, 1, 2, ...],  # read, write, open, ...
    "aarch64": [...],
}

def apply_seccomp_filter(allowed_syscalls=None):
    """
    应用 seccomp 过滤器：
    1. 构建 BPF 过滤规则
    2. 设置 NO_NEW_PRIVS
    3. 加载过滤器
    """
```

### 5.5 DockerSandbox

使用 Docker 容器执行代码，提供最强隔离：

```python
class DockerSandbox:
    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        """
        在 Docker 容器中执行代码：
        1. 创建临时脚本
        2. 构建 Docker 命令
        3. 执行并获取结果
        """
```

#### Docker 安全选项

```python
docker_cmd = [
    "docker", "run", "--rm", "-i",
    f"--memory={max_memory_mb}m",     # 内存限制
    "--cpus=1",                        # CPU 限制
    "--pids-limit=100",                # 进程数限制
    "--read-only",                     # 只读文件系统
    "--tmpfs=/tmp:size=100m",          # 临时文件系统
    "--network=none",                  # 禁用网络
    "--security-opt=no-new-privileges",  # 禁止提权
    "--cap-drop=ALL",                  # 移除所有能力
]
```

### 5.6 SandboxExecutor

沙箱执行器，统一接口。

```python
class SandboxExecutor:
    def __init__(self, config: SandboxConfig = None):
        self.config = config or SandboxConfig()
        self._sandbox = self._create_sandbox()

    def execute(
        self,
        code_str: Optional[str] = None,
        serialized_code: Optional[str] = None,
        task_input_data: Optional[Dict] = None,
    ) -> Dict[str, Any]:
        if self.config.level == SandboxLevel.NONE:
            return self._execute_direct(...)
        return self._sandbox.execute(...)
```

### 5.7 全局配置

```python
# 设置全局沙箱配置
from lattice.executor.sandbox import set_sandbox_config, SandboxConfig, SandboxLevel

config = SandboxConfig(
    level=SandboxLevel.SECCOMP,
    timeout=300,
    max_memory_mb=2048,
)
set_sandbox_config(config)

# 获取全局配置
get_sandbox_config() -> SandboxConfig

# 获取执行器
get_sandbox_executor() -> SandboxExecutor
```

---

## 6. CodeRunner

位置：`executor/runner.py`

### 6.1 概述

代码运行器，用于执行用户提供的代码字符串。

### 6.2 实现

```python
class CodeRunner:
    def __init__(self, code_str: str, task_input_data: Dict[str, Any]):
        self.code_str = code_str
        self.task_input_data = task_input_data

    def run(self) -> Any:
        """
        执行代码字符串：
        1. 解析代码为 AST
        2. 提取函数定义和 import 语句
        3. 在隔离的命名空间中执行
        4. 调用函数并返回结果
        """
        import ast

        tree = ast.parse(self.code_str)

        # 提取函数定义
        func_node = None
        import_nodes = []
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                func_node = node
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                import_nodes.append(node)

        if func_node is None:
            raise ValueError("No function definition found")

        # 在隔离命名空间中执行
        namespace = {}

        # 执行 import
        for imp in import_nodes:
            module = ast.Module(body=[imp], type_ignores=[])
            exec(compile(module, '<string>', 'exec'), namespace)

        # 执行函数定义
        module = ast.Module(body=[func_node], type_ignores=[])
        exec(compile(module, '<string>', 'exec'), namespace)

        # 调用函数
        return namespace[func_node.name](self.task_input_data)
```

---

## 7. 执行器工厂

位置：`executor/factory.py`

```python
def create_executor(
    executor_type: ExecutorType,
    **kwargs,
) -> ExecutorBackend:
    """
    创建执行器实例。

    Args:
        executor_type: 执行器类型
        **kwargs: 执行器特定参数

    Returns:
        ExecutorBackend 实例
    """
    if executor_type == ExecutorType.RAY:
        return RayExecutor(**kwargs)
    elif executor_type == ExecutorType.LOCAL:
        return LocalExecutor(**kwargs)
    else:
        raise ValueError(f"Unknown executor type: {executor_type}")
```
