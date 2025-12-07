import ctypes
import pandas as pd
import os
import streamlit as st # Keep this for the error handler, but define the exception correctly

# 1. Define C Structures
class Process(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("at", ctypes.c_int),
        ("bt", ctypes.c_int),
        ("priority", ctypes.c_int),      # Base priority from input
        ("ct", ctypes.c_int),
        ("tat", ctypes.c_int),
        ("wt", ctypes.c_int),
        ("rem_time", ctypes.c_int),
        
        # --- NEW FIELDS FOR AGING/RT ---
        ("first_run", ctypes.c_int),     # Time when the process first ran
        ("base_priority", ctypes.c_int), # Original priority (used for comparison)
        ("current_priority", ctypes.c_int), # Aged priority
    ]

class GanttLog(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("start", ctypes.c_int),
        ("finish", ctypes.c_int),
    ]

# --- Error Handling Setup ---
class SchedulerLoadError(Exception):
    """Custom exception raised when the DLL fails to load."""
    pass

def run_scheduler_dummy(procs, n, algorithm_code, quantum, logs, max_logs):
    """Dummy function to raise a clear error if the DLL is not loaded."""
    raise SchedulerLoadError("The C++ scheduler.dll could not be loaded. Please ensure the file is in the project directory and compiled correctly.")

# 2. Load Library
dll_path = os.path.abspath("scheduler.dll")
lib = None
dll_loaded = False

try:
    lib = ctypes.CDLL(dll_path)
    dll_loaded = True
except Exception as e:
    print(f"Error loading scheduler.dll: {e}. Using dummy scheduler.")
    class DummyLib:
        run_scheduler = run_scheduler_dummy
    lib = DummyLib()

# 3. Define function signature
if dll_loaded:
    lib.run_scheduler.argtypes = [
        ctypes.POINTER(Process), ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.POINTER(GanttLog), ctypes.c_int
    ]
    lib.run_scheduler.restype = ctypes.c_int


def solve_scheduling(processes, algorithm_name, quantum=2):
    n = len(processes)

    if n == 0:
        return pd.DataFrame(), []
    
    ProcessArray = Process * n
    c_procs = ProcessArray()
    
    for i, p in enumerate(processes):
        try:
            pid_num = int(str(p['pid']).replace('P', ''))
        except:
            pid_num = i + 1
            
        c_procs[i].pid = pid_num
        c_procs[i].at = int(p['at'])
        c_procs[i].bt = int(p['bt'])
        c_procs[i].priority = int(p['priority'])
        c_procs[i].rem_time = int(p['bt'])
        # Initialize new fields (important for the C++ side to read zeros/defaults)
        c_procs[i].first_run = -1 
        c_procs[i].base_priority = int(p['priority'])
        c_procs[i].current_priority = int(p['priority'])


    # Map Algorithm Name to Code
    algo_map = {
        "FCFS": 0, "SJF (Non-Preemptive)": 1, "SRTF (Preemptive SJF)": 2, 
        "Priority (Non-Preemptive)": 3, "Priority (Preemptive)": 4, "Round Robin": 5
    }
    algo_code = algo_map.get(algorithm_name, 0)

    max_logs = 1000
    LogArray = GanttLog * max_logs
    c_logs = LogArray()

    # --- CALL C++ ---
    count = lib.run_scheduler(c_procs, n, algo_code, int(quantum), c_logs, max_logs)

    # --- Convert Results back to Python format ---
    
    final_data = []
    for i in range(n):
        p = c_procs[i]
        
        # Calculate Response Time (RT)
        rt = p.first_run - p.at if p.first_run != -1 else 0
        
        final_data.append({
            "pid": f"P{p.pid}",
            "at": p.at,
            "bt": p.bt,
            "priority": p.priority,
            "ct": p.ct,
            "tat": p.tat,
            "wt": p.wt,
            "rt": rt,         # NEW METRIC
            "status": "completed"
        })
    final_df = pd.DataFrame(final_data)

    # 2. Timeline (remains the same)
    timeline = []
    for i in range(count):
        l = c_logs[i]
        task_name = "Idle" if l.pid == -1 else f"P{l.pid}"
        timeline.append({
            "Task": task_name,
            "Start": l.start,
            "Finish": l.finish,
            "Resource": task_name
        })

    return final_df, timeline