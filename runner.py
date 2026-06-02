import os
import sys
import uuid
import time
import traceback
import multiprocessing as mp
from multiprocessing import Queue, Process
from flask import Flask, render_template, request, jsonify

# ---------------------------
# Configuration
# ---------------------------
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
os.makedirs(SKILLS_DIR, exist_ok=True)

tasks = {}
task_queue = Queue()
lock = mp.Lock()

def is_safe_path(path):
    """Ensure the path is inside SKILLS_DIR (no directory traversal)."""
    abs_path = os.path.abspath(os.path.join(SKILLS_DIR, path))
    return abs_path.startswith(os.path.abspath(SKILLS_DIR))

def read_skill_file(relative_path):
    if not is_safe_path(relative_path):
        raise ValueError("Invalid path: outside skills directory")
    full_path = os.path.join(SKILLS_DIR, relative_path)
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"Skill file not found: {relative_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

# ---------------------------
# Worker (unchanged logic)
# ---------------------------
def worker(task_queue, tasks, lock):
    while True:
        task_id, code = task_queue.get()
        if task_id == "SHUTDOWN":
            break

        with lock:
            tasks[task_id]["status"] = "running"
            tasks[task_id]["started_at"] = time.time()

        exec_globals = {}
        try:
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, exec_globals)
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
# Flask app
# ---------------------------
app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/skills", methods=["GET"])
def list_skills():
    """Return a list of .py files under skills/ (recursive)."""
    skill_files = []
    for root, _, files in os.walk(SKILLS_DIR):
        for file in files:
            if file.endswith(".py"):
                rel_path = os.path.relpath(os.path.join(root, file), SKILLS_DIR)
                skill_files.append(rel_path)
    return jsonify(sorted(skill_files))

@app.route("/api/submit", methods=["POST"])
def submit_task():
    data = request.get_json()
    skill_path = data.get("skill_path", "").strip()
    if not skill_path:
        return jsonify({"error": "skill_path is required"}), 400

    try:
        code = read_skill_file(skill_path)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    task_id = str(uuid.uuid4())
    with lock:
        tasks[task_id] = {
            "status": "pending",
            "skill_path": skill_path,
            "submitted_at": time.time(),
        }
    task_queue.put((task_id, code))
    return jsonify({"task_id": task_id, "status": "pending"})

@app.route("/api/tasks", methods=["GET"])
def api_tasks():
    with lock:
        safe_tasks = {
            tid: {k: v for k, v in data.items() if k != "code"}
            for tid, data in tasks.items()
        }
    return jsonify(safe_tasks)

@app.route("/api/task/<task_id>", methods=["GET"])
def get_task(task_id):
    with lock:
        if task_id not in tasks:
            return jsonify({"error": "Task not found"}), 404
        task_data = tasks[task_id].copy()
        task_data.pop("code", None)
    return jsonify(task_data)

# ---------------------------
# Worker pool startup
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
    workers = start_workers(4)
    print(f"Workers started. Skills directory: {SKILLS_DIR}")
    print("Launching web UI at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

    for _ in workers:
        task_queue.put(("SHUTDOWN", None))
    for p in workers:
        p.join(timeout=2)import os
import sys
import uuid
import time
import traceback
import multiprocessing as mp
from multiprocessing import Queue, Process
from flask import Flask, render_template, request, jsonify

# ---------------------------
# Configuration
# ---------------------------
SKILLS_DIR = os.path.join(os.path.dirname(__file__), "skills")
os.makedirs(SKILLS_DIR, exist_ok=True)

tasks = {}
task_queue = Queue()
lock = mp.Lock()

def is_safe_path(path):
    """Ensure the path is inside SKILLS_DIR (no directory traversal)."""
    abs_path = os.path.abspath(os.path.join(SKILLS_DIR, path))
    return abs_path.startswith(os.path.abspath(SKILLS_DIR))

def read_skill_file(relative_path):
    if not is_safe_path(relative_path):
        raise ValueError("Invalid path: outside skills directory")
    full_path = os.path.join(SKILLS_DIR, relative_path)
    if not os.path.isfile(full_path):
        raise FileNotFoundError(f"Skill file not found: {relative_path}")
    with open(full_path, "r", encoding="utf-8") as f:
        return f.read()

# ---------------------------
# Worker (unchanged logic)
# ---------------------------
def worker(task_queue, tasks, lock):
    while True:
        task_id, code = task_queue.get()
        if task_id == "SHUTDOWN":
            break

        with lock:
            tasks[task_id]["status"] = "running"
            tasks[task_id]["started_at"] = time.time()

        exec_globals = {}
        try:
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, exec_globals)
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
# Flask app
# ---------------------------
app = Flask(__name__)

