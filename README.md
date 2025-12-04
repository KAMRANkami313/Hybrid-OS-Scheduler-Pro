# **Hybrid OS CPU Scheduler Pro**

A high-performance hybrid CPU scheduling simulator combining **Python**, **C++**, and **Streamlit**, designed to visualize and compare popular CPU scheduling algorithms using Gantt charts and detailed metrics.
This project uses **C++ for computation speed** and **Python for UI + visualization**, delivering both accuracy and efficiency.

---

## 🚀 **Features**

* Supports **6 major CPU scheduling algorithms**:

  * **FCFS (First Come First Serve)**
  * **SJF (Non-Preemptive)**
  * **SRTF (Preemptive SJF)**
  * **Priority (Non-Preemptive)**
  * **Priority (Preemptive)**
  * **Round Robin**
* C++ backend for:

  * Fast scheduling computation
  * Accurate Gantt log generation
  * Efficient CPU time tracking
* Python wrapper using **ctypes**
* Streamlit-based modern GUI
* Automatic Gantt chart visualization
* Table of results including:

  * Completion Time (CT)
  * Turnaround Time (TAT)
  * Waiting Time (WT)
* Idle time handling
* Clean and simple project structure

---

## 📌 **Project Architecture**

```
CPUScheduler/
│
├── app.py                 # Streamlit UI
├── scheduler.cpp          # C++ scheduling engine
├── scheduler.dll          # Compiled C++ library (Windows)
├── scheduler_wrapper.py   # Python <-> C++ bridge
├── .gitignore
└── README.md
```

---

## 🛠 **Requirements**

### **System Requirements**

* OS: Windows (because DLL is provided)
* Python 3.8+
* C++ compiler (only needed if you want to recompile DLL)

### **Python Packages**

Install these with pip:

```
pip install streamlit pandas
```

### **Included Files**

No need to compile anything if `scheduler.dll` is already present.

---

## 📥 **How to Clone the Repository**

Run:

```bash
git clone https://github.com/KAMRANkami313/Hybrid-OS-Scheduler-Pro.git
```

Navigate into the project:

```bash
cd Hybrid-OS-Scheduler-Pro
```

---

## ⚙️ **Installation**

### Step 1 — Create Virtual Environment (Recommended)

```bash
python -m venv venv
```

Activate it:

```bash
venv\Scripts\activate
```

### Step 2 — Install Dependencies

```bash
pip install -r requirements.txt
```

If you don’t have a requirements file, install manually:

```bash
pip install streamlit pandas
```

---

## ▶️ **How to Run the Project**

After activating the virtual environment, run:

```bash
streamlit run app.py
```

Your browser will open automatically with the UI.

---

## 🧠 **How the Application Works**

### 1. **User Inputs Processes**

* PID (P1, P2, ...)
* Arrival Time
* Burst Time
* Priority (optional)
* Quantum (for RR)

### 2. **Python Validates Data**

### 3. **Python → C++ via ctypes**

`scheduler_wrapper.py` prepares:

* Process structure
* Algorithm code
* Log buffers

It then calls:

```
run_scheduler()
```

from `scheduler.dll`.

### 4. **C++ Computes Scheduling**

* Tracks time
* Generates Gantt logs
* Updates CT, TAT, WT

### 5. **Backend returns results to Python**

### 6. **Streamlit Visualizes**

* Gantt chart
* Performance metrics
* Process table

---

## 🔧 **Compiling the C++ Code (Optional)**

If you want to build the DLL yourself:

### Using MinGW:

```bash
g++ -shared -o scheduler.dll scheduler.cpp -static
```

### Using MSVC:

```bash
cl /LD scheduler.cpp /o scheduler.dll
```

DLL must remain in the same folder as `app.py`.

---

## 📊 **Supported Scheduling Algorithms**

| Algorithm   | Preemptive | Description                   |
| ----------- | ---------- | ----------------------------- |
| FCFS        | No         | Executes in arrival order     |
| SJF         | No         | Shortest job first            |
| SRTF        | Yes        | Shortest remaining time first |
| Priority    | No         | Lowest priority first         |
| Priority-P  | Yes        | Can preempt based on priority |
| Round Robin | Yes        | Time-sharing with quantum     |

---

## 🧪 **Sample Output Table**

| PID | AT | BT | Priority | CT | TAT | WT |
| --- | -- | -- | -------- | -- | --- | -- |
| P1  | 0  | 5  | 1        | 10 | 10  | 5  |

---

## 🛡 **Error Handling**

* Invalid PID formats automatically corrected
* Missing fields handled gracefully
* Supports up to **1000 Gantt entries**

---

## 🛠 **Future Improvements**

* Add Multi-Level Queue scheduling
* Add CPU utilization & throughput metrics
* Add exporting results to PDF/CSV
* Dark mode UI
* Web-hosted version via Streamlit Cloud

---

## 🤝 **Contributing**

Pull requests are welcome.
For major changes, open an issue first.

---

## 📄 **License**

This project is licensed under the **KAMRANkami313** — free for academic and personal use.

---

