"""
Utility functions for GPU information collection.
"""
import subprocess
from typing import List, Dict, Any


def collect_gpu_info() -> List[Dict[str, Any]]:
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=index,name,utilization.gpu,memory.total,memory.used,memory.free",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        
        if result.returncode != 0:
            return []
        
        output = result.stdout.decode("utf-8")
        lines = output.strip().split("\n")
        
        gpus = []
        for line in lines:
            if not line.strip():
                continue
            
            values = [v.strip() for v in line.split(",")]
            if len(values) < 6:
                continue
            
            gpus.append({
                "index": int(values[0]),
                "name": values[1],
                "utilization": int(values[2]),
                "memory_total": int(values[3]),
                "memory_used": int(values[4]),
                "memory_free": int(values[5]),
            })
        
        return gpus
    except Exception:
        return []
