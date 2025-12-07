import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
import io
import random
from scheduler_wrapper import solve_scheduling, SchedulerLoadError

# --- PAGE CONFIG ---
st.set_page_config(page_title="Hybrid OS Scheduler Pro", page_icon="🚀", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    
    .block-container {padding-top: 1rem; padding-bottom: 3rem;}
    
    /* Metrics Styling */
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 10px; 
        border-radius: 8px; 
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.05);
    }
    
    /* Button Styling */
    div.stButton > button:first-child {
        width: 100%;
        font-weight: bold;
        border-radius: 8px;
        padding-top: 0.5rem;
        padding-bottom: 0.5rem;
    }
    </style>
    """, unsafe_allow_html=True)

# --- SESSION STATE INITIALIZATION (Persistence) ---
if 'processes' not in st.session_state: st.session_state.processes = []
if 'last_run_df' not in st.session_state: st.session_state.last_run_df = None
if 'last_run_tl' not in st.session_state: st.session_state.last_run_tl = None
if 'last_total_time' not in st.session_state: st.session_state.last_total_time = 0
if 'step_mode_active' not in st.session_state: st.session_state.step_mode_active = False
if 'current_step_time' not in st.session_state: st.session_state.current_step_time = 0

# --- HELPER FUNCTIONS ---

# --- UPDATED PID GENERATION LOGIC ---
def generate_random_processes(count, max_at, min_bt, max_bt, max_prio):
    new_procs = []
    
    current_pid_nums = []
    for p in st.session_state.processes:
        try:
            pid_str = str(p['pid']).upper().strip()
            if pid_str.startswith('P'):
                current_pid_nums.append(int(pid_str[1:]))
        except ValueError:
            pass
            
    next_pid_num = max(current_pid_nums) + 1 if current_pid_nums else 1
    
    for i in range(count):
        new_procs.append({
            "pid": f"P{next_pid_num + i}",
            "at": random.randint(0, max_at),
            "bt": random.randint(min_bt, max_bt),
            "priority": random.randint(1, max_prio)
        })
    return new_procs
# --- END UPDATED PID GENERATION LOGIC ---


def create_gantt_chart(gantt_data, total_duration, color_map, height=200):
    fig = go.Figure()
    ticks = set([0])
    if gantt_data:
        ticks.update([s['Start'] for s in gantt_data])
        ticks.update([s['Finish'] for s in gantt_data])
    ticks = sorted(list(ticks))

    max_x = max(total_duration, 1)

    for segment in gantt_data:
        if segment['Task'] == "Idle": continue
        fig.add_trace(go.Bar(
            x=[segment['Finish'] - segment['Start']], y=["CPU"], base=[segment['Start']],
            orientation='h', marker=dict(color=color_map.get(segment['Task'], 'grey'), line=dict(color='black', width=1.5)),
            text=segment['Task'], textposition='inside', textfont=dict(color='white', size=14, family="Arial Black"),
            hovertext=f"Task: {segment['Task']}<br>Time: {segment['Start']} - {segment['Finish']}", hoverinfo='text'
        ))

    fig.update_layout(
        height=height, showlegend=False, margin=dict(l=10, r=10, t=10, b=30),
        xaxis=dict(range=[0, max_x], tickmode='array', tickvals=ticks, ticktext=ticks, showgrid=True, side='bottom'),
        yaxis=dict(showticklabels=False, showgrid=False), plot_bgcolor='white'
    )
    return fig

def generate_event_log(timeline):
    logs = []
    sorted_tl = sorted(timeline, key=lambda x: x['Start'])
    for seg in sorted_tl:
        if seg['Task'] == "Idle": logs.append(f"⏱️ Time {seg['Start']}: CPU is Idle.")
        else: 
            logs.append(f"▶️ Time {seg['Start']}: {seg['Task']} starts running.")
            logs.append(f"⏹️ Time {seg['Finish']}: {seg['Task']} finishes burst.")
    return logs

def display_stats_table(df):
    if df is None or df.empty: return

    # Calculate Averages
    avg_tat = df['tat'].mean()
    avg_wt = df['wt'].mean()
    avg_bt = df['bt'].mean()
    avg_rt = df['rt'].mean()

    disp_df = df.copy()
    avg_row = pd.DataFrame([{
        "pid": "AVERAGE", "at": 0, "bt": avg_bt, "priority": 0, 
        "ct": 0, "tat": avg_tat, "wt": avg_wt, "rt": avg_rt, "status": "-"
    }])
    disp_df = pd.concat([disp_df, avg_row], ignore_index=True)

    st.dataframe(
        disp_df.style.format({
            "bt": "{:.1f}", "tat": "{:.2f}", "wt": "{:.2f}", "rt": "{:.2f}", "at": "{:.0f}", "ct": "{:.0f}"
        }).background_gradient(subset=['tat', 'wt', 'rt'], cmap="Reds"), 
        use_container_width=True,
        # Try to hide the confusing Pandas index (0, 1, 2, 3...)
        hide_index=True 
    )

def run_scheduler_logic(algo, quant):
    if not st.session_state.processes:
        st.error("Please add processes first.")
        return False
    
    try:
        final_df, timeline = solve_scheduling(st.session_state.processes, algo, quant)
    except SchedulerLoadError as e:
        st.error(str(e))
        return False
        
    total_time = int(final_df['ct'].max()) if not final_df.empty else 0
    
    st.session_state.last_run_df = final_df
    st.session_state.last_run_tl = timeline
    st.session_state.last_total_time = total_time
    return True

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")

# --- Process Addition Tab 1 ---
st.sidebar.subheader("📝 Manual Process Entry")
with st.sidebar.form("add_manual"):
    c1, c2 = st.columns(2)
    # Hint for next available PID
    try:
        pids_in_use = [int(str(p['pid']).replace('P', '')) for p in st.session_state.processes if str(p['pid']).startswith('P')]
        next_manual_pid = max(pids_in_use) + 1 if pids_in_use else 1
    except:
        next_manual_pid = len(st.session_state.processes) + 1
        
    pid = c1.text_input("ID", value=f"P{next_manual_pid}")
    at = c2.number_input("Arrival", 0, value=0)
    bt = c1.number_input("Burst", 1, value=5)
    prio = c2.number_input("Priority", 1, value=1)
    if st.form_submit_button("Add Process"):
        st.session_state.processes.append({"pid": pid, "at": int(at), "bt": int(bt), "priority": int(prio)})
        st.rerun()

# --- Process Generation Tab 2 ---
st.sidebar.subheader("🎲 Random Process Generator")
with st.sidebar.form("add_random"):
    N = st.number_input("Number of Processes (N)", 1, 10, 3)
    max_at = st.number_input("Max Arrival Time", 0, 20, 5)
    c3, c4 = st.columns(2)
    min_bt = c3.number_input("Min Burst", 1, value=3)
    max_bt = c4.number_input("Max Burst", 1, value=10)
    max_prio = st.number_input("Max Priority Value", 1, 10, 5)
    if st.form_submit_button(f"Generate {N} Processes"):
        new_procs = generate_random_processes(N, max_at, min_bt, max_bt, max_prio)
        st.session_state.processes.extend(new_procs)
        st.rerun()

# --- Process File Handling (Fixed against infinite rerun loop) ---
st.sidebar.subheader("📂 Data Utilities")
upload_file = st.sidebar.file_uploader("Upload CSV Process List", type=["csv"], key="csv_uploader")
if upload_file is not None:
    try:
        uploaded_df = pd.read_csv(upload_file)
        required_cols = ['pid', 'at', 'bt', 'priority']
        if all(col in uploaded_df.columns for col in required_cols):
            st.session_state.processes = uploaded_df[required_cols].astype({'at': int, 'bt': int, 'priority': int}).to_dict('records')
            st.sidebar.success("Processes loaded successfully!")
        else:
            st.sidebar.error(f"CSV must contain columns: {', '.join(required_cols)}")
    except Exception as e:
        st.sidebar.error(f"Error reading file: {e}")

# Download button for current processes
if st.session_state.processes:
    download_df = pd.DataFrame(st.session_state.processes)
    csv = download_df.to_csv(index=False).encode('utf-8')
    st.sidebar.download_button(
        "Download Current Processes (CSV)",
        csv,
        "processes.csv",
        "text/csv",
        key='download-csv'
    )
    
st.sidebar.markdown("---")
if st.sidebar.button("Reset All Data", help="Clears all processes and simulation results"): 
    st.session_state.processes = []
    st.session_state.last_run_df = None
    st.session_state.step_mode_active = False
    st.rerun()

# --- MAIN APP ---
st.title("⚡ Hybrid OS Scheduler Pro")
st.caption("C++ Logic Engine | Python Analysis Suite")

if st.session_state.processes:
    st.markdown("#### Current Process List")
    # Display the input data using PID as index
    st.dataframe(pd.DataFrame(st.session_state.processes).set_index('pid'), use_container_width=True)
else:
    st.info("Add processes using the sidebar (manual or random generation) to begin.")

# Colors
pids = sorted(list(set([p['pid'] for p in st.session_state.processes])))
palette = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#DDA0DD', '#FFD700', '#C0C0C0']
color_map = {pid: palette[i % len(palette)] for i, pid in enumerate(pids)}

# --- TABS ---
tab1, tab2, tab3 = st.tabs(["⚡ Real-Time Simulation", "⚔️ Algorithm Comparison", "📊 Deep Analytics"])

# === TAB 1: SIMULATION ===
with tab1:
    col_settings, col_visuals = st.columns([1, 3.5], gap="medium")

    # --- SETTINGS ---
    with col_settings:
        st.subheader("Settings")
        algo = st.selectbox("Algorithm", ["FCFS", "Round Robin", "SJF (Non-Preemptive)", "SRTF (Preemptive SJF)", "Priority (Non-Preemptive)", "Priority (Preemptive)"])
        quant = 2
        if algo == "Round Robin": quant = st.number_input("Quantum", 1, 10, 2, key="q1")
        speed = st.slider("Anim Speed", 0.05, 1.0, 0.2)
        
        st.markdown("---")
        st.subheader("Controls")
        
        anim_clicked = st.button("🚀 Run Animation", type="primary")
        step_clicked = st.button("👣 Step-by-Step Mode")

        if step_clicked:
            if run_scheduler_logic(algo, quant):
                st.session_state.step_mode_active = True
                st.session_state.current_step_time = 0
            else:
                st.session_state.step_mode_active = False

        if anim_clicked:
            st.session_state.step_mode_active = False
            run_scheduler_logic(algo, quant)

    # --- VISUALS ---
    with col_visuals:
        m_col1, m_col2 = st.columns(2)
        timer_placeholder = m_col1.empty()
        cpu_placeholder = m_col2.empty()

        queue_placeholder = st.empty()
        chart_placeholder = st.empty()
        stats_placeholder = st.empty()

        def render_queue(t, df, curr_task):
            q_list = [p['pid'] for i,p in df.iterrows() if p['at']<=t and p['ct']>t and p['pid']!=curr_task]
            q_str = ' ➡️ '.join(q_list) if q_list else "Empty"
            html = f"""
            <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; margin-bottom: 10px;">
                <strong>Ready Queue (Approximate):</strong> <span style="color: #007bff;">{q_str}</span>
            </div>
            """
            queue_placeholder.markdown(html, unsafe_allow_html=True)

        # Logic A/B/C Combined View
        if st.session_state.last_run_df is not None:
            final_df = st.session_state.last_run_df
            timeline = st.session_state.last_run_tl
            total_time = st.session_state.last_total_time
            
            is_active = anim_clicked or (st.session_state.step_mode_active and st.session_state.current_step_time <= total_time)
            
            if is_active:
                
                current_t = st.session_state.current_step_time
                if anim_clicked: current_t = 0
                
                t_range = [current_t] if st.session_state.step_mode_active else range(current_t, total_time + 1)

                for t in t_range:
                    # 1. Update Metrics
                    timer_placeholder.metric("⏱️ Current Time" if st.session_state.step_mode_active else "⏱️ Timer", f"{t}s")
                    curr = "Idle"
                    for s in timeline:
                        if s['Start'] <= t < s['Finish']: curr = s['Task']
                    cpu_placeholder.metric("💻 CPU Process", curr)
                    
                    # 2. Queue
                    render_queue(t, final_df, curr)

                    # 3. Chart
                    vis_data = []
                    for s in timeline:
                        if s['Finish'] <= t: vis_data.append(s)
                        elif s['Start'] < t and s['Finish'] > t:
                            temp = s.copy(); temp['Finish'] = t; vis_data.append(temp)
                    
                    chart_placeholder.plotly_chart(create_gantt_chart(vis_data, total_time, color_map), use_container_width=True, key=f"anim_{t}")
                    
                    if anim_clicked:
                        time.sleep(speed)
                    
                    if st.session_state.step_mode_active:
                        break

                # Step-by-Step Controls
                if st.session_state.step_mode_active:
                    bc1, bc2 = st.columns([1, 1])
                    if bc1.button("◀ Previous Step"):
                        if st.session_state.current_step_time > 0:
                            st.session_state.current_step_time -= 1
                            st.rerun()
                    if bc2.button("Next Step ▶"):
                        if st.session_state.current_step_time < total_time:
                            st.session_state.current_step_time += 1
                            st.rerun()

                # Display final stats if simulation is complete
                if st.session_state.current_step_time >= total_time or anim_clicked:
                    with stats_placeholder.container():
                        st.markdown("### 📊 Final Statistics")
                        display_stats_table(final_df)

            else:
                # Static View after a run
                timer_placeholder.metric("⏱️ Total Time", f"{total_time}s")
                cpu_placeholder.metric("💻 Status", "Completed")
                render_queue(total_time, final_df, "Idle")
                chart_placeholder.plotly_chart(create_gantt_chart(timeline, total_time, color_map), use_container_width=True)
                
                with stats_placeholder.container():
                    st.markdown("### 📊 Final Statistics")
                    display_stats_table(final_df)
        
# === TAB 2: COMPARISON ===
with tab2:
    if not st.session_state.processes:
        st.info("Add processes in the sidebar to enable comparison.")
    else:
        ca1, ca2 = st.columns(2)
        with ca1:
            algoA = st.selectbox("Algorithm A", ["FCFS", "Round Robin", "SJF (Non-Preemptive)", "SRTF (Preemptive SJF)", "Priority (Non-Preemptive)", "Priority (Preemptive)"], index=0)
            qA = 2; 
            if algoA == "Round Robin": qA = st.number_input("Q-A", 1, 10, 2, key="qA")
        with ca2:
            algoB = st.selectbox("Algorithm B", ["FCFS", "Round Robin", "SJF (Non-Preemptive)", "SRTF (Preemptive SJF)", "Priority (Non-Preemptive)", "Priority (Preemptive)"], index=1)
            qB = 2; 
            if algoB == "Round Robin": qB = st.number_input("Q-B", 1, 10, 2, key="qB")

        if st.button("Compare Algorithms"):
            try:
                df1, tl1 = solve_scheduling(st.session_state.processes, algoA, qA)
                df2, tl2 = solve_scheduling(st.session_state.processes, algoB, qB)
            except SchedulerLoadError as e:
                st.error(str(e))
                st.stop()

            max_t = max(df1['ct'].max(), df2['ct'].max())
            
            st.markdown("### 📈 Performance Summary")
            
            comp_data = pd.DataFrame({
                'Algorithm': [algoA, algoA, algoA, algoB, algoB, algoB],
                'Metric': ['Avg TAT', 'Avg WT', 'Avg RT', 'Avg TAT', 'Avg WT', 'Avg RT'],
                'Value': [df1['tat'].mean(), df1['wt'].mean(), df1['rt'].mean(), df2['tat'].mean(), df2['wt'].mean(), df2['rt'].mean()]
            })
            fig_comp = px.bar(
                comp_data, x="Algorithm", y="Value", color="Metric", 
                barmode="group",
                title="Average Performance Metrics Comparison",
                color_discrete_map={'Avg TAT': '#FF6B6B', 'Avg WT': '#4ECDC4', 'Avg RT': '#45B7D1'}
            )
            st.plotly_chart(fig_comp, use_container_width=True)

            g1, g2 = st.columns(2)
            with g1:
                st.subheader(f"1. {algoA}")
                st.plotly_chart(create_gantt_chart(tl1, max_t, color_map, 180), use_container_width=True, key="c1")
                st.write("#### Detailed Stats")
                display_stats_table(df1)

            with g2:
                st.subheader(f"2. {algoB}")
                st.plotly_chart(create_gantt_chart(tl2, max_t, color_map, 180), use_container_width=True, key="c2")
                st.write("#### Detailed Stats")
                display_stats_table(df2)

# === TAB 3: DEEP ANALYTICS ===
with tab3:
    if st.session_state.last_run_df is None:
        st.info("Run a simulation in Tab 1 first to see analytics.")
    else:
        df = st.session_state.last_run_df
        tl = st.session_state.last_run_tl
        total_time = st.session_state.last_total_time

        st.subheader("📊 System Performance Overview")
        
        idle_time = sum([s['Finish'] - s['Start'] for s in tl if s['Task'] == "Idle"])
        busy_time = total_time - idle_time
        utilization = (busy_time / total_time) * 100 if total_time > 0 else 0
        throughput = len(df) / total_time if total_time > 0 else 0
        
        context_switches = len([s for s in tl if s['Task'] != "Idle"]) - len(df)
        if context_switches < 0: context_switches = 0
        
        avg_rt = df['rt'].mean()
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("CPU Utilization", f"{round(utilization, 1)}%")
        m2.metric("Throughput", f"{round(throughput, 2)} jobs/sec")
        m3.metric("Context Switches", context_switches)
        m4.metric("Avg Response Time", f"{round(avg_rt, 2)}s")

        c1, c2 = st.columns([1, 2])
        
        # 3.1 Utilization Gauge
        with c1: 
            fig_gauge = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = utilization,
                title = {'text': "CPU Load"},
                gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#4ECDC4"}}
            ))
            fig_gauge.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20))
            st.plotly_chart(fig_gauge, use_container_width=True)
            
        # 3.2 Time Composition Bar Chart (Burst, Wait, Response)
        with c2: 
            df_plot = df.copy()
            df_plot["Burst"] = df_plot["bt"]
            df_plot["Wait"] = df_plot["wt"]
            df_plot["Response"] = df_plot["rt"]
            
            fig_bar = px.bar(
                df_plot, x="pid", y=["Burst", "Wait", "Response"], 
                title="Time Composition per Process (Burst vs. Wait vs. Response)",
                color_discrete_map={"Burst": "#FF6B6B", "Wait": "#D3D3D3", "Response": "#45B7D1"},
                labels={"value": "Time (s)", "variable": "State"}
            )
            fig_bar.update_layout(height=300, plot_bgcolor='white')
            st.plotly_chart(fig_bar, use_container_width=True)

        st.markdown("---")
        st.subheader("🔍 Performance Trade-offs")
        
        c_plots1, c_plots2 = st.columns(2) 

        # 3.3 Scatter Plot 1: AT vs WT (Identify Starvation/Delay)
        with c_plots1:
            fig_scatter_wt = px.scatter(
                df, x='at', y='wt', text='pid',
                title='Waiting Time vs. Arrival Time',
                labels={'at': 'Arrival Time (s)', 'wt': 'Waiting Time (s)'}
            )
            fig_scatter_wt.update_traces(textposition='top center')
            fig_scatter_wt.update_layout(plot_bgcolor='white')
            st.plotly_chart(fig_scatter_wt, use_container_width=True)
            
        # 3.4 Scatter Plot 2: RT vs TAT (Relates responsiveness to throughput)
        with c_plots2:
            fig_scatter_rt = px.scatter(
                df, x='rt', y='tat', text='pid',
                title='Response Time vs. Turnaround Time',
                labels={'rt': 'Response Time (s)', 'tat': 'Turnaround Time (s)'}
            )
            fig_scatter_rt.update_traces(textposition='top center')
            fig_scatter_rt.update_layout(plot_bgcolor='white')
            st.plotly_chart(fig_scatter_rt, use_container_width=True)


        # 3.5 Event Logs
        logs = "\n".join(generate_event_log(tl))
        st.download_button("📜 Download Simulation Event Logs", logs, "events.txt", "text/plain")