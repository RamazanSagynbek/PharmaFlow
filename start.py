"""PharmaFlow launcher: start the warehouse server and open the HMI window.

    python start.py            # normal start
    python start.py --demo     # presentation mode: conveyor runs, orders arrive automatically
    python start.py --rebuild  # rebuild the HMI after changing frontend code

First run creates backend/.venv, installs Python dependencies and builds the HMI
(needs Node.js). Close the HMI window or press Ctrl+C here to stop the server.
"""
import argparse
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"
VENV = BACKEND / ".venv"
STATIC_INDEX = BACKEND / "app" / "static" / "index.html"
IS_WINDOWS = os.name == "nt"
VENV_PYTHON = VENV / ("Scripts/python.exe" if IS_WINDOWS else "bin/python")


def step(msg: str) -> None:
    print(f"\033[92m▶\033[0m {msg}", flush=True)


def run(cmd: list[str], cwd: Path) -> None:
    subprocess.run(cmd, cwd=cwd, check=True, shell=IS_WINDOWS and cmd[0] == "npm")


def ensure_backend() -> None:
    marker = VENV / ".deps-installed"
    requirements = BACKEND / "requirements.txt"
    if not VENV_PYTHON.exists():
        step("Создаю виртуальное окружение Python…")
        run([sys.executable, "-m", "venv", str(VENV)], BACKEND)
    if not marker.exists() or marker.stat().st_mtime < requirements.stat().st_mtime:
        step("Устанавливаю зависимости бэкенда…")
        run([str(VENV_PYTHON), "-m", "pip", "install", "-q", "-r", str(requirements)], BACKEND)
        marker.touch()


def ensure_hmi(rebuild: bool) -> None:
    if STATIC_INDEX.exists() and not rebuild:
        return
    if shutil.which("npm") is None:
        sys.exit("Для сборки HMI нужен Node.js (https://nodejs.org). Установите его и запустите снова.")
    if not (FRONTEND / "node_modules").exists():
        step("Устанавливаю зависимости HMI…")
        run(["npm", "install", "--no-audit", "--no-fund"], FRONTEND)
    step("Собираю HMI…")
    run(["npm", "run", "build"], FRONTEND)


def free_port(preferred: int) -> int:
    for port in range(preferred, preferred + 20):
        with socket.socket() as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    sys.exit("Нет свободного порта")


def wait_ready(url: str, timeout: float = 30) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(f"{url}/api/health", timeout=1):
                return
        except OSError:
            time.sleep(0.3)
    sys.exit("Сервер не запустился, смотрите сообщения выше.")


def find_app_browser() -> str | None:
    """Edge or Chrome can open a page as a standalone app window (no tabs/address bar)."""
    candidates = [shutil.which(n) for n in ("msedge", "chrome", "google-chrome", "chromium")]
    if IS_WINDOWS:
        for env in ("PROGRAMFILES(X86)", "PROGRAMFILES", "LOCALAPPDATA"):
            base = os.environ.get(env)
            if base:
                candidates += [
                    str(Path(base) / "Microsoft/Edge/Application/msedge.exe"),
                    str(Path(base) / "Google/Chrome/Application/chrome.exe"),
                ]
    return next((c for c in candidates if c and Path(c).exists()), None)


def open_hmi(url: str) -> subprocess.Popen | None:
    browser = find_app_browser()
    if browser:
        profile = BACKEND / ".hmi-profile"
        return subprocess.Popen([
            browser, f"--app={url}", "--window-size=1600,920", "--window-position=40,30",
            f"--user-data-dir={profile}", "--no-first-run", "--no-default-browser-check",
        ])
    webbrowser.open(url)
    return None


def main() -> None:
    parser = argparse.ArgumentParser(description="PharmaFlow HMI launcher")
    parser.add_argument("--demo", action="store_true", help="режим презентации")
    parser.add_argument("--rebuild", action="store_true", help="пересобрать HMI")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()

    ensure_backend()
    ensure_hmi(args.rebuild)

    port = free_port(args.port)
    base = f"http://localhost:{port}"
    env = {**os.environ, "PF_SIM_SPEED": os.environ.get("PF_SIM_SPEED", "5")}
    step(f"Запускаю сервер склада на {base}")
    server = subprocess.Popen(
        [str(VENV_PYTHON), "-m", "uvicorn", "app.main:app", "--port", str(port), "--log-level", "warning"],
        cwd=BACKEND, env=env,
    )
    try:
        wait_ready(base)
        url = base + ("/?demo=1" if args.demo else "/")
        step(f"Открываю HMI: {url}")
        window = open_hmi(url)
        print("   API и документация: " + base + "/docs")
        print("   Остановить: закройте окно HMI или нажмите Ctrl+C\n")
        if window:
            window.wait()  # app window closed -> stop the server
        else:
            server.wait()
    except KeyboardInterrupt:
        pass
    finally:
        server.terminate()
        server.wait(timeout=10)
        step("Склад остановлен.")


if __name__ == "__main__":
    main()