@app.route("/")
def dashboard():
    return render_template("dashboard.html")

@app.route("/api/skills", methods=["GET"])
def list_skills():
    """Return a list of .py files under skills/ (recursive)."""
    skill_files = []
    for root, _, files in os.walk(SKILLS_DIR):
        for file in files:
            if file.endswith(".py"):
                rel_path = os.path.relpath(os.path.join(root, file), SKILLS_DIR)
                skill_files.append(rel_path)
    return jsonify(sorted(skill_files))

@app.route("/api/submit", methods=["POST"])
def submit_task():
    data = request.get_json()
    skill_path = data.get("skill_path", "").strip()
    if not skill_path:
        return jsonify({"error": "skill_path is required"}), 400

    try:
        code = read_skill_file(skill_path)
    except (ValueError, FileNotFoundError) as e:
        return jsonify({"error": str(e)}), 400

    task_id = str(uuid.uuid4())
    with lock:
        tasks[task_id] = {
            "status": "pending",
            "skill_path": skill_path,
            "submitted_at": time.time(),
        }
    task_queue.put((task_id, code))
    return jsonify({"task_id": task_id, "status": "pending"})

@app.route("/api/tasks", methods=["GET"])
def api_tasks():
    with lock:
        safe_tasks = {
            tid: {k: v for k, v in data.items() if k != "code"}
            for tid, data in tasks.items()
        }
    return jsonify(safe_tasks)

@app.route("/api/task/<task_id>", methods=["GET"])
def get_task(task_id):
    with lock:
        if task_id not in tasks:
            return jsonify({"error": "Task not found"}), 404
        task_data = tasks[task_id].copy()
        task_data.pop("code", None)
    return jsonify(task_data)

# ---------------------------
# Worker pool startup
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
    workers = start_workers(4)
    print(f"Workers started. Skills directory: {SKILLS_DIR}")
    print("Launching web UI at http://localhost:5000")
    app.run(host="0.0.0.0", port=5000, debug=False)

    for _ in workers:
        task_queue.put(("SHUTDOWN", None))
    for p in workers:
        p.join(timeout=2)import os
import sys
import uuid
import time
import traceback
import threading
import multiprocessing as mp
from multiprocessing import Queue, Process
from flask import Flask, render_template, request, jsonify, abort

# ---------------------------
# Global registry of instances
# ---------------------------
instances = {}          # instance_name -> {'queue': Queue, 'tasks': dict, 'lock': Lock, 'workers': list}
instance_lock = mp.Lock()

def get_or_create_instance(name):
    """Get an existing instance or create a new one."""
    with instance_lock:
        if name not in instances:
            # Create new instance components
            task_queue = Queue()
            tasks = {}
            lock = mp.Lock()
            workers = start_workers(name, task_queue, tasks, lock, num_workers=2)  # default 2 workers per instance
            instances[name] = {
                'queue': task_queue,
                'tasks': tasks,
                'lock': lock,
                'workers': workers,
                'created_at': time.time()
            }
        return instances[name]

def shutdown_instance(name):
    """Gracefully shut down an instance's workers and remove it."""
    with instance_lock:
        if name not in instances:
            return False
        inst = instances[name]
        # Send shutdown to workers
        for _ in inst['workers']:
            inst['queue'].put(("SHUTDOWN", None))
        for p in inst['workers']:
            p.join(timeout=2)
        del instances[name]
        return True

def list_instances():
    with instance_lock:
        return list(instances.keys())

