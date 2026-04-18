#!/usr/bin/env python3
"""
一键启动脚本：同时启动后端(FastAPI)和前端(Vite)
"""

import subprocess
import sys
import os
import signal
import atexit

processes = []


def cleanup():
    for p in processes:
        if p.poll() is None:
            p.terminate()
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()


atexit.register(cleanup)


def handle_signal(signum, frame):
    print("\n正在停止所有服务...")
    cleanup()
    sys.exit(0)


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def start_backend():
    print("[后端] 启动 FastAPI 服务 (http://127.0.0.1:8000) ...")
    venv_python = os.path.join(project_root, ".venv", "bin", "python")
    python = venv_python if os.path.exists(venv_python) else sys.executable
    p = subprocess.Popen(
        [python, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        cwd=project_root,
    )
    processes.append(p)
    return p


def start_frontend():
    print("[前端] 启动 Vite 开发服务器 (http://localhost:5173) ...")
    npm = "npm"
    p = subprocess.Popen(
        [npm, "run", "dev"],
        cwd=os.path.join(project_root, "frontend"),
    )
    processes.append(p)
    return p


if __name__ == "__main__":
    start_backend()
    start_frontend()

    print("\n" + "=" * 50)
    print("  服务已启动:")
    print("  前端: http://localhost:5173")
    print("  后端: http://127.0.0.1:8000")
    print("  API文档: http://127.0.0.1:8000/docs")
    print("  按 Ctrl+C 停止所有服务")
    print("=" * 50 + "\n")

    try:
        for p in processes:
            p.wait()
    except KeyboardInterrupt:
        handle_signal(None, None)
