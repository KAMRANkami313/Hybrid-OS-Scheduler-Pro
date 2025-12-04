#include <vector>
#include <algorithm>
#include <iostream>

// Define standard C structures to match Python
struct Process {
    int pid;        // Numeric ID (e.g., 1 for P1)
    int at;         // Arrival Time
    int bt;         // Burst Time
    int priority;
    int ct;         // Completion Time
    int tat;        // Turnaround Time
    int wt;         // Waiting Time
    int rem_time;   // Remaining Time (internal usage)
};

struct GanttLog {
    int pid;
    int start;
    int finish;
};

extern "C" {
    // Windows requires dllexport to make functions visible
    __declspec(dllexport) int run_scheduler(
        Process* procs, 
        int n, 
        int algorithm_code, 
        int quantum, 
        GanttLog* logs, 
        int max_logs
    ) {
        // Copy processes to a local vector for manipulation
        std::vector<Process> queue;
        for(int i=0; i<n; i++) {
            procs[i].rem_time = procs[i].bt;
            queue.push_back(procs[i]);
        }

        std::vector<GanttLog> local_logs;
        int current_time = 0;
        int completed = 0;
        int log_count = 0;

        // 0: FCFS, 1: SJF, 2: SRTF, 3: Prio-NP, 4: Prio-P, 5: RR
        
        // --- ROUND ROBIN LOGIC (Code 5) ---
        if (algorithm_code == 5) {
            std::vector<int> ready_queue;
            std::vector<bool> in_queue(n, false);

            // Initial Arrival
            for(int i=0; i<n; i++) {
                if(queue[i].at <= current_time) {
                    ready_queue.push_back(i);
                    in_queue[i] = true;
                }
            }

            while(completed < n) {
                if(ready_queue.empty()) {
                    // Handle Idle
                    if(!local_logs.empty() && local_logs.back().pid == -1) {
                        local_logs.back().finish++;
                    } else {
                        local_logs.push_back({-1, current_time, current_time + 1}); // -1 = Idle
                    }
                    current_time++;
                    
                    // Check arrivals
                    for(int i=0; i<n; i++) {
                        if(!in_queue[i] && queue[i].at <= current_time) {
                            ready_queue.push_back(i);
                            in_queue[i] = true;
                        }
                    }
                    continue;
                }

                int idx = ready_queue.front();
                ready_queue.erase(ready_queue.begin());

                int exec_time = (queue[idx].rem_time < quantum) ? queue[idx].rem_time : quantum;
                
                int start = current_time;
                current_time += exec_time;
                queue[idx].rem_time -= exec_time;

                // Log
                if(!local_logs.empty() && local_logs.back().pid == queue[idx].pid && local_logs.back().finish == start) {
                    local_logs.back().finish = current_time;
                } else {
                    local_logs.push_back({queue[idx].pid, start, current_time});
                }

                // Check arrivals during execution
                for(int i=0; i<n; i++) {
                    if(!in_queue[i] && queue[i].at <= current_time) {
                        ready_queue.push_back(i);
                        in_queue[i] = true;
                    }
                }

                if(queue[idx].rem_time > 0) {
                    ready_queue.push_back(idx);
                } else {
                    completed++;
                    procs[idx].ct = current_time; // Update original array
                    procs[idx].tat = procs[idx].ct - procs[idx].at;
                    procs[idx].wt = procs[idx].tat - procs[idx].bt;
                }
            }
        }
        // --- GENERIC LOGIC (FCFS, Priority, etc - simplified for example) ---
        else {
            // A unified preemptive-style ticker for visualization accuracy
            while(completed < n) {
                int idx = -1;
                
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

                // SELECTION
                idx = candidates[0];
                for(int i : candidates) {
                    if (algorithm_code == 0) { // FCFS
                        if (queue[i].at < queue[idx].at) idx = i;
                    }
                    else if (algorithm_code == 1 || algorithm_code == 2) { // SJF/SRTF
                        if (queue[i].rem_time < queue[idx].rem_time) idx = i;
                    }
                    else if (algorithm_code == 3 || algorithm_code == 4) { // Priority
                        if (queue[i].priority < queue[idx].priority) idx = i;
                    }
                }

                // Execute 1 tick (simplest way to handle all preemptive/non-preemptive logic for Gantt)
                // Optimization: If non-preemptive, run full duration
                int run_time = 1;
                if(algorithm_code == 0 || algorithm_code == 1 || algorithm_code == 3) {
                    run_time = queue[idx].rem_time;
                }

                int start = current_time;
                current_time += run_time;
                queue[idx].rem_time -= run_time;

                 if(!local_logs.empty() && local_logs.back().pid == queue[idx].pid && local_logs.back().finish == start) {
                    local_logs.back().finish = current_time;
                } else {
                    local_logs.push_back({queue[idx].pid, start, current_time});
                }

                if(queue[idx].rem_time == 0) {
                    completed++;
                    procs[idx].ct = current_time;
                    procs[idx].tat = procs[idx].ct - procs[idx].at;
                    procs[idx].wt = procs[idx].tat - procs[idx].bt;
                }
            }
        }

        // Copy logs back to pointer
        int count = 0;
        for(const auto& log : local_logs) {
            if(count >= max_logs) break;
            logs[count].pid = log.pid;
            logs[count].start = log.start;
            logs[count].finish = log.finish;
            count++;
        }
        return count; // Return number of log entries
    }
}