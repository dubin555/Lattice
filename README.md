<h2 align="center"><img src="./assets/imgs/image.png" style="height:1em; width:auto; vertical-align:middle"/> Lattice: A Distributed Framework for LLM Agents</h2>

<p align="center">
    <a href="https://latticeagent.net/">
        <img src="https://img.shields.io/badge/Website-latticeagent.net-blue?style=for-the-badge&logo=google-chrome&logoColor=white" alt="Website">
    </a>
    <a href="https://lattice-doc.readthedocs.io/en/latest/">
        <img src="https://img.shields.io/badge/Docs-ReadTheDocs-black?style=for-the-badge&logo=readthedocs&logoColor=white" alt="Documentation">
    </a>
    <a href="https://github.com/QinbinLi/Lattice/blob/main/LICENSE">
        <img src="https://img.shields.io/badge/License-MIT-green?style=for-the-badge" alt="License">
    </a>
</p>

<p align="center">
    <a href="./README_ZH.md">中文</a> | English
</p>

## 🌟 Why Lattice?

- **Task-level Parallelism**

  Lattice enables fine-grained, task-level management, enhancing system flexibility and composability while supporting task parallelism to significantly improve the end-to-end performance of agent workflows.

- **Resource Management**

  Lattice supports resource allocation for workflow tasks, effectively preventing resource contention both among parallel tasks within a single workflow and across multiple concurrently executing workflows.

- **Distributed Deployment**

  Lattice supports not only standalone but also distributed deployment, allowing you to build highly available and scalable Lattice clusters to meet the demands of large-scale concurrency and high-performance computing.

- **Sandbox Execution**

  Lattice provides secure task execution with multiple isolation levels (subprocess, seccomp, Docker), protecting your system from potentially malicious or buggy task code.

- **Multi-Agent Support**

  Lattice can serve as a runtime backend for other agent frameworks. For example, it allows LangGraph to be seamlessly migrated to Lattice and automatically gain task-level parallelism without modifying original logic.

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Lattice Client                           │
│  (LatticeClient, LatticeWorkflow, @task decorator, LangGraph)   │
└─────────────────────────────┬───────────────────────────────────┘
                              │ HTTP/WebSocket
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      Lattice Server (Head)                      │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │ FastAPI     │  │ Orchestrator│  │ Scheduler               │  │
│  │ (REST API)  │  │ (Lifecycle) │  │ (Task Queue + Dispatch) │  │
│  └─────────────┘  └─────────────┘  └─────────────────────────┘  │
│  ┌─────────────────────────────────────────────────────────────┐│
│  │              Resource Manager (CPU/GPU/Memory)              ││
│  └─────────────────────────────────────────────────────────────┘│
└─────────────────────────────┬───────────────────────────────────┘
                              │ Ray
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
   ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
   │   Worker 1  │     │   Worker 2  │     │   Worker N  │
   │  (Executor) │     │  (Executor) │     │  (Executor) │
   │  [Sandbox]  │     │  [Sandbox]  │     │  [Sandbox]  │
   └─────────────┘     └─────────────┘     └─────────────┘
```

## 🚀 Quick Start

### 1. Install

**From PyPI (Recommended)**

```bash
pip install lattice-agent
```

**From source**

```bash
git clone https://github.com/QinbinLi/Lattice.git
cd Lattice
pip install -e .
```

### 2. Launch Lattice

Launch Lattice Head as the server:

```bash
lattice start --head --port 8000
```

For distributed deployment, connect worker nodes:

```bash
lattice start --worker --addr HEAD_IP:HEAD_PORT
```

**With Sandbox (Recommended for untrusted code):**

```bash
# Enable seccomp sandbox (Linux, lightweight)
lattice start --head --port 8000 --sandbox seccomp

# Or subprocess sandbox (cross-platform)
lattice start --head --port 8000 --sandbox subprocess
```

### 3. Example

```python
from typing import Any
from lattice import LatticeClient, task

# 1. Define your task functions using the @task decorator
@task(inputs=["text"], outputs=["result"])
def my_task(params):
    text: Any = params.get("text")
    return {"result": f"Hello {text}"}

# 2. Create the lattice client
client = LatticeClient("http://localhost:8000")

# 3. Create the workflow
workflow = client.create_workflow()
task1 = workflow.add_task(
    my_task,
    inputs={"text": "Lattice"}
)

# 4. Submit the workflow and get results
run_id = workflow.run()
results = workflow.get_results(run_id)
print(results)  # {'result': 'Hello Lattice'}
```

### 4. LangGraph Integration

```python
from lattice import LangGraphClient

client = LangGraphClient("http://localhost:8000")

@client.task(cpu=2, memory=4096)
def process_data(state):
    # Your LangGraph node logic
    return {"processed": True}

# Use in your LangGraph workflow
# Tasks automatically gain parallelism and resource management
```

## 🛡️ Sandbox Isolation

Lattice provides multiple sandbox levels for secure task execution:

| Level | Platform | Isolation | Performance |
|-------|----------|-----------|-------------|
| `none` | All | No isolation | Fastest |
| `subprocess` | All | Separate process + resource limits | Fast |
| `seccomp` | Linux | Syscall filtering + resource limits | Fast |
| `docker` | All (requires Docker) | Full container isolation | Slower |

```python
# Configure sandbox programmatically
from lattice.executor.sandbox import set_sandbox_config, SandboxConfig, SandboxLevel

config = SandboxConfig(
    level=SandboxLevel.SECCOMP,
    timeout=300,
    max_memory_mb=2048,
)
set_sandbox_config(config)
```

## 🖥️ Lattice Playground

Build workflows through a drag-and-drop interface:

```bash
lattice start --head --port 8000 --playground
```

### Builtin Task Workflow
![Design Workflow Screenshot](https://meeting-agent1.oss-cn-beijing.aliyuncs.com/builtin_task.png)  
[Design Workflow Video](https://meeting-agent1.oss-cn-beijing.aliyuncs.com/builtin_task.mp4)

### User Defined Task Workflow
![Check Result Screenshot](https://meeting-agent1.oss-cn-beijing.aliyuncs.com/userdef_task.png)  
[Check Result Video](https://meeting-agent1.oss-cn-beijing.aliyuncs.com/userdef_task.mp4)

## 📊 Lattice Board

Monitor your Lattice cluster with the built-in dashboard:

- Real-time worker status and resource usage
- Workflow execution tracking
- Task-level metrics and logs

## 🧪 Testing

```bash
# Run unit tests
pytest tests/unit/ -v

# Run integration tests (requires running server)
lattice start --head --port 8000 &
pytest tests/integration/ -v -m integration
```

## 📁 Project Structure

```
lattice/
├── api/            # FastAPI server and routes
├── cli/            # Command-line interface
├── client/         # Client SDK (LatticeClient, LangGraphClient)
├── core/           # Core runtime (orchestrator, scheduler, resource)
├── executor/       # Task execution (Ray, sandbox)
├── llm/            # LLM instance management
└── utils/          # Utilities
web/
├── lattice_playground/  # Workflow designer (React + Node.js)
└── lattice_board/       # Monitoring dashboard (React)
```

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📚 Documentation

For detailed documentation, visit [Lattice Documentation](https://lattice-doc.readthedocs.io/en/latest/).
