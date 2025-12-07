#include <vector>
#include <algorithm>
#include <iostream>
#include <map>

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
    int first_run;  // Time of first execution
    int base_priority; // Original priority
    int current_priority; // Aged priority
    
    // MLFQ/MLQ Fields
    int current_queue;   // 1, 2, or 3
    int last_q3_entry;   // Time the process entered Q3 (for promotion check)
};

struct GanttLog {
    int pid;
    int start;
    int finish;
};

// Global definition for aging rate (used for Priority P/NP)
#define PRIORITY_AGING_RATE 5 

// MLFQ Parameters
#define Q1_QUANTUM 8
#define Q2_QUANTUM 16
#define Q3_PROMOTION_THRESHOLD 50 

// MLQ Parameters
#define MLQ_Q2_QUANTUM 10

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
        procs[i].rem_time = procs[i].bt;
        procs[i].first_run = -1; 
        procs[i].base_priority = procs[i].priority;
        procs[i].current_priority = procs[i].priority;
        
        // MLFQ / MLQ Initialization
        if (algorithm_code == 6) {
            procs[i].current_queue = 1; // MLFQ: Start in Q1
        } else if (algorithm_code == 7) {
            // MLQ: The target queue ID (1, 2, or 3) is passed in the initial 'priority' field.
            procs[i].current_queue = procs[i].priority; 
        } else {
            procs[i].current_queue = -1; 
        }
        procs[i].last_q3_entry = -1;
        queue.push_back(procs[i]);
    }

    std::vector<GanttLog> local_logs;
    int current_time = 0;
    int completed = 0;
    
    // 0: FCFS, 1: SJF, 2: SRTF, 3: Prio-NP, 4: Prio-P, 5: RR, 6: MLFQ, 7: MLQ
    
    // --- MLQ LOGIC (Code 7) ---
    if (algorithm_code == 7) {
        // Ready queues grouped by fixed assignment (1, 2, 3)
        std::map<int, std::vector<int>> ready_queues; 
        std::vector<bool> in_ready_queue(n, false);
        
        auto check_arrivals = [&](int t) {
            for(int i=0; i<n; i++) {
                if(!in_ready_queue[i] && queue[i].rem_time > 0 && queue[i].at <= t) {
                    int target_q = queue[i].current_queue; 
                    ready_queues[target_q].push_back(i);
                    in_ready_queue[i] = true;
                    
                    // Q1 (Priority P): Sort by base_priority (lower=higher) then AT
                    if (target_q == 1) {
                        std::sort(ready_queues[1].begin(), ready_queues[1].end(), [&](int a, int b) {
                            if (queue[a].base_priority != queue[b].base_priority) {
                                return queue[a].base_priority < queue[b].base_priority;
                            }
                            return queue[a].at < queue[b].at;
                        });
                    } 
                    // Q3 (FCFS): Sort by AT
                    else if (target_q == 3) {
                         std::sort(ready_queues[3].begin(), ready_queues[3].end(), [&](int a, int b) {
                            return queue[a].at < queue[b].at;
                        });
                    }
                }
            }
        };

        while(completed < n) {
            check_arrivals(current_time);

            int idx = -1;
            int current_q = -1;
            int run_time = 1;

            // Phase 2: Strict Priority Selection (Q1 > Q2 > Q3)
            
            if (!ready_queues[1].empty()) {
                idx = ready_queues[1][0]; // Highest priority process
                current_q = 1;
            } 
            else if (!ready_queues[2].empty()) {
                idx = ready_queues[2].front();
                ready_queues[2].erase(ready_queues[2].begin()); // Dequeue RR
                current_q = 2;
            } 
            else if (!ready_queues[3].empty()) {
                idx = ready_queues[3].front();
                ready_queues[3].erase(ready_queues[3].begin()); // Dequeue FCFS
                current_q = 3;
            }

            if (idx == -1) {
                // Handle Idle
                if(!local_logs.empty() && local_logs.back().pid == -1) local_logs.back().finish++;
                else local_logs.push_back({-1, current_time, current_time + 1});
                current_time++;
                continue;
            }

            int selected_pid = queue[idx].pid;
            
            // Phase 3: Execution Duration
            if (current_q == 1) { // Q1: Priority Preemptive (Execute 1 tick)
                run_time = 1;
            } else if (current_q == 2) { // Q2: Round Robin (Q=10)
                run_time = std::min(queue[idx].rem_time, MLQ_Q2_QUANTUM);
            } else { // Q3: FCFS (Run until completion)
                run_time = queue[idx].rem_time;
            }
            
            // --- MLQ Master Preemption Check (Q1 arrivals preempt Q2/Q3) ---
            int next_switch_time = current_time + run_time;

            // Check for arrivals of any Q1 processes during Q2/Q3 execution
            for (int i=0; i<n; ++i) {
                if (queue[i].rem_time > 0 && queue[i].current_queue == 1 && queue[i].at > current_time && queue[i].at < next_switch_time) {
                    next_switch_time = queue[i].at;
                }
            }
            run_time = next_switch_time - current_time;
            
            // Sanity check/Re-enqueue if run time was reduced to zero by an arrival
            if (run_time <= 0) {
                 if (current_q == 2) ready_queues[2].insert(ready_queues[2].begin(), idx);
                 else if (current_q == 3) ready_queues[3].insert(ready_queues[3].begin(), idx);
                 // Q1 index stays in ready_queues[1], no insert needed
                 current_time++;
                 continue;
            }
            
            int start = current_time;
            
            // Response Time Check
            if (queue[idx].first_run == -1) {
                queue[idx].first_run = start;
                procs[idx].first_run = start; 
            }
            
            current_time += run_time;
            queue[idx].rem_time -= run_time;

            // Log
            if(!local_logs.empty() && local_logs.back().pid == selected_pid && local_logs.back().finish == start) {
                local_logs.back().finish = current_time;
            } else {
                local_logs.push_back({selected_pid, start, current_time});
            }
            
            // Phase 4: Post-Execution Status Update
            if(queue[idx].rem_time == 0) {
                completed++;
                procs[idx].ct = current_time;
                procs[idx].tat = procs[idx].ct - procs[idx].at;
                procs[idx].bt = queue[idx].bt;
                procs[idx].wt = procs[idx].tat - procs[idx].bt;
                in_ready_queue[idx] = false; 
            } else {
                // Re-enqueue (Preemption or Quantum expiration)
                if (current_q == 2) {
                    ready_queues[2].push_back(idx); // RR
                } 
                // Q1 runs indefinitely until completion or higher priority/arrival. 
                // Since Q1 processes are not dequeued until completion, no re-enqueue needed here.
            }
        }
    }
    // --- MLFQ LOGIC (Code 6) ---
    else if (algorithm_code == 6) {
        std::vector<int> q1_ready; // RR (Q=8)
        std::vector<int> q2_ready; // RR (Q=16)
        std::vector<int> q3_ready; // FCFS (Wait list)
        
        std::vector<bool> in_ready_queue(n, false);
        
        auto check_arrivals = [&](int t) {
            for(int i=0; i<n; i++) {
                if(!in_ready_queue[i] && queue[i].rem_time > 0 && queue[i].at <= t) {
                    q1_ready.push_back(i); // All new arrivals go to Q1
                    in_ready_queue[i] = true;
                }
            }
        };

        while(completed < n) {
            check_arrivals(current_time);

            // Phase 1: Q3 Promotion (Aging)
            for(size_t i = 0; i < q3_ready.size(); ) {
                int idx = q3_ready[i];
                if (queue[idx].last_q3_entry != -1 && (current_time - queue[idx].last_q3_entry) >= Q3_PROMOTION_THRESHOLD) {
                    queue[idx].current_queue = 2;
                    queue[idx].last_q3_entry = -1;
                    q2_ready.push_back(idx);
                    q3_ready.erase(q3_ready.begin() + i);
                } else {
                    ++i;
                }
            }

            int idx = -1;
            int current_q = -1;
            int current_quantum = 0;

            // Phase 2: Selection (Priority Q1 > Q2 > Q3)
            if (!q1_ready.empty()) {
                idx = q1_ready.front();
                q1_ready.erase(q1_ready.begin());
                current_q = 1;
                current_quantum = Q1_QUANTUM;
            } else if (!q2_ready.empty()) {
                idx = q2_ready.front();
                q2_ready.erase(q2_ready.begin());
                current_q = 2;
                current_quantum = Q2_QUANTUM;
            } else if (!q3_ready.empty()) {
                idx = q3_ready.front();
                q3_ready.erase(q3_ready.begin());
                current_q = 3;
                current_quantum = queue[idx].rem_time; 
            }

            if (idx == -1) {
                if(!local_logs.empty() && local_logs.back().pid == -1) local_logs.back().finish++;
                else local_logs.push_back({-1, current_time, current_time + 1});
                current_time++;
                continue;
            }

            // Phase 3: Execution
            int exec_time = (queue[idx].rem_time < current_quantum) ? queue[idx].rem_time : current_quantum;
            int start = current_time;
            
            if (queue[idx].first_run == -1) {
                queue[idx].first_run = start;
                procs[idx].first_run = start; 
            }
            
            current_time += exec_time;
            queue[idx].rem_time -= exec_time;

            // Log
            if(!local_logs.empty() && local_logs.back().pid == queue[idx].pid && local_logs.back().finish == start) {
                local_logs.back().finish = current_time;
            } else {
                local_logs.push_back({queue[idx].pid, start, current_time});
            }
            
            check_arrivals(current_time);

            // Phase 4: Post-Execution Status Update (Demotion/Completion)
            if(queue[idx].rem_time == 0) {
                completed++;
                procs[idx].ct = current_time;
                procs[idx].tat = procs[idx].ct - procs[idx].at;
                procs[idx].bt = queue[idx].bt;
                procs[idx].wt = procs[idx].tat - procs[idx].bt;
                in_ready_queue[idx] = false;
            } else {
                if (exec_time < current_quantum && current_q != 3) {
                    // Finished segment early (re-enqueue in same queue, unless Q3)
                    if (current_q == 1) q1_ready.push_back(idx);
                    else if (current_q == 2) q2_ready.push_back(idx);
                } else if (current_q != 3) {
                    // Quantum expired -> Demote (Q3 is handled by FCFS completion rule)
                    queue[idx].current_queue++;
                    
                    if (queue[idx].current_queue == 2) {
                        q2_ready.push_back(idx);
                    } else if (queue[idx].current_queue >= 3) {
                        queue[idx].current_queue = 3;
                        q3_ready.push_back(idx);
                        queue[idx].last_q3_entry = current_time;
                    }
                }
                in_ready_queue[idx] = true;
            }
            procs[idx].current_queue = queue[idx].current_queue; 
        }
    }
    // --- GENERIC LOGIC (Codes 0, 1, 2, 3, 4, 5) ---
    else {
        // --- RR LOGIC (Code 5) ---
        if (algorithm_code == 5) {
            std::vector<int> ready_queue;
            std::vector<bool> in_queue(n, false);

            while(completed < n) {
                for(int i=0; i<n; i++) {
                    if(!in_queue[i] && queue[i].rem_time > 0 && queue[i].at <= current_time) {
                        ready_queue.push_back(i);
                        in_queue[i] = true;
                    }
                }

                if(ready_queue.empty()) {
                    if(!local_logs.empty() && local_logs.back().pid == -1) local_logs.back().finish++;
                    else local_logs.push_back({-1, current_time, current_time + 1});
                    current_time++;
                    continue;
                }

                int idx = ready_queue.front();
                ready_queue.erase(ready_queue.begin());

                int exec_time = (queue[idx].rem_time < quantum) ? queue[idx].rem_time : quantum;
                int start = current_time;
                
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

                if(!local_logs.empty() && local_logs.back().pid == queue[idx].pid && local_logs.back().finish == start) {
                    local_logs.back().finish = current_time;
                } else {
                    local_logs.push_back({queue[idx].pid, start, current_time});
                }

                for(int i=0; i<n; i++) {
                    if(!in_queue[i] && queue[i].rem_time > 0 && queue[i].at <= current_time) {
                        ready_queue.push_back(i);
                        in_queue[i] = true;
                    }
                }

                if(queue[idx].rem_time > 0) {
                    ready_queue.push_back(idx);
                } else {
                    completed++;
                    procs[idx].ct = current_time;
                    procs[idx].tat = procs[idx].ct - procs[idx].at;
                    procs[idx].bt = queue[idx].bt;
                    procs[idx].wt = procs[idx].tat - procs[idx].bt;
                    in_queue[idx] = false;
                }
            }
        }
        
        // --- GENERIC LOGIC (Codes 0, 1, 2, 3, 4) ---
        else {
            while(completed < n) {
                int idx = -1;
                
                // Phase 1: Aging 
                if (algorithm_code == 3 || algorithm_code == 4) {
                    for (int i=0; i<n; ++i) {
                        if (queue[i].rem_time > 0 && queue[i].at <= current_time && queue[i].first_run == -1) {
                            int wait_time = current_time - queue[i].at;
                            int boost = wait_time / PRIORITY_AGING_RATE; 
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
                     if(!local_logs.empty() && local_logs.back().pid == -1) local_logs.back().finish++;
                     else local_logs.push_back({-1, current_time, current_time + 1});
                    current_time++;
                    continue;
                }

                // --- SELECTION LOGIC ---
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
                        if (queue[i].current_priority < queue[idx].current_priority ||
                            (queue[i].current_priority == queue[idx].current_priority && queue[i].at < queue[idx].at)) {
                            idx = i;
                        }
                    }
                }

                // --- EXECUTION DURATION CALCULATION ---
                int run_time = 1;
                int selected_pid = queue[idx].pid;

                if(algorithm_code == 0 || algorithm_code == 1 || algorithm_code == 3) {
                    run_time = queue[idx].rem_time;
                } 
                else {
                    int next_switch_time = current_time + queue[idx].rem_time;

                    for (int i=0; i<n; ++i) {
                        if (i == idx || queue[i].rem_time == 0) continue;
                        
                        if (queue[i].at > current_time && queue[i].at < next_switch_time) {
                            bool arrival_preempts = false;
                            if (algorithm_code == 2) { 
                                if (queue[i].rem_time < queue[idx].rem_time) arrival_preempts = true;
                            } else if (algorithm_code == 4) { 
                                if (queue[i].current_priority < queue[idx].current_priority) arrival_preempts = true;
                            }

                            if (arrival_preempts) {
                                next_switch_time = queue[i].at;
                            }
                        }
                        
                        if (algorithm_code == 4 && queue[i].at <= current_time) {
                            if (queue[i].current_priority < queue[idx].current_priority) {
                                run_time = 1;
                            }
                        }
                    }
                    run_time = std::min(run_time, next_switch_time - current_time);
                }

                if (run_time <= 0) { 
                    current_time++; 
                    continue; 
                }

                int start = current_time;
                
                if (queue[idx].first_run == -1) {
                    queue[idx].first_run = start;
                    procs[idx].first_run = start; 
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
                    procs[idx].bt = queue[idx].bt;
                    procs[idx].wt = procs[idx].tat - procs[idx].bt;
                }
            }
        }
    }

    // Final log copy
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