import ctypes
import pandas as pd
import os

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
    ]

class GanttLog(ctypes.Structure):
    _fields_ = [
        ("pid", ctypes.c_int),
        ("start", ctypes.c_int),
        ("finish", ctypes.c_int),
    ]

# 2. Load Library
dll_path = os.path.abspath("scheduler.dll")
lib = ctypes.CDLL(dll_path)

# Define function signature
lib.run_scheduler.argtypes = [
    ctypes.POINTER(Process), # procs array
    ctypes.c_int,            # n
    ctypes.c_int,            # algo code
    ctypes.c_int,            # quantum
    ctypes.POINTER(GanttLog),# logs array
    ctypes.c_int             # max logs
]
lib.run_scheduler.restype = ctypes.c_int

def solve_scheduling(processes, algorithm_name, quantum=2):
    n = len(processes)
    ProcessArray = Process * n
    c_procs = ProcessArray()
    
    # Map PIDs (P1 -> 1, P2 -> 2) for C++ processing
    # We assume input PID format is "P#"
    for i, p in enumerate(processes):
        # Extract number from P1, P2 etc.
        try:
            pid_num = int(str(p['pid']).replace('P', ''))
        except:
            pid_num = i + 1 # Fallback
            
        c_procs[i].pid = pid_num
        c_procs[i].at = int(p['at'])
        c_procs[i].bt = int(p['bt'])
        c_procs[i].priority = int(p['priority'])
        c_procs[i].rem_time = int(p['bt'])

    # Map Algorithm Name to Code
    # 0: FCFS, 1: SJF, 2: SRTF, 3: Prio-NP, 4: Prio-P, 5: RR
    algo_map = {
        "FCFS": 0,
        "SJF (Non-Preemptive)": 1,
        "SRTF (Preemptive SJF)": 2,
        "Priority (Non-Preemptive)": 3,
        "Priority (Preemptive)": 4,
        "Round Robin": 5
    }
    algo_code = algo_map.get(algorithm_name, 0)

    # Prepare Log Buffer (Max 1000 entries)
    max_logs = 1000
    LogArray = GanttLog * max_logs
    c_logs = LogArray()

    # --- CALL C++ ---
    count = lib.run_scheduler(c_procs, n, algo_code, int(quantum), c_logs, max_logs)

    # --- Convert Results back to Python format ---
    
    # 1. Final DataFrame
    final_data = []
    for i in range(n):
        p = c_procs[i]
        final_data.append({
            "pid": f"P{p.pid}",
            "at": p.at,
            "bt": p.bt,
            "priority": p.priority,
            "ct": p.ct,
            "tat": p.tat,
            "wt": p.wt,
            "status": "completed"
        })
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