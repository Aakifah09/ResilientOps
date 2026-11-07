# ResilientOps — Technology Operational Resilience Monitoring Platform

ResilientOps is a **demonstration prototype**. It shows how an organisation could track technology incidents and service disruptions. It is built with Python, Streamlit, Plotly and SQLite.

> ⚠️ **Disclaimer:** all incidents, services, teams and uptime figures are **fictional**. This is not a real-time production monitoring system, and it is not connected to any real telemetry. It contains no data, branding or logos from any real company.

---

## Features

| Area | What it does |
|---|---|
| **Executive Dashboard** | KPIs for total, critical, open, resolved and overdue incidents, plus SLA compliance, MTTR, average availability and incidents at risk. Weekly trend, root cause, severity mix, category and SLA charts. Filter by date, category and severity. |
| **Incident Register** | Searchable, filterable table showing ID, title, affected service, severity, dates, root cause, assigned team, status, SLA status and recovery progress. Click a row to see full details and the timeline. Export the current view to CSV. |
| **Create / Edit Incident** | Create incidents with automatic IDs (`INC-10xx`). Edit or delete existing incidents. Every change is written to the incident timeline. |
| **Severity Classification** | A rules-based assistant suggests a severity from customer impact, scope, financial impact, workaround availability and data/security risk. You can override the suggestion. |
| **Service Availability** | Availability per service against its target (99.5%–99.99%), with a daily trend, a heatmap and downtime totals. It is calculated from sample uptime data minus the downtime of recorded incidents, so new incidents affect availability. |
| **SLA & Overdue** | Resolution targets by severity: Critical 4h, High 8h, Medium 24h, Low 72h. Each incident is marked Met, Breached, Within SLA, At Risk (≥75% of target used) or Overdue. Includes an overdue list and compliance by severity and by team. |
| **Recovery Tracker** | Progress through the stages Detected → Triaged → Contained → Recovering → Restored → Post-Incident Review. Shows progress bars, a recovery path chart for each incident, and a form to log updates. |
| **Export & Admin** | Seven CSV reports and a one-click reset of the demo data. |
| **Persistence** | SQLite database stored at `data/resilientops.db`, created automatically on first run. |

The sample data has **26 fictional incidents** covering card payment processing, settlement, payouts, public and partner APIs, core and ledger databases, SSO, MFA and OAuth. Dates are set relative to the first run, so open, at-risk and overdue examples are always present.

---

## Windows installation

### Prerequisites
- **Windows 10 or 11**
- **Python 3.10 or newer** from <https://www.python.org/downloads/windows/>. During installation, tick **"Add python.exe to PATH"**.

To check your version, open **Command Prompt** or **PowerShell** and run:
```powershell
python --version
```

### 1. Open a terminal in the project folder
```powershell
cd C:\path\to\ResilientOps
```

### 2. Create and activate a virtual environment
**PowerShell:**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
If PowerShell blocks the activation script, run this once, then try again:
```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

**Command Prompt (cmd.exe):**
```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

### 3. Install dependencies
```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 4. Run the app
```powershell
streamlit run app.py
```
The app opens in your browser at <http://localhost:8501>. Press `Ctrl+C` in the terminal to stop it.

### Optional: run the smoke test
```powershell
python smoke_test.py
```
This checks the database layer and renders every page headlessly with Streamlit's testing framework. It uses a temporary database, so your data is not touched.

---

## Project structure

```
ResilientOps/
├── app.py            # Streamlit UI: all pages, charts and forms
├── database.py       # SQLite schema, CRUD, SLA rules, availability and severity logic
├── seed_data.py      # 26 fictional incidents and their recovery timelines
├── smoke_test.py     # Automated checks (data layer + headless page rendering)
├── requirements.txt
├── README.md
└── data/
    └── resilientops.db   # created automatically on first run
```

## Data model (SQLite)

- `services`: name, category, tier, availability target
- `incidents`: id, title, service, severity, status, reported/resolved timestamps, root cause, assigned team, description, customer impact, recovery stage and progress
- `incident_updates`: timeline entries (stage, progress, note) for each incident
- `uptime_samples`: daily sample baseline uptime for each service

## Business rules

- **Statuses:** Open, Investigating and Mitigating count as *open*. Resolved and Closed count as *resolved*. Setting an incident to Resolved or Closed records the resolution time automatically. Reopening it clears that time.
- **SLA:** the clock runs from the reported time to the resolved time, or to now if the incident is still open.
- **Availability:** daily availability = sample baseline − (incident duration × severity downtime factor). The factors are Critical 90%, High 40%, Medium 12% and Low 2%. Downtime is split across each day the incident spans.
- **Recovery:** logging progress of 90% or more on an open incident marks it Resolved.

## Resetting data

Use **Export & Admin → Reset demonstration data**, or stop the app and delete `data\resilientops.db`. The database is rebuilt on the next start.

## Troubleshooting

| Problem | Fix |
|---|---|
| `'streamlit' is not recognized` | Activate the virtual environment first, or run `python -m streamlit run app.py`. |
| Port 8501 already in use | `streamlit run app.py --server.port 8502` |
| Charts or tables look wrong after upgrading | `pip install -r requirements.txt --upgrade` |
| Want a clean start | Delete `data\resilientops.db` and restart. |
