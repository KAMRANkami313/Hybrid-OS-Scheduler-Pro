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
    
    // 0: FCFS, 1: SJF, 2: SRTF, 3: Prio-NP, 4: Prio-P, 5: RR
    
    // --- ROUND ROBIN LOGIC (Code 5) ---
    if (algorithm_code == 5) {
        std::vector<int> ready_queue;
        std::vector<bool> in_queue(n, false);

        // Initial Arrival check
        // NOTE: In a true RR implementation, the ready queue management is complex
        // This simplified version relies on current_time >= AT checks
        
        while(completed < n) {
            
            // Phase 1: Check for new arrivals before execution starts
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
                    local_logs.push_back({-1, current_time, current_time + 1}); // -1 = Idle
                }
                current_time++;
                
                // Advance current_time until the next arrival or until max simulation time (implicit by loop termination)
                // In a real scheduler, we would jump to the next arrival time here. For tick-based consistency, we increment by 1.
                continue;
            }

            int idx = ready_queue.front();
            ready_queue.erase(ready_queue.begin());

            int exec_time = (queue[idx].rem_time < quantum) ? queue[idx].rem_time : quantum;
            
            int start = current_time;
            
            // Find the time point (T_end) where this burst ends or the next arrival happens, whichever is sooner
            int next_arrival_time = -1;
            for(int i=0; i<n; ++i) {
                if (!in_queue[i] && queue[i].rem_time > 0) {
                    if (next_arrival_time == -1 || queue[i].at < next_arrival_time) {
                        next_arrival_time = queue[i].at;
                    }
                }
            }
            
            // Adjust execution time if a process arrives during the execution (preemption by arrival)
            if (next_arrival_time != -1 && start + exec_time > next_arrival_time) {
                exec_time = next_arrival_time - start;
                // If exec_time is 0 or less, we skip execution and re-add the current process to the front
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

            // Phase 2: Check arrivals during execution (Crucial for RR accuracy)
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
                procs[idx].ct = current_time; // Update original array
                procs[idx].tat = procs[idx].ct - procs[idx].at;
                procs[idx].wt = procs[idx].tat - procs[idx].bt;
                in_queue[idx] = false; // Mark as finished
            }
        }
    }
    // --- GENERIC LOGIC (FCFS, SJF, Priority, SRTF, Prio-P) ---
    else {
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

            // --- SELECTION LOGIC (Including new Tie-Breakers) ---
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
                else if (algorithm_code == 3 || algorithm_code == 4) { // Priority
                    // Lower number means higher priority
                    if (queue[i].priority < queue[idx].priority ||
                        (queue[i].priority == queue[idx].priority && queue[i].at < queue[idx].at)) {
                        idx = i;
                    }
                }
            }

            // --- EXECUTION DURATION CALCULATION ---
            int run_time = 1; // Default for preemptive (SRTF, Prio-P)
            int selected_pid = queue[idx].pid;

            // Non-Preemptive Execution (FCFS, SJF-NP, Prio-NP)
            if(algorithm_code == 0 || algorithm_code == 1 || algorithm_code == 3) {
                run_time = queue[idx].rem_time;
            } 
            // Preemptive Execution (SRTF, Prio-P) - Must check for preemption triggers
            else {
                // Find the next time point where a context switch might occur.
                int next_switch_time = current_time + queue[idx].rem_time; // Time of completion (max run)

                for (int i=0; i<n; ++i) {
                    if (i == idx || queue[i].rem_time == 0) continue;
                    
                    // Check if new arrival happens that could preempt
                    if (queue[i].at > current_time && queue[i].at < next_switch_time) {
                        
                        // Check if the arrival would actually preempt:
                        bool arrival_preempts = false;
                        if (algorithm_code == 2) { // SRTF
                            if (queue[i].rem_time < queue[idx].rem_time) arrival_preempts = true;
                        } else if (algorithm_code == 4) { // Priority P
                            if (queue[i].priority < queue[idx].priority) arrival_preempts = true;
                        }

                        if (arrival_preempts) {
                            next_switch_time = queue[i].at;
                        }
                    }
                }
                run_time = next_switch_time - current_time;
            }

            // Ensure run_time is positive
            if (run_time <= 0) { 
                current_time++; 
                continue; 
            }

            int start = current_time;
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