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

# --- Error Handling Setup ---
def run_scheduler_dummy(procs, n, algorithm_code, quantum, logs, max_logs):
    """Dummy function to prevent crash if DLL is not loaded."""
    # Raise a clear error when trying to use the dummy function
    raise RuntimeError("The C++ scheduler.dll could not be loaded. Please ensure the file is in the project directory and compiled correctly.")
    # return 0

# 2. Load Library
dll_path = os.path.abspath("scheduler.dll")
lib = None
dll_loaded = False

try:
    lib = ctypes.CDLL(dll_path)
    dll_loaded = True
except Exception as e:
    # If loading fails, use the dummy function
    print(f"Error loading scheduler.dll: {e}. Using dummy scheduler.")
    class DummyLib:
        run_scheduler = run_scheduler_dummy
    lib = DummyLib()


# 3. Define function signature
# Only attempt to set argtypes/restype if the DLL was actually loaded
if dll_loaded:
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

    # If DLL failed to load, calling lib.run_scheduler will call run_scheduler_dummy 
    # and raise the descriptive runtime error.
    if not dll_loaded and n > 0:
         # We still need to run the dummy function if the DLL is missing, 
         # but since it raises an exception, we wrap it in a try/except for a nicer Streamlit message
         try:
             lib.run_scheduler(None, 0, 0, 0, None, 0)
         except RuntimeError as e:
             st.error(str(e))
             return pd.DataFrame(), [] # Return empty dataframes
         
    # Only proceed if there are processes to run OR if the DLL is loaded (safe call)
    if n == 0:
        return pd.DataFrame(), []

    ProcessArray = Process * n
    c_procs = ProcessArray()
    
    # Map PIDs 
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