import ctypes
import pandas as pd
import os
import streamlit as st # Retained for exception definition, must not be used directly

# --- Error Handling Setup ---
class SchedulerLoadError(Exception):
    """Custom exception raised when the DLL fails to load."""
    pass

def run_scheduler_dummy(procs, n, algorithm_code, quantum, logs, max_logs):
    """Dummy function to raise a clear error if the DLL is not loaded."""
    raise SchedulerLoadError("The C++ scheduler.dll could not be loaded. Please ensure the file is in the project directory and compiled correctly.")

# 1. Define C Structures
class Process(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("at", ctypes.c_int),
        ("bt", ctypes.c_int),
        ("priority", ctypes.c_int),      
        ("ct", ctypes.c_int),
        ("tat", ctypes.c_int),
        ("wt", ctypes.c_int),
        ("rem_time", ctypes.c_int),
        ("first_run", ctypes.c_int),     
        ("base_priority", ctypes.c_int), 
        ("current_priority", ctypes.c_int),
        ("current_queue", ctypes.c_int), 
        ("last_q3_entry", ctypes.c_int),
    ]

class GanttLog(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("start", ctypes.c_int),
        ("finish", ctypes.c_int),
    ]

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


def solve_scheduling(processes_input, algorithm_name, quantum=2, mlq_assignments=None):
    n = len(processes_input)

    if n == 0:
        return pd.DataFrame(), []
    
    ProcessArray = Process * n
    c_procs = ProcessArray()
    
    # 0: FCFS, 1: SJF, 2: SRTF, 3: Prio-NP, 4: Prio-P, 5: RR, 6: MLFQ, 7: MLQ
    algo_map = {
        "FCFS": 0, "SJF (Non-Preemptive)": 1, "SRTF (Preemptive SJF)": 2, 
        "Priority (Non-Preemptive)": 3, "Priority (Preemptive)": 4, 
        "Round Robin": 5, "MLFQ (Multi-Level Feedback Queue)": 6,
        "MLQ (Multi-Level Queue)": 7 
    }
    algo_code = algo_map.get(algorithm_name, 0)
    
    processes = processes_input
    
    # --- MLQ Assignment Logic ---
    if algo_code == 7 and mlq_assignments:
        processes = []
        for p in processes_input:
            p_new = p.copy()
            # Assign the target queue ID (1, 2, or 3) from the Streamlit input
            # If the process isn't in mlq_assignments (shouldn't happen), default to Q3
            p_new['queue_assignment'] = mlq_assignments.get(p['pid'], 3) 
            processes.append(p_new)

    # Convert Python dicts to C structs
    for i, p in enumerate(processes):
        try:
            pid_num = int(str(p['pid']).replace('P', ''))
        except:
            pid_num = i + 1
            
        c_procs[i].pid = pid_num
        c_procs[i].at = int(p['at'])
        c_procs[i].bt = int(p['bt'])
        c_procs[i].rem_time = int(p['bt'])
        
        # Priority mapping: 
        if algo_code == 7:
            # For MLQ, we store the assigned Queue ID in the priority field for C++ initialization.
            c_procs[i].priority = int(p['queue_assignment'])
            c_procs[i].base_priority = int(p['priority']) # Store original priority separately
        else:
            # Standard priority scheduling
            c_procs[i].priority = int(p['priority'])
            c_procs[i].base_priority = int(p['priority'])
            
        
        # Initialize extended fields
        c_procs[i].current_priority = int(p['priority']) # Initial current priority
        c_procs[i].first_run = -1 
        c_procs[i].current_queue = -1
        c_procs[i].last_q3_entry = -1

    max_logs = 1000
    LogArray = GanttLog * max_logs
    c_logs = LogArray()

    # --- CALL C++ ---
    count = lib.run_scheduler(c_procs, n, algo_code, int(quantum), c_logs, max_logs)

    # --- Convert Results back to Python format ---
    
    final_data = []
    for i in range(n):
        p = c_procs[i]
        rt = p.first_run - p.at if p.first_run != -1 else 0
        
        final_pid_data = {
            "pid": f"P{p.pid}",
            "at": p.at,
            "bt": p.bt,
            "ct": p.ct,
            "tat": p.tat,
            "wt": p.wt,
            "rt": rt,
            "current_queue": p.current_queue,
            "status": "completed"
        }
        
        if algo_code == 7:
             # For MLQ, show the assigned queue as the priority for clarity
             final_pid_data['priority'] = p.current_queue 
        else:
             final_pid_data['priority'] = p.base_priority
             
        final_data.append(final_pid_data)
        
    final_df = pd.DataFrame(final_data)

    # 2. Timeline
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