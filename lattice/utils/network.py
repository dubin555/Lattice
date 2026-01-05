"""
Utility functions for networking.
"""
import socket
from typing import List


def get_available_ports(count: int = 1) -> List[int]:
    ports = []
    sockets = []
    
    try:
        for _ in range(count):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(("", 0))
            port = sock.getsockname()[1]
            ports.append(port)
            sockets.append(sock)
        return ports
    finally:
        for sock in sockets:
            sock.close()


def is_port_available(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.bind((host, port))
            return True
    except OSError:
        return False
