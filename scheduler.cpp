#include <vector>
#include <algorithm>
#include <iostream>

// Define standard C structures to match Python
struct Process {
    int pid;        // Numeric ID (e.g., 1 for P1)
    int at;         // Arrival Time
    int bt;         // Burst Time
    int priority;   // Base (User-defined) Priority
    int ct;         // Completion Time
    int tat;        // Turnaround Time
    int wt;         // Waiting Time
    int rem_time;   // Remaining Time (internal usage)
    int first_run;  // Time of first execution (NEW for RT calculation)
    int base_priority; // Original priority (NEW for Aging tracking)
    int current_priority; // Priority adjusted by aging (NEW for scheduling)
};

struct GanttLog {
    int pid;
    int start;
    int finish;
};

// Global definition for aging rate (how often priority increases)
#define AGING_RATE 5 // Every 5 time units, priority increases by 1 (lower number = higher priority)

extern "C" {
__declspec(dllexport) int run_scheduler(
    Process* procs,
    int n,
    int algorithm_code,
    int quantum,
    GanttLog* logs,
    int max_logs
) {
    std::vector<Process> queue;
    for(int i=0; i<n; i++) {
        // Initialize new fields
        procs[i].rem_time = procs[i].bt;
        procs[i].first_run = -1; // -1 means never run
        procs[i].base_priority = procs[i].priority;
        procs[i].current_priority = procs[i].priority;
        queue.push_back(procs[i]);
    }

    std::vector<GanttLog> local_logs;
    int current_time = 0;
    int completed = 0;
    
    // 0: FCFS, 1: SJF, 2: SRTF, 3: Prio-NP, 4: Prio-P, 5: RR
    
    // --- ROUND ROBIN LOGIC (Code 5) ---
    // (RR logic remains complex and is omitted here for brevity, assuming the prior implementation is used)
    if (algorithm_code == 5) {
        // ... (Keep the previous, robust RR implementation logic here) ...
        // Note: You must update the final CT/TAT/WT calculation in the RR block 
        // to also update 'first_run' and 'current_priority' in 'procs[idx]'
        // when a process executes for the first time.
        
        // --- Placeholder for RR logic ---
        // Since the previous RR logic was provided, insert it here.
        // Ensure that inside the RR logic, when a process runs:
        /*
            if (queue[idx].first_run == -1) {
                queue[idx].first_run = start;
                procs[idx].first_run = start; // Propagate change to output struct
            }
        */
        // --- END Placeholder ---
        
        // Using the logic from the first submission for RR, with the added 'first_run' tracking:
        std::vector<int> ready_queue;
        std::vector<bool> in_queue(n, false);

        while(completed < n) {
            
            // Phase 1: Check for new arrivals
            for(int i=0; i<n; i++) {
                if(!in_queue[i] && queue[i].rem_time > 0 && queue[i].at <= current_time) {
                    ready_queue.push_back(i);
                    in_queue[i] = true;
                }
            }

            if(ready_queue.empty()) {
                // Handle Idle
                if(!local_logs.empty() && local_logs.back().pid == -1) {
                    local_logs.back().finish++;
                } else {
                    local_logs.push_back({-1, current_time, current_time + 1});
                }
                current_time++;
                continue;
            }

            int idx = ready_queue.front();
            ready_queue.erase(ready_queue.begin());

            int exec_time = (queue[idx].rem_time < quantum) ? queue[idx].rem_time : quantum;
            int start = current_time;
            
            // Track first run for Response Time calculation
            if (queue[idx].first_run == -1) {
                queue[idx].first_run = start;
                procs[idx].first_run = start; 
            }
            
            int next_arrival_time = -1;
            for(int i=0; i<n; ++i) {
                if (!in_queue[i] && queue[i].rem_time > 0) {
                    if (next_arrival_time == -1 || queue[i].at < next_arrival_time) {
                        next_arrival_time = queue[i].at;
                    }
                }
            }
            
            if (next_arrival_time != -1 && start + exec_time > next_arrival_time) {
                exec_time = next_arrival_time - start;
                if (exec_time <= 0) {
                    current_time = next_arrival_time;
                    ready_queue.insert(ready_queue.begin(), idx);
                    continue;
                }
            }

            current_time += exec_time;
            queue[idx].rem_time -= exec_time;

            // Log
            if(!local_logs.empty() && local_logs.back().pid == queue[idx].pid && local_logs.back().finish == start) {
                local_logs.back().finish = current_time;
            } else {
                local_logs.push_back({queue[idx].pid, start, current_time});
            }

            // Phase 2: Check arrivals during execution
            for(int i=0; i<n; i++) {
                if(!in_queue[i] && queue[i].rem_time > 0 && queue[i].at <= current_time) {
                    ready_queue.push_back(i);
                    in_queue[i] = true;
                }
            }

            if(queue[idx].rem_time > 0) {
                ready_queue.push_back(idx); // Re-add to the end
            } else {
                completed++;
                procs[idx].ct = current_time;
                procs[idx].tat = procs[idx].ct - procs[idx].at;
                procs[idx].bt = queue[idx].bt; // Restore original BT for WT calc
                procs[idx].wt = procs[idx].tat - procs[idx].bt;
                in_queue[idx] = false;
            }
        }
    }
    // --- GENERIC LOGIC (FCFS, SJF, Priority, SRTF, Prio-P) ---
    else {
        while(completed < n) {
            int idx = -1;
            
            // Phase 1: Aging (Applied only if Priority algorithm is selected)
            if (algorithm_code == 3 || algorithm_code == 4) {
                for (int i=0; i<n; ++i) {
                    if (queue[i].rem_time > 0 && queue[i].at <= current_time && queue[i].first_run == -1) {
                        // Calculate wait time
                        int wait_time = current_time - queue[i].at;
                        // Calculate priority boost: +1 priority (lower number) for every AGING_RATE units of wait time
                        int boost = wait_time / AGING_RATE; 
                        queue[i].current_priority = std::max(1, queue[i].base_priority - boost);
                        procs[i].current_priority = queue[i].current_priority;
                    }
                }
            }

            // Find candidates
            std::vector<int> candidates;
            for(int i=0; i<n; i++) {
                if(queue[i].at <= current_time && queue[i].rem_time > 0) {
                    candidates.push_back(i);
                }
            }

            if(candidates.empty()) {
                 if(!local_logs.empty() && local_logs.back().pid == -1) {
                    local_logs.back().finish++;
                } else {
                    local_logs.push_back({-1, current_time, current_time + 1});
                }
                current_time++;
                continue;
            }

            // --- SELECTION LOGIC (Using current_priority for Codes 3/4) ---
            idx = candidates[0];
            for(int i : candidates) {
                if (algorithm_code == 0) { // FCFS
                    if (queue[i].at < queue[idx].at) idx = i;
                }
                else if (algorithm_code == 1 || algorithm_code == 2) { // SJF/SRTF
                    if (queue[i].rem_time < queue[idx].rem_time || 
                        (queue[i].rem_time == queue[idx].rem_time && queue[i].at < queue[idx].at)) {
                        idx = i;
                    }
                }
                else if (algorithm_code == 3 || algorithm_code == 4) { // Priority (using current_priority)
                    // Lower number means higher priority
                    if (queue[i].current_priority < queue[idx].current_priority ||
                        (queue[i].current_priority == queue[idx].current_priority && queue[i].at < queue[idx].at)) {
                        idx = i;
                    }
                }
            }

            // --- EXECUTION DURATION CALCULATION ---
            int run_time = 1;
            int selected_pid = queue[idx].pid;

            // Non-Preemptive Execution (FCFS, SJF-NP, Prio-NP)
            if(algorithm_code == 0 || algorithm_code == 1 || algorithm_code == 3) {
                run_time = queue[idx].rem_time;
            } 
            // Preemptive Execution (SRTF, Prio-P) - Must check for preemption triggers
            else {
                int next_switch_time = current_time + queue[idx].rem_time;

                for (int i=0; i<n; ++i) {
                    if (i == idx || queue[i].rem_time == 0) continue;
                    
                    if (queue[i].at > current_time && queue[i].at < next_switch_time) {
                        bool arrival_preempts = false;
                        if (algorithm_code == 2) { // SRTF
                            if (queue[i].rem_time < queue[idx].rem_time) arrival_preempts = true;
                        } else if (algorithm_code == 4) { // Priority P (Check based on current priority)
                            if (queue[i].current_priority < queue[idx].current_priority) arrival_preempts = true;
                        }

                        if (arrival_preempts) {
                            next_switch_time = queue[i].at;
                        }
                    }
                    
                    // Preemption check for Prio-P when running (Aging could trigger a switch)
                    // We only need to check if the current process will be preempted by a WAITING process.
                    if (algorithm_code == 4 && queue[i].at <= current_time) {
                        if (queue[i].current_priority < queue[idx].current_priority) {
                            // If a waiting process is now higher priority, run for 1 tick to allow switch next tick
                            // NOTE: Since aging is applied tick-by-tick (or batch-by-batch before selection), 
                            // setting run_time=1 ensures the scheduler re-evaluates the highest priority process next tick.
                            run_time = 1;
                        }
                    }
                }
                run_time = std::min(run_time, next_switch_time - current_time);
            }
            
            // Sanity check
            if (run_time <= 0) { 
                current_time++; 
                continue; 
            }

            int start = current_time;
            
            // --- Record First Run (Response Time) ---
            if (queue[idx].first_run == -1) {
                queue[idx].first_run = start;
                procs[idx].first_run = start; // Propagate to output struct
            }

            current_time += run_time;
            queue[idx].rem_time -= run_time;

             if(!local_logs.empty() && local_logs.back().pid == selected_pid && local_logs.back().finish == start) {
                local_logs.back().finish = current_time;
            } else {
                local_logs.push_back({selected_pid, start, current_time});
            }

            if(queue[idx].rem_time == 0) {
                completed++;
                procs[idx].ct = current_time;
                procs[idx].tat = procs[idx].ct - procs[idx].at;
                procs[idx].bt = queue[idx].bt; // Restore original BT for WT calc
                procs[idx].wt = procs[idx].tat - procs[idx].bt;
            }
        }
    }

    // Copy logs back and finalize Response Time calculation
    for(int i=0; i<n; ++i) {
        if(procs[i].first_run != -1) {
            // We overload the 'priority' field in the output structure to temporarily hold Response Time (RT)
            // We assume 'priority' is unused after scheduling is complete, but let's be safer and use a dedicated field.
            // Since we cannot add a new field without breaking the wrapper, we will calculate RT in Python.
            // procs[i].rt = procs[i].first_run - procs[i].at; // Assuming RT field existed
        }
    }


    int count = 0;
    for(const auto& log : local_logs) {
        if(count >= max_logs) break;
        logs[count].pid = log.pid;
        logs[count].start = log.start;
        logs[count].finish = log.finish;
        count++;
    }
    return count;
}

}