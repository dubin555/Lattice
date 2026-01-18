# Lattice 文档中心

欢迎阅读 Lattice 框架的技术文档。

## 文档结构

### 架构文档

- **[系统架构总览](./architecture.md)** - 整体架构设计、核心概念、设计决策

### 模块文档

- **[Core 模块](./modules/core.md)** - Orchestrator、Scheduler、ResourceManager、Workflow 等核心组件
- **[Client 模块](./modules/client.md)** - LatticeClient、LatticeWorkflow、@task 装饰器、LangGraphClient
- **[Executor 模块](./modules/executor.md)** - 执行器后端、沙箱执行环境
- **[API 模块](./modules/api.md)** - FastAPI 服务器、路由、请求/响应模型

### 交互文档

- **[模块交互](./modules/interactions.md)** - 工作流生命周期、任务执行流程、消息通信、资源管理

---

## 快速导航

### 我想了解...

| 主题 | 推荐文档 |
|------|----------|
| Lattice 是什么，解决什么问题 | [README.md](../README.md)、[架构总览](./architecture.md) |
| 整体架构和设计思路 | [架构总览](./architecture.md) |
| 如何使用 Lattice | [Client 模块](./modules/client.md)、[examples/](../examples/) |
| Orchestrator 和 Scheduler 的工作原理 | [Core 模块](./modules/core.md) |
| 任务是如何被调度和执行的 | [模块交互](./modules/interactions.md)、[Executor 模块](./modules/executor.md) |
| API 端点和请求格式 | [API 模块](./modules/api.md) |
| 沙箱执行和安全隔离 | [Executor 模块](./modules/executor.md) |
| 分布式部署和 Worker 管理 | [Core 模块](./modules/core.md)、[模块交互](./modules/interactions.md) |
| LangGraph 集成 | [Client 模块](./modules/client.md) |

---

## 架构概览图

```
┌─────────────────────────────────────────────────────────────────┐
│                        Client Layer                              │
│   LatticeClient, LatticeWorkflow, @task, LangGraphClient        │
└───────────────────────────────┬─────────────────────────────────┘
                                │ HTTP/WebSocket
┌───────────────────────────────┴─────────────────────────────────┐
│                        API Layer (FastAPI)                       │
│   /create_workflow, /add_task, /run_workflow, ...               │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────┐
│                        Core Layer                                │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Orchestrator (主线程)                                   │    │
│  │  - 工作流管理                                            │    │
│  │  - 执行上下文管理                                        │    │
│  └─────────────────────────────────────────────────────────┘    │
│                         ▲ MessageBus ▼                           │
│  ┌─────────────────────────────────────────────────────────┐    │
│  │  Scheduler (后台线程)                                    │    │
│  │  - 任务调度                                              │    │
│  │  - 资源分配 (ResourceManager)                            │    │
│  │  - 批处理 (BatchCollector)                               │    │
│  └─────────────────────────────────────────────────────────┘    │
└───────────────────────────────┬─────────────────────────────────┘
                                │
┌───────────────────────────────┴─────────────────────────────────┐
│                     Executor Layer (Ray)                         │
│   RayExecutor, LocalExecutor, Sandbox                           │
└───────────────────────────────┬─────────────────────────────────┘
                                │
              ┌─────────────────┼─────────────────┐
              ▼                 ▼                 ▼
         Worker 1          Worker 2          Worker N
```

---

## 目录结构

```
docs/
├── README.md              # 本文件 - 文档索引
├── architecture.md        # 系统架构总览
└── modules/
    ├── core.md           # Core 模块文档
    ├── client.md         # Client 模块文档
    ├── executor.md       # Executor 模块文档
    ├── api.md            # API 模块文档
    └── interactions.md   # 模块交互文档
```

---

## 代码结构

```
lattice/
├── api/            # FastAPI 服务器
├── cli/            # 命令行接口
├── client/         # 客户端 SDK
├── config/         # 配置
├── core/           # 核心运行时
│   ├── orchestrator/
│   ├── scheduler/
│   ├── resource/
│   ├── runtime/
│   ├── workflow/
│   └── worker/
├── executor/       # 执行器
├── llm/            # LLM 管理
├── observability/  # 可观测性
└── utils/          # 工具函数
```
