import os
import sys
import uuid
import time
import traceback
import multiprocessing as mp
from multiprocessing import Queue, Process
from flask import Flask, render_template, request, jsonify

# ---------------------------
# Task storage & state
# ---------------------------
tasks = {}          # task_id -> {status, result, error, stdout}
task_queue = Queue()  # (task_id, code_string)
lock = mp.Lock()    # for safely updating tasks dict

# ---------------------------
# Worker function
# ---------------------------
def worker(task_queue, tasks, lock):
    """Runs in a separate process: picks tasks from the queue and executes them."""
    while True:
        task_id, code = task_queue.get()
        if task_id == "SHUTDOWN":
            break

        # Update status: running
        with lock:
            tasks[task_id]["status"] = "running"
            tasks[task_id]["started_at"] = time.time()

        # Prepare a fresh globals dict for isolated execution
        exec_globals = {}
        try:
            # Capture stdout/stderr (optional)
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, exec_globals)
                # If the code defines a 'run' function, call it
                if "run" in exec_globals and callable(exec_globals["run"]):
                    exec_globals["run"]()

            result = exec_globals.get("result", None)
            with lock:
                tasks[task_id]["status"] = "completed"
                tasks[task_id]["result"] = result
                tasks[task_id]["stdout"] = stdout_buffer.getvalue()
                tasks[task_id]["stderr"] = stderr_buffer.getvalue()
        except Exception as e:
            with lock:
                tasks[task_id]["status"] = "failed"
                tasks[task_id]["error"] = str(e)
                tasks[task_id]["traceback"] = traceback.format_exc()

# ---------------------------
# Flask web app
# ---------------------------
app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html", tasks=tasks)

@app.route("/api/tasks", methods=["GET"])
def api_tasks():
    with lock:
        # Return a copy of tasks for JSON serialization
        safe_tasks = {
            tid: {k: v for k, v in data.items() if k not in ("code",)}
            for tid, data in tasks.items()
        }
    return jsonify(safe_tasks)

@app.route("/api/submit", methods=["POST"])
def submit_task():
    data = request.get_json()
    code = data.get("code", "")
    if not code.strip():
        return jsonify({"error": "Empty code"}), 400

    task_id = str(uuid.uuid4())
    with lock:
        tasks[task_id] = {
            "status": "pending",
            "code": code,          # stored only for display, not sent to worker
            "submitted_at": time.time(),
        }
    task_queue.put((task_id, code))
    return jsonify({"task_id": task_id, "status": "pending"})

@app.route("/api/task/<task_id>", methods=["GET"])
def get_task(task_id):
    with lock:
        if task_id not in tasks:
            return jsonify({"error": "Task not found"}), 404
        task_data = tasks[task_id].copy()
        task_data.pop("code", None)
    return jsonify(task_data)

# ---------------------------
# Startup: create worker pool
# ---------------------------
def start_workers(n_workers=4):
    processes = []
    for _ in range(n_workers):
        p = Process(target=worker, args=(task_queue, tasks, lock))
        p.daemon = True
        p.start()
        processes.append(p)
    return processes

if __name__ == "__main__":
    # Start 4 worker processes
    workers = start_workers(4)
    print("Workers started. Launching web UI...")
    # Run Flask (use debug=False because multiprocessing can conflict)
    app.run(host="0.0.0.0", port=5000, debug=False)

    # On shutdown, signal workers to exit
    for _ in workers:
        task_queue.put(("SHUTDOWN", None))
    for p in workers:
        p.join(timeout=2)
