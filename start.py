import subprocess
import sys
import time
import os

os.environ["PYTHONUNBUFFERED"] = "1"

print("Waiting before start...", flush=True)
time.sleep(5)

port = os.environ.get("PORT", "10000")

processes = [
    ["web", [
        sys.executable,
        "-u",
        "-m",
        "uvicorn",
        "web_server:app",
        "--host",
        "0.0.0.0",
        "--port",
        port
    ]],
    ["bot", [sys.executable, "-u", "bot.py"]],
    ["worker", [sys.executable, "-u", "stories_worker.py"]],
]

running = {}

for name, cmd in processes:
    print(f"Starting {name}: {' '.join(cmd)}", flush=True)
    running[name] = subprocess.Popen(cmd)
    time.sleep(2)

while True:
    for name, process in list(running.items()):
        code = process.poll()

        if code is not None:
            print(f"{name} stopped with code {code}. Restarting...", flush=True)
            cmd = dict(processes)[name]
            running[name] = subprocess.Popen(cmd)

    time.sleep(5)
