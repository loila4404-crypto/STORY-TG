import os
import sys
import subprocess
import threading

from fastapi import FastAPI
import uvicorn

app = FastAPI()


@app.get("/")
def root():
    return {"status": "worker alive"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.head("/health")
def health_head():
    return


def run_worker():
    subprocess.Popen([sys.executable, "-u", "stories_worker.py"]).wait()


if __name__ == "__main__":
    threading.Thread(target=run_worker, daemon=True).start()

    port = int(os.environ.get("PORT", "10000"))

    uvicorn.run(
        app,
        host="0.0.0.0",
        port=port
    )
