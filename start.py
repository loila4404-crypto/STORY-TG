import subprocess
import sys
import time
import os

os.environ["PYTHONUNBUFFERED"] = "1"

print("Waiting before start...", flush=True)
time.sleep(15)

processes = [
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
