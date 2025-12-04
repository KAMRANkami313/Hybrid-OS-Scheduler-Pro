import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import time
from scheduler_wrapper import solve_scheduling

# --- PAGE CONFIG ---
st.set_page_config(page_title="Hybrid OS Scheduler Pro", page_icon="🚀", layout="wide")

# --- CUSTOM CSS ---
st.markdown("""
    <style>
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
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
        if seg['Task'] == "Idle": logs.append(f"⏱️ **Time {seg['Start']}**: CPU is Idle.")
        else: 
            logs.append(f"▶️ **Time {seg['Start']}**: {seg['Task']} starts running.")
            logs.append(f"⏹️ **Time {seg['Finish']}**: {seg['Task']} finishes burst.")
    return logs

def display_stats_table(df):
    if df is None or df.empty: return

    # Calculate Averages
    avg_tat = df['tat'].mean()
    avg_wt = df['wt'].mean()
    avg_bt = df['bt'].mean()

    disp_df = df.copy()
    avg_row = pd.DataFrame([{
        "pid": "AVERAGE", "at": 0, "bt": avg_bt, "priority": 0, 
        "ct": 0, "tat": avg_tat, "wt": avg_wt, "status": "-"
    }])
    disp_df = pd.concat([disp_df, avg_row], ignore_index=True)

    st.dataframe(
        disp_df.style.format({
            "bt": "{:.1f}", "tat": "{:.2f}", "wt": "{:.2f}", "at": "{:.0f}", "ct": "{:.0f}"
        }).background_gradient(subset=['tat', 'wt'], cmap="Reds"), 
        use_container_width=True
    )

def run_scheduler_logic(algo, quant):
    if not st.session_state.processes:
        return False
    
    final_df, timeline = solve_scheduling(st.session_state.processes, algo, quant)
    total_time = int(final_df['ct'].max()) if not final_df.empty else 0
    
    st.session_state.last_run_df = final_df
    st.session_state.last_run_tl = timeline
    st.session_state.last_total_time = total_time
    return True

# --- SIDEBAR ---
st.sidebar.header("⚙️ Configuration")
st.sidebar.subheader("📝 Process Management")
with st.sidebar.form("add"):
    c1, c2 = st.columns(2)
    pid = c1.text_input("ID", value=f"P{len(st.session_state.processes)+1}")
    at = c2.number_input("Arrival", 0, value=0)
    bt = c1.number_input("Burst", 1, value=5)
    prio = c2.number_input("Priority", 0, value=1)
    if st.form_submit_button("Add Process"):
        st.session_state.processes.append({"pid": pid, "at": int(at), "bt": int(bt), "priority": int(prio)})

if st.sidebar.button("Reset Processes"): 
    st.session_state.processes = []
    st.session_state.step_mode_active = False
    st.rerun()

# --- MAIN APP ---
st.title("⚡ Hybrid OS Scheduler Pro")
st.caption("C++ Logic Engine | Python Analysis Suite")

if st.session_state.processes:
    st.dataframe(pd.DataFrame(st.session_state.processes), use_container_width=True)
else:
    st.info("Add processes using the sidebar to begin.")

# Colors
pids = sorted(list(set([p['pid'] for p in st.session_state.processes])))
palette = ['#FF6B6B', '#4ECDC4', '#45B7D1', '#FFA07A', '#98D8C8', '#DDA0DD', '#FFD700']
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
        if algo == "Round Robin": quant = st.number_input("Quantum", 1, 10, 2)
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
                st.error("No Data!")

        if anim_clicked:
            st.session_state.step_mode_active = False
            if not run_scheduler_logic(algo, quant):
                st.error("No Data!")

    # --- VISUALS ---
    with col_visuals:
        # 1. FIXED METRIC PLACEHOLDERS (To prevent stacking)
        m_col1, m_col2 = st.columns(2)
        timer_placeholder = m_col1.empty()
        cpu_placeholder = m_col2.empty()

        # 2. OTHER PLACEHOLDERS
        queue_placeholder = st.empty()
        chart_placeholder = st.empty()
        stats_placeholder = st.empty()

        # Helper to Render Queue Cleanly
        def render_queue(t, df, curr_task):
            q_list = [p['pid'] for i,p in df.iterrows() if p['at']<=t and p['ct']>t and p['pid']!=curr_task]
            q_str = ' ➡️ '.join(q_list) if q_list else "Empty"
            html = f"""
            <div style="background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 5px; padding: 10px; margin-bottom: 10px;">
                <strong>Ready Queue:</strong> <span style="color: #007bff;">{q_str}</span>
            </div>
            """
            queue_placeholder.markdown(html, unsafe_allow_html=True)

        # Logic A: Run Animation
        if anim_clicked and st.session_state.last_run_df is not None:
            final_df = st.session_state.last_run_df
            timeline = st.session_state.last_run_tl
            total_time = st.session_state.last_total_time

            for t in range(total_time + 1):
                # 1. Update Metrics in Place
                timer_placeholder.metric("⏱️ Timer", f"{t}s")
                curr = "Idle"
                for s in timeline:
                    if s['Start'] <= t < s['Finish']: curr = s['Task']
                cpu_placeholder.metric("💻 CPU", curr)
                
                # 2. Queue
                render_queue(t, final_df, curr)

                # 3. Chart
                vis_data = []
                for s in timeline:
                    if s['Finish'] <= t: vis_data.append(s)
                    elif s['Start'] < t and s['Finish'] > t:
                        temp = s.copy(); temp['Finish'] = t; vis_data.append(temp)
                
                chart_placeholder.plotly_chart(create_gantt_chart(vis_data, total_time, color_map), use_container_width=True, key=f"anim_{t}")
                time.sleep(speed)
            
            # End: Stats
            with stats_placeholder.container():
                st.markdown("### 📊 Final Statistics")
                display_stats_table(final_df)

        # Logic B: Step-by-Step
        elif st.session_state.step_mode_active and st.session_state.last_run_tl is not None:
            timeline = st.session_state.last_run_tl
            final_df = st.session_state.last_run_df
            total_time = st.session_state.last_total_time
            curr_t = st.session_state.current_step_time

            # 1. Metrics
            timer_placeholder.metric("⏱️ Current Time", f"{curr_t}s")
            curr_task = "Idle"
            for s in timeline:
                if s['Start'] <= curr_t < s['Finish']: curr_task = s['Task']
            cpu_placeholder.metric("💻 CPU Process", curr_task)

            # 2. Queue
            render_queue(curr_t, final_df, curr_task)

            # 3. Chart
            vis_data = []
            for s in timeline:
                if s['Finish'] <= curr_t: vis_data.append(s)
                elif s['Start'] < curr_t and s['Finish'] > curr_t:
                    temp = s.copy(); temp['Finish'] = curr_t; vis_data.append(temp)
            
            if vis_data:
                chart_placeholder.plotly_chart(create_gantt_chart(vis_data, total_time, color_map), use_container_width=True, key="step_chart")
            else:
                chart_placeholder.info("Simulation Ready. Click Next.")

            # 4. Controls
            bc1, bc2 = st.columns([1, 1])
            if bc1.button("◀ Previous Step"):
                if st.session_state.current_step_time > 0:
                    st.session_state.current_step_time -= 1
                    st.rerun()
            if bc2.button("Next Step ▶"):
                if st.session_state.current_step_time < total_time:
                    st.session_state.current_step_time += 1
                    st.rerun()
            
            if curr_t >= total_time:
                 with stats_placeholder.container():
                    st.markdown("### 📊 Final Statistics")
                    display_stats_table(final_df)


        # Logic C: Static View
        elif st.session_state.last_run_df is not None:
            final_df = st.session_state.last_run_df
            timeline = st.session_state.last_run_tl
            total_time = st.session_state.last_total_time
            
            timer_placeholder.metric("⏱️ Total Time", f"{total_time}s")
            cpu_placeholder.metric("💻 Status", "Completed")
            
            render_queue(total_time, final_df, "Idle")

            chart_placeholder.plotly_chart(create_gantt_chart(timeline, total_time, color_map), use_container_width=True)

            with stats_placeholder.container():
                st.markdown("### 📊 Final Statistics")
                display_stats_table(final_df)

# === TAB 2: COMPARISON ===
with tab2:
    ca1, ca2 = st.columns(2)
    with ca1:
        algoA = st.selectbox("Algorithm A", ["FCFS", "Round Robin"], index=0)
        qA = 2; 
        if algoA == "Round Robin": qA = st.number_input("Q-A", 1, 10, 2)
    with ca2:
        algoB = st.selectbox("Algorithm B", ["SJF (Non-Preemptive)", "Round Robin"], index=0)
        qB = 2; 
        if algoB == "Round Robin": qB = st.number_input("Q-B", 1, 10, 2)

    if st.button("Compare Algorithms"):
        if not st.session_state.processes: st.error("No Data!")
        else:
            df1, tl1 = solve_scheduling(st.session_state.processes, algoA, qA)
            df2, tl2 = solve_scheduling(st.session_state.processes, algoB, qB)
            max_t = max(df1['ct'].max(), df2['ct'].max())
            
            g1, g2 = st.columns(2)
            with g1:
                st.subheader(f"{algoA}")
                st.plotly_chart(create_gantt_chart(tl1, max_t, color_map, 180), use_container_width=True, key="c1")
                st.write("#### Detailed Stats")
                display_stats_table(df1)

            with g2:
                st.subheader(f"{algoB}")
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

        st.subheader("📊 System Performance")
        
        idle_time = sum([s['Finish'] - s['Start'] for s in tl if s['Task'] == "Idle"])
        busy_time = total_time - idle_time
        utilization = (busy_time / total_time) * 100 if total_time > 0 else 0
        throughput = len(df) / total_time if total_time > 0 else 0
        
        m1, m2, m3 = st.columns(3)
        m1.metric("CPU Utilization", f"{round(utilization, 1)}%")
        m2.metric("Throughput", f"{round(throughput, 2)} jobs/sec")
        
        context_switches = len([s for s in tl if s['Task'] != "Idle"]) - 1
        if context_switches < 0: context_switches = 0
        m3.metric("Context Switches", context_switches)

        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = utilization,
            title = {'text': "CPU Load"},
            gauge = {'axis': {'range': [0, 100]}, 'bar': {'color': "#4ECDC4"}}
        ))
        fig_gauge.update_layout(height=250, margin=dict(l=20,r=20,t=30,b=20))
        
        df_plot = df.copy()
        df_plot["Burst"] = df_plot["bt"]
        df_plot["Wait"] = df_plot["wt"]
        
        fig_bar = px.bar(
            df_plot, x="pid", y=["Burst", "Wait"], 
            title="Time Composition per Process",
            color_discrete_map={"Burst": "#FF6B6B", "Wait": "#D3D3D3"},
            labels={"value": "Time (s)", "variable": "State"}
        )
        fig_bar.update_layout(height=300, plot_bgcolor='white')

        c1, c2 = st.columns([1, 2])
        with c1: st.plotly_chart(fig_gauge, use_container_width=True)
        with c2: st.plotly_chart(fig_bar, use_container_width=True)

        logs = "\n".join(generate_event_log(tl))
        st.download_button("📜 Download Event Logs", logs, "events.txt", "text/plain")