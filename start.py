import subprocess
import sys
import time

processes = [
    [sys.executable, "bot.py"],
    [sys.executable, "stories_worker.py"],
    [sys.executable, "-m", "uvicorn", "web_server:app", "--host", "0.0.0.0", "--port", "10000"],
]

running = []

for cmd in processes:
    running.append(subprocess.Popen(cmd))
    time.sleep(2)

for p in running:
    p.wait()