# ---------------------------
# Worker function (same as before, but uses instance's tasks/lock)
# ---------------------------
def worker(instance_name, task_queue, tasks, lock):
    """Runs tasks for a specific instance."""
    while True:
        task_id, code = task_queue.get()
        if task_id == "SHUTDOWN":
            break

        with lock:
            tasks[task_id]["status"] = "running"
            tasks[task_id]["started_at"] = time.time()

        exec_globals = {}
        try:
            import io
            from contextlib import redirect_stdout, redirect_stderr

            stdout_buffer = io.StringIO()
            stderr_buffer = io.StringIO()

            with redirect_stdout(stdout_buffer), redirect_stderr(stderr_buffer):
                exec(code, exec_globals)
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

def start_workers(instance_name, task_queue, tasks, lock, num_workers=2):
    processes = []
    for _ in range(num_workers):
        p = Process(target=worker, args=(instance_name, task_queue, tasks, lock))
        p.daemon = True
        p.start()
        processes.append(p)
    return processes

# ---------------------------
# Flask app with multi-instance support
# ---------------------------
app = Flask(__name__)

@app.route("/")
def dashboard():
    # Show instance selector and default to first instance
    inst_list = list_instances()
    current_instance = request.args.get('instance', inst_list[0] if inst_list else None)
    if current_instance not in inst_list and inst_list:
        current_instance = inst_list[0]
    return render_template("dashboard.html", instances=inst_list, current_instance=current_instance)

@app.route("/api/instances", methods=["GET"])
def api_instances():
    return jsonify({"instances": list_instances()})

@app.route("/api/instances", methods=["POST"])
def create_instance():
    data = request.get_json()
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"error": "Instance name required"}), 400
    if name in instances:
        return jsonify({"error": "Instance already exists"}), 409
    get_or_create_instance(name)  # creates it
    return jsonify({"instance": name, "status": "created"})

@app.route("/api/instances/<instance_name>", methods=["DELETE"])
def delete_instance(instance_name):
    if instance_name not in instances:
        return jsonify({"error": "Instance not found"}), 404
    shutdown_instance(instance_name)
    return jsonify({"status": "deleted"})

@app.route("/api/<instance_name>/tasks", methods=["GET"])
def api_tasks(instance_name):
    if instance_name not in instances:
        abort(404, description="Instance not found")
    inst = instances[instance_name]
    with inst['lock']:
        safe_tasks = {
            tid: {k: v for k, v in data.items() if k != "code"}
            for tid, data in inst['tasks'].items()
        }
    return jsonify(safe_tasks)

@app.route("/api/<instance_name>/submit", methods=["POST"])
def submit_task(instance_name):
    if instance_name not in instances:
        abort(404, description="Instance not found")
    data = request.get_json()
    code = data.get("code", "")
    if not code.strip():
        return jsonify({"error": "Empty code"}), 400

    inst = instances[instance_name]
    task_id = str(uuid.uuid4())
    with inst['lock']:
        inst['tasks'][task_id] = {
            "status": "pending",
            "code": code,
            "submitted_at": time.time(),
        }
    inst['queue'].put((task_id, code))
    return jsonify({"task_id": task_id, "status": "pending", "instance": instance_name})

@app.route("/api/<instance_name>/task/<task_id>", methods=["GET"])
def get_task(instance_name, task_id):
    if instance_name not in instances:
        abort(404, description="Instance not found")
    inst = instances[instance_name]
    with inst['lock']:
        if task_id not in inst['tasks']:
            return jsonify({"error": "Task not found"}), 404
        task_data = inst['tasks'][task_id].copy()
        task_data.pop("code", None)
    return jsonify(task_data)

# ---------------------------
# Startup: create a default instance
# ---------------------------
if __name__ == "__main__":
    # Create a default instance called "default"
    get_or_create_instance("default")
    print("Multi-instance runner ready. Default instance: 'default'")
    print("Create new instances via POST /api/instances with {\"name\": \"myinstance\"}")
    app.run(host="0.0.0.0", port=5000, debug=False)
