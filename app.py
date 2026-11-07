"""ResilientOps — Technology Operational Resilience Monitoring Platform.

Demonstration prototype using fictional data. Run with:  streamlit run app.py
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import plotly.express as px
import streamlit as st

import database as db

st.set_page_config(page_title="ResilientOps", page_icon="🛡️", layout="wide")

SEV_COLORS = {"Critical": "#C0392B", "High": "#E67E22", "Medium": "#D4AC0D", "Low": "#2E86C1"}
SLA_COLORS = {"Met": "#2E7D32", "Within SLA": "#1565C0", "At Risk": "#EF6C00",
              "Breached": "#C62828", "Overdue": "#8E0000"}
STATUS_COLORS = {"Open": "#C0392B", "Investigating": "#E67E22", "Mitigating": "#D4AC0D",
                 "Resolved": "#27AE60", "Closed": "#7F8C8D"}

PAGES = ["📊 Executive Dashboard", "📋 Incident Register", "✏️ Create / Edit Incident",
         "🟢 Service Availability", "⏱️ SLA & Overdue", "🔧 Recovery Tracker", "📤 Export & Admin"]

st.markdown(
    """
    <style>
      .block-container {padding-top: 1.6rem;}
      .ro-banner {background: linear-gradient(90deg,#0B2545,#13315C); color:#fff;
                  padding:14px 20px; border-radius:10px; margin-bottom:14px;}
      .ro-banner h2 {margin:0; color:#fff; font-size:1.5rem;}
      .ro-banner p {margin:2px 0 0 0; color:#C9D6EA; font-size:0.9rem;}
      .sev-pill {padding:2px 10px; border-radius:12px; color:#fff; font-weight:600; font-size:0.8rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_resource
def _bootstrap() -> bool:
    db.init_db()
    return True


_bootstrap()


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------
def banner(title: str, subtitle: str) -> None:
    st.markdown(f'<div class="ro-banner"><h2>{title}</h2><p>{subtitle}</p></div>', unsafe_allow_html=True)


def sev_pill(sev: str) -> str:
    return f'<span class="sev-pill" style="background:{SEV_COLORS.get(sev, "#555")}">{sev}</span>'


def flash() -> None:
    msg = st.session_state.pop("flash", None)
    if msg:
        st.success(msg, icon="✅")


def go_edit(inc_id: str) -> None:
    st.session_state["nav"] = PAGES[2]
    st.session_state["edit_target"] = inc_id


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    """Columns used in the register / exports, with readable names."""
    out = df[["id", "title", "service", "category", "severity", "status", "reported_at", "resolved_at",
              "root_cause", "assigned_team", "sla_target_hrs", "elapsed_hrs", "sla_status",
              "recovery_stage", "recovery_progress"]].copy()
    out["reported_at"] = out["reported_at"].dt.strftime("%Y-%m-%d %H:%M")
    out["resolved_at"] = out["resolved_at"].dt.strftime("%Y-%m-%d %H:%M").fillna("—")
    return out


TABLE_CONFIG = {
    "id": st.column_config.TextColumn("Incident ID", width="small"),
    "title": st.column_config.TextColumn("Title", width="large"),
    "service": "Affected Service",
    "category": "Category",
    "severity": "Severity",
    "status": "Status",
    "reported_at": "Reported",
    "resolved_at": "Resolved",
    "root_cause": "Root Cause",
    "assigned_team": "Assigned Team",
    "sla_target_hrs": st.column_config.NumberColumn("SLA (h)", format="%d"),
    "elapsed_hrs": st.column_config.NumberColumn("Elapsed (h)", format="%.1f"),
    "sla_status": "SLA Status",
    "recovery_stage": "Recovery Stage",
    "recovery_progress": st.column_config.ProgressColumn("Recovery", min_value=0, max_value=100, format="%d%%"),
    "hours_overdue": st.column_config.NumberColumn("Hours Overdue", format="%.1f"),
}


def style_sla(df: pd.DataFrame):
    def color(v):
        c = SLA_COLORS.get(v)
        return f"color:{c}; font-weight:600" if c else ""

    def sev(v):
        c = SEV_COLORS.get(v)
        return f"color:{c}; font-weight:600" if c else ""

    styler = df.style
    if "sla_status" in df:
        styler = styler.map(color, subset=["sla_status"])
    if "severity" in df:
        styler = styler.map(sev, subset=["severity"])
    return styler


def to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")


def chart(fig, height: int = 340) -> None:
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      legend=dict(orientation="h", yanchor="bottom", y=1.02, x=0))
    st.plotly_chart(fig, width="stretch")


# --------------------------------------------------------------------------
# Pages
# --------------------------------------------------------------------------
def page_dashboard(df: pd.DataFrame) -> None:
    banner("Executive Dashboard", "Operational resilience posture across critical technology services")

    c1, c2, c3 = st.columns([1.3, 1.5, 1.5])
    min_d = df["reported_at"].min().date()
    rng = c1.date_input("Reporting period", (max(min_d, date.today() - timedelta(days=90)), date.today()),
                        min_value=min_d - timedelta(days=365), max_value=date.today())
    cats = c2.multiselect("Service category", sorted(df["category"].unique()), placeholder="All categories")
    sevs = c3.multiselect("Severity", db.SEVERITIES, placeholder="All severities")

    # date_input returns a 1-tuple while the user is mid-selection
    if isinstance(rng, (tuple, list)) and len(rng) == 2:
        start, end = rng
    elif isinstance(rng, (tuple, list)) and len(rng) == 1:
        start = end = rng[0]
    else:
        start, end = min_d, date.today()
    f = df[(df["reported_at"].dt.date >= start) & (df["reported_at"].dt.date <= end)]
    if cats:
        f = f[f["category"].isin(cats)]
    if sevs:
        f = f[f["severity"].isin(sevs)]

    resolved = f[~f["is_open"]]
    sla_pct = (resolved["sla_status"] == "Met").mean() * 100 if len(resolved) else 0
    mttr = resolved["resolution_hrs"].mean() if len(resolved) else 0

    av = db.load_availability()
    av = av[(av["day"].dt.date >= start) & (av["day"].dt.date <= end)]
    if cats:
        av = av[av["category"].isin(cats)]
    avg_av = av["availability"].mean() if len(av) else 100

    k = st.columns(5)
    k[0].metric("Total incidents", len(f), border=True)
    k[1].metric("Critical", int((f["severity"] == "Critical").sum()), border=True)
    k[2].metric("Open", int(f["is_open"].sum()), border=True)
    k[3].metric("Resolved", int((~f["is_open"]).sum()), border=True)
    k[4].metric("Overdue (SLA)", int(f["is_overdue"].sum()), border=True,
                delta="needs action" if f["is_overdue"].any() else None, delta_color="inverse")
    k = st.columns(5)
    k[0].metric("SLA compliance", f"{sla_pct:.0f}%", border=True, help="Resolved incidents closed within target")
    k[1].metric("Mean time to resolve", f"{mttr:.1f} h", border=True)
    k[2].metric("Avg service availability", f"{avg_av:.3f}%", border=True)
    k[3].metric("Open Critical/High", int((f["is_open"] & f["severity"].isin(["Critical", "High"])).sum()), border=True)
    k[4].metric("At risk of breach", int((f["sla_status"] == "At Risk").sum()), border=True)

    if f.empty:
        st.info("No incidents match the selected filters.")
        return

    left, right = st.columns([3, 2])
    with left:
        wk = (f.groupby([pd.Grouper(key="reported_at", freq="W-MON", label="left", closed="left"), "severity"])
              .size().reset_index(name="incidents"))
        fig = px.bar(wk, x="reported_at", y="incidents", color="severity", color_discrete_map=SEV_COLORS,
                     category_orders={"severity": db.SEVERITIES}, title="Weekly incident trend by severity",
                     labels={"reported_at": "Week commencing", "incidents": "Incidents"})
        chart(fig)
    with right:
        rc = f["root_cause"].value_counts().reset_index()
        rc.columns = ["root_cause", "incidents"]
        fig = px.bar(rc.sort_values("incidents"), x="incidents", y="root_cause", orientation="h",
                     title="Root cause analysis", color_discrete_sequence=["#13315C"],
                     labels={"root_cause": "", "incidents": "Incidents"})
        chart(fig)

    a, b, c = st.columns(3)
    with a:
        fig = px.pie(f, names="severity", hole=0.55, title="Severity mix", color="severity",
                     color_discrete_map=SEV_COLORS, category_orders={"severity": db.SEVERITIES})
        chart(fig, 320)
    with b:
        sc = f.groupby(["category", "status"]).size().reset_index(name="incidents")
        fig = px.bar(sc, x="category", y="incidents", color="status", color_discrete_map=STATUS_COLORS,
                     category_orders={"status": db.STATUSES}, title="Incidents by service category",
                     labels={"category": ""})
        chart(fig, 320)
    with c:
        sl = f["sla_status"].value_counts().reset_index()
        sl.columns = ["sla_status", "incidents"]
        fig = px.bar(sl, x="sla_status", y="incidents", color="sla_status", color_discrete_map=SLA_COLORS,
                     title="SLA position", labels={"sla_status": ""})
        fig.update_layout(showlegend=False)
        chart(fig, 320)

    st.subheader("Open incidents requiring attention")
    openf = f[f["is_open"]].sort_values(["is_overdue", "sla_used_pct"], ascending=False)
    if openf.empty:
        st.success("No open incidents in the selected period.")
    else:
        cols = ["id", "title", "service", "severity", "status", "assigned_team", "elapsed_hrs",
                "sla_target_hrs", "sla_status", "recovery_progress"]
        st.dataframe(style_sla(openf[cols]), hide_index=True, width="stretch", column_config=TABLE_CONFIG)


def page_register(df: pd.DataFrame) -> None:
    banner("Incident Register", "Full log of technology incidents and service disruptions")
    flash()

    c = st.columns([2, 1, 1, 1.4, 1.4])
    q = c[0].text_input("Search", placeholder="ID, title, description…")
    sev = c[1].multiselect("Severity", db.SEVERITIES)
    status = c[2].multiselect("Status", db.STATUSES)
    svc = c[3].multiselect("Service", sorted(df["service"].unique()))
    team = c[4].multiselect("Team", db.TEAMS)
    t1, t2, _ = st.columns([1, 1, 4])
    only_open = t1.toggle("Open only")
    only_overdue = t2.toggle("Overdue only")

    f = df.copy()
    if q:
        ql = q.lower()
        f = f[f["id"].str.lower().str.contains(ql, regex=False)
              | f["title"].str.lower().str.contains(ql, regex=False)
              | f["description"].fillna("").str.lower().str.contains(ql, regex=False)]
    for col, vals in (("severity", sev), ("status", status), ("service", svc), ("assigned_team", team)):
        if vals:
            f = f[f[col].isin(vals)]
    if only_open:
        f = f[f["is_open"]]
    if only_overdue:
        f = f[f["is_overdue"]]

    h1, h2 = st.columns([4, 1])
    h1.caption(f"Showing **{len(f)}** of {len(df)} incidents · select a row to view details")
    h2.download_button("⬇️ Export view (CSV)", to_csv(display_table(f)) if len(f) else b"",
                       file_name=f"incident_register_{date.today()}.csv", mime="text/csv",
                       width="stretch", disabled=f.empty)

    if f.empty:
        st.info("No incidents match the filters.")
        return
    table = display_table(f)
    event = st.dataframe(style_sla(table), hide_index=True, width="stretch", height=430,
                         column_config=TABLE_CONFIG, on_select="rerun", selection_mode="single-row",
                         key="register_table")
    rows = event.selection.rows if event and event.selection else []
    if rows:
        inc_id = table.iloc[rows[0]]["id"]
        r = f[f["id"] == inc_id].iloc[0]
        with st.container(border=True):
            top = st.columns([4, 1])
            top[0].markdown(f"### {r['id']} — {r['title']} &nbsp; {sev_pill(r['severity'])}",
                            unsafe_allow_html=True)
            top[1].button("✏️ Edit incident", on_click=go_edit, args=(inc_id,), width="stretch")
            d = st.columns(4)
            d[0].markdown(f"**Service**<br>{r['service']}<br><small>{r['category']} · {r['tier']}</small>",
                          unsafe_allow_html=True)
            d[1].markdown(f"**Status**<br>{r['status']}<br><small>Team: {r['assigned_team']}</small>",
                          unsafe_allow_html=True)
            d[2].markdown(f"**Root cause**<br>{r['root_cause']}<br><small>Reported {r['reported_at']:%d %b %Y %H:%M}</small>",
                          unsafe_allow_html=True)
            d[3].markdown(f"**SLA**<br>{r['sla_status']} ({r['elapsed_hrs']}h / {r['sla_target_hrs']}h)",
                          unsafe_allow_html=True)
            st.markdown(f"**Description:** {r['description'] or '—'}")
            st.markdown(f"**Customer impact:** {r['customer_impact'] or '—'}")
            st.progress(int(r["recovery_progress"]) / 100, text=f"Recovery: {r['recovery_stage']} ({r['recovery_progress']}%)")
            with st.expander("Incident timeline"):
                st.dataframe(db.get_updates(inc_id), hide_index=True, width="stretch")


def incident_fields(prefix: str, defaults: dict, suggested_sev: str | None = None) -> dict:
    """Render the shared incident form fields and return the values."""
    services = list(db.SERVICES)
    c = st.columns([3, 2])
    title = c[0].text_input("Incident title *", defaults.get("title", ""), key=f"{prefix}_title")
    service = c[1].selectbox("Affected service *", services,
                             index=services.index(defaults.get("service", services[0])), key=f"{prefix}_svc")
    c = st.columns(4)
    sev_default = suggested_sev or defaults.get("severity", "Medium")
    severity = c[0].selectbox("Severity *", db.SEVERITIES, index=db.SEVERITIES.index(sev_default),
                              key=f"{prefix}_sev_{sev_default}",
                              help=f"SLA targets: " + ", ".join(f"{k} {v}h" for k, v in db.SLA_HOURS.items()))
    status = c[1].selectbox("Status *", db.STATUSES, index=db.STATUSES.index(defaults.get("status", "Open")),
                            key=f"{prefix}_status")
    root = c[2].selectbox("Root cause *", db.ROOT_CAUSES,
                          index=db.ROOT_CAUSES.index(defaults.get("root_cause", "Under Investigation")),
                          key=f"{prefix}_root")
    team = c[3].selectbox("Assigned team *", db.TEAMS, index=db.TEAMS.index(defaults.get("assigned_team", db.TEAMS[0])),
                          key=f"{prefix}_team")
    c = st.columns(4)
    rep: datetime = defaults.get("reported_at", db.now())
    rep_date = c[0].date_input("Reported date *", rep.date(), max_value=date.today(), key=f"{prefix}_rdate")
    rep_time = c[1].time_input("Reported time *", rep.time(), key=f"{prefix}_rtime", step=300)
    stages = list(db.RECOVERY_STAGES)
    stage = c[2].selectbox("Recovery stage", stages, index=stages.index(defaults.get("recovery_stage", "Detected")),
                           key=f"{prefix}_stage")
    progress = c[3].slider("Recovery progress %", 0, 100, int(defaults.get("recovery_progress", db.RECOVERY_STAGES[stage])),
                           step=5, key=f"{prefix}_prog")
    desc = st.text_area("Description", defaults.get("description", "") or "", height=90, key=f"{prefix}_desc")
    impact = st.text_area("Customer / business impact", defaults.get("customer_impact", "") or "", height=70,
                          key=f"{prefix}_impact")
    return {
        "title": title.strip(), "service": service, "severity": severity, "status": status,
        "root_cause": root, "assigned_team": team,
        "reported_at": datetime.combine(rep_date, rep_time).strftime(db.DT_FMT),
        "recovery_stage": stage, "recovery_progress": progress,
        "description": desc.strip(), "customer_impact": impact.strip(),
    }


def validate(data: dict) -> list[str]:
    errors = []
    if len(data["title"]) < 5:
        errors.append("Title must be at least 5 characters.")
    if datetime.strptime(data["reported_at"], db.DT_FMT) > db.now() + timedelta(minutes=5):
        errors.append("Reported date/time cannot be in the future.")
    return errors


def page_manage(df: pd.DataFrame) -> None:
    banner("Create / Edit Incident", "Log new disruptions, classify severity and maintain incident records")
    flash()
    target = st.session_state.get("edit_target")
    tab_new, tab_edit = st.tabs(["➕ Create new incident", "✏️ Edit existing incident"])

    with tab_new:
        v = st.session_state.setdefault("create_version", 0)
        with st.expander("🧭 Severity classification assistant", expanded=True):
            st.caption("Answer the impact questions to get a recommended severity. You can override it below.")
            a = st.columns(5)
            cf = a[0].checkbox("Customer-facing", True, key=f"cls_cf_{v}")
            scope = a[1].selectbox("Impact scope", ["Single user / internal", "Single team or region",
                                                    "Multiple regions / partners", "All customers"],
                                   index=1, key=f"cls_scope_{v}")
            fin = a[2].selectbox("Financial impact", ["None", "Low (< £10k)", "Medium (£10k–£250k)", "High (> £250k)"],
                                 index=1, key=f"cls_fin_{v}")
            wa = a[3].checkbox("Workaround available", True, key=f"cls_wa_{v}")
            dr = a[4].checkbox("Data / security risk", False, key=f"cls_dr_{v}")
            sev, score, reasons = db.classify_severity(cf, scope, fin, wa, dr)
            st.markdown(f"Recommended severity: {sev_pill(sev)} &nbsp; score **{score}** "
                        f"· resolution SLA **{db.SLA_HOURS[sev]}h**", unsafe_allow_html=True)
            st.caption(" · ".join(reasons))
        with st.container(border=True):
            data = incident_fields(f"new{v}", {}, suggested_sev=sev)
            st.caption(f"New incident will be assigned ID **{db.next_incident_id()}**")
            if st.button("💾 Create incident", type="primary"):
                errs = validate(data)
                if errs:
                    for e in errs:
                        st.error(e)
                else:
                    new_id = db.create_incident(data)
                    st.session_state["create_version"] = v + 1
                    st.session_state["flash"] = f"Incident {new_id} created ({data['severity']})."
                    st.rerun()

    with tab_edit:
        if df.empty:
            st.info("No incidents yet.")
            return
        ids = df.sort_values("id", ascending=False)["id"].tolist()
        labels = {i: f"{i} — {t}" for i, t in zip(df["id"], df["title"])}
        idx = ids.index(target) if target in ids else 0
        if target in ids:
            st.info(f"Editing **{target}** (opened from the register).", icon="✏️")
        inc_id = st.selectbox("Select incident", ids, index=idx, format_func=lambda i: labels[i], key="edit_select")
        inc = db.get_incident(inc_id)
        inc["reported_at"] = datetime.strptime(inc["reported_at"], db.DT_FMT)
        ev = st.session_state.setdefault("edit_version", 0)
        with st.form(f"edit_form_{inc_id}_{ev}"):
            data = incident_fields(f"edit_{inc_id}_{ev}", inc)
            note = st.text_input("Change note (added to incident timeline)", key=f"edit_note_{inc_id}_{ev}")
            st.caption(f"Created {inc['created_at']} · last updated {inc['updated_at']}"
                       + (f" · resolved {inc['resolved_at']}" if inc["resolved_at"] else ""))
            saved = st.form_submit_button("💾 Save changes", type="primary")
        if saved:
            errs = validate(data)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                db.update_incident(inc_id, data, note.strip() or None)
                st.session_state["edit_version"] = ev + 1
                st.session_state["edit_target"] = inc_id
                st.session_state["flash"] = f"Incident {inc_id} updated."
                st.rerun()
        with st.expander("🗑️ Delete incident"):
            confirm = st.checkbox(f"I confirm I want to permanently delete {inc_id}", key=f"del_{inc_id}")
            if st.button("Delete", disabled=not confirm, key=f"delbtn_{inc_id}"):
                db.delete_incident(inc_id)
                st.session_state.pop("edit_target", None)
                st.session_state["flash"] = f"Incident {inc_id} deleted."
                st.rerun()


def page_availability() -> None:
    banner("Service Availability", "Daily availability derived from sample uptime telemetry and incident downtime")
    av = db.load_availability()
    c = st.columns([1, 2])
    days = c[0].selectbox("Period", [7, 30, 90], index=1, format_func=lambda d: f"Last {d} days")
    cats = c[1].multiselect("Category", sorted(av["category"].unique()), placeholder="All categories")
    cutoff = pd.Timestamp(date.today() - timedelta(days=days - 1))
    a = av[av["day"] >= cutoff]
    if cats:
        a = a[a["category"].isin(cats)]
    if a.empty:
        st.info("No availability data for this selection.")
        return

    summ = (a.groupby(["service", "category", "tier", "target_availability"])
            .agg(availability=("availability", "mean"), downtime_min=("downtime_min", "sum"),
                 worst_day=("availability", "min")).reset_index())
    summ["availability"] = summ["availability"].round(3)
    summ["downtime_min"] = summ["downtime_min"].round(0)
    summ["gap"] = (summ["availability"] - summ["target_availability"]).round(3)
    summ["status"] = summ["gap"].apply(lambda g: "✅ Meeting target" if g >= 0 else "❌ Below target")
    summ = summ.sort_values("gap")

    k = st.columns(4)
    meeting = (summ["gap"] >= 0).sum()
    k[0].metric("Services meeting target", f"{meeting} / {len(summ)}", border=True)
    k[1].metric("Average availability", f"{a['availability'].mean():.3f}%", border=True)
    worst = summ.iloc[0]
    k[2].metric("Lowest availability", f"{worst['availability']:.3f}%", border=True, help=worst["service"])
    k[3].metric("Total downtime", f"{summ['downtime_min'].sum() / 60:.1f} h", border=True)

    fig = px.bar(summ.sort_values("availability"), x="availability", y="service", orientation="h",
                 color="status", color_discrete_map={"✅ Meeting target": "#2E7D32", "❌ Below target": "#C62828"},
                 title=f"Availability vs target — last {days} days", labels={"service": "", "availability": "Availability %"},
                 hover_data={"target_availability": True, "downtime_min": True})
    fig.add_scatter(x=summ["target_availability"], y=summ["service"], mode="markers", name="Target",
                    marker=dict(symbol="line-ns-open", size=18, color="#111", line=dict(width=3)))
    fig.update_xaxes(range=[max(min(summ["availability"].min(), summ["target_availability"].min()) - 0.1, 90), 100.02])
    chart(fig, 380)

    st.dataframe(
        summ[["service", "category", "tier", "target_availability", "availability", "gap", "downtime_min", "worst_day", "status"]],
        hide_index=True, width="stretch",
        column_config={
            "service": "Service", "category": "Category", "tier": "Tier",
            "target_availability": st.column_config.NumberColumn("Target %", format="%.2f"),
            "availability": st.column_config.NumberColumn("Actual %", format="%.3f"),
            "gap": st.column_config.NumberColumn("Gap (pp)", format="%+.3f"),
            "downtime_min": st.column_config.NumberColumn("Downtime (min)", format="%d"),
            "worst_day": st.column_config.NumberColumn("Worst day %", format="%.2f"),
            "status": "Status",
        },
    )

    left, right = st.columns(2)
    with left:
        svcs = st.multiselect("Services for trend", sorted(a["service"].unique()),
                              default=summ["service"].head(3).tolist())
        if svcs:
            fig = px.line(a[a["service"].isin(svcs)], x="day", y="availability", color="service", markers=True,
                          title="Daily availability trend", labels={"day": "", "availability": "Availability %"})
            chart(fig, 380)
    with right:
        piv = a.pivot_table(index="service", columns="day", values="availability")
        piv.columns = [d.strftime("%d %b") for d in piv.columns]
        fig = px.imshow(piv, aspect="auto", color_continuous_scale="RdYlGn", zmin=98.5, zmax=100,
                        title="Availability heatmap (%)", labels=dict(color="%"))
        chart(fig, 430)


def page_sla(df: pd.DataFrame) -> None:
    banner("SLA Tracking & Overdue Incidents", "Resolution performance against severity-based targets")
    resolved = df[~df["is_open"]]
    k = st.columns(5)
    k[0].metric("SLA compliance", f"{(resolved['sla_status'] == 'Met').mean() * 100:.0f}%" if len(resolved) else "—",
                border=True)
    k[1].metric("Resolved within SLA", int((resolved["sla_status"] == "Met").sum()), border=True)
    k[2].metric("Resolved but breached", int((resolved["sla_status"] == "Breached").sum()), border=True)
    k[3].metric("Open & overdue", int(df["is_overdue"].sum()), border=True)
    k[4].metric("Open & at risk (≥75%)", int((df["sla_status"] == "At Risk").sum()), border=True)

    with st.expander("SLA policy (resolution targets)"):
        st.dataframe(pd.DataFrame({"Severity": list(db.SLA_HOURS), "Resolution target (hours)": list(db.SLA_HOURS.values()),
                                   "At-risk threshold": ["75% of target"] * 4}), hide_index=True)

    st.subheader("🚨 Overdue incidents")
    od = df[df["is_overdue"]].sort_values("hours_overdue", ascending=False)
    if od.empty:
        st.success("No overdue incidents. 🎉")
    else:
        cols = ["id", "title", "service", "severity", "status", "assigned_team", "sla_target_hrs",
                "elapsed_hrs", "hours_overdue", "recovery_progress"]
        st.dataframe(style_sla(od[cols]), hide_index=True, width="stretch", column_config=TABLE_CONFIG)
        st.button("✏️ Edit most overdue incident", on_click=go_edit, args=(od.iloc[0]["id"],))

    risk = df[df["sla_status"] == "At Risk"]
    if not risk.empty:
        st.subheader("⚠️ At risk of breach")
        risk = risk.assign(time_left_hrs=(risk["sla_target_hrs"] - risk["elapsed_hrs"]).round(1))
        st.dataframe(risk[["id", "title", "service", "severity", "assigned_team", "elapsed_hrs", "sla_target_hrs",
                           "time_left_hrs"]], hide_index=True, width="stretch",
                     column_config={**TABLE_CONFIG, "time_left_hrs": st.column_config.NumberColumn("Time left (h)", format="%.1f")})

    a, b = st.columns(2)
    with a:
        bs = df.groupby(["severity", "sla_status"]).size().reset_index(name="incidents")
        fig = px.bar(bs, x="severity", y="incidents", color="sla_status", color_discrete_map=SLA_COLORS,
                     category_orders={"severity": db.SEVERITIES}, title="SLA outcome by severity",
                     labels={"severity": ""})
        chart(fig)
    with b:
        if len(resolved):
            bt = resolved.groupby("assigned_team").apply(
                lambda g: pd.Series({"compliance": (g["sla_status"] == "Met").mean() * 100, "incidents": len(g)}),
                include_groups=False).reset_index().sort_values("compliance")
            fig = px.bar(bt, x="compliance", y="assigned_team", orientation="h", text="incidents",
                         title="SLA compliance by team (resolved, label = count)", range_x=[0, 105],
                         color="compliance", color_continuous_scale="RdYlGn", range_color=[0, 100],
                         labels={"assigned_team": "", "compliance": "Compliance %"})
            chart(fig)

    fig = px.scatter(df, x="reported_at", y="sla_used_pct", color="sla_status", color_discrete_map=SLA_COLORS,
                     symbol="severity", hover_data=["id", "title", "elapsed_hrs", "sla_target_hrs"],
                     title="Time taken as % of SLA target (100% = target)",
                     labels={"reported_at": "Reported", "sla_used_pct": "% of SLA used"})
    fig.add_hline(y=100, line_dash="dash", line_color="#C62828", annotation_text="SLA target")
    fig.update_yaxes(type="log")
    chart(fig, 380)


def page_recovery(df: pd.DataFrame) -> None:
    banner("Recovery Progress Tracker", "Track restoration of disrupted services through recovery stages")
    flash()
    openf = df[df["is_open"]].sort_values("recovery_progress")
    if openf.empty:
        st.success("All incidents are resolved. 🎉")
    else:
        fig = px.bar(openf, x="recovery_progress", y="id", orientation="h", color="severity",
                     color_discrete_map=SEV_COLORS, text="recovery_stage", range_x=[0, 100],
                     hover_data=["title", "service", "assigned_team"],
                     title="Recovery progress — open incidents", labels={"id": "", "recovery_progress": "Progress %"})
        chart(fig, 120 + 45 * len(openf))

        cols = st.columns(3)
        for i, (_, r) in enumerate(openf.iterrows()):
            with cols[i % 3].container(border=True):
                st.markdown(f"**{r['id']}** {sev_pill(r['severity'])}<br>{r['title']}<br>"
                            f"<small>{r['service']} · {r['assigned_team']} · SLA: {r['sla_status']}</small>",
                            unsafe_allow_html=True)
                st.progress(int(r["recovery_progress"]) / 100,
                            text=f"{r['recovery_stage']} — {r['recovery_progress']}%")

    st.divider()
    st.subheader("Incident recovery timeline")
    choices = openf["id"].tolist() + df[~df["is_open"]]["id"].tolist()
    labels = {i: f"{i} — {t} ({s})" for i, t, s in zip(df["id"], df["title"], df["status"])}
    inc_id = st.selectbox("Incident", choices, format_func=lambda i: labels[i])
    upd = db.get_updates(inc_id)
    left, right = st.columns([3, 2])
    with left:
        if not upd.empty:
            u = upd.assign(logged_at=pd.to_datetime(upd["logged_at"]))
            fig = px.line(u, x="logged_at", y="progress", markers=True, text="stage", range_y=[0, 110],
                          title=f"{inc_id} recovery path", labels={"logged_at": "", "progress": "Progress %"})
            fig.update_traces(textposition="top center", line_color="#13315C")
            chart(fig, 330)
        st.dataframe(upd, hide_index=True, width="stretch",
                     column_config={"logged_at": "Logged", "stage": "Stage",
                                    "progress": st.column_config.ProgressColumn("Progress", min_value=0, max_value=100, format="%d%%"),
                                    "note": "Note"})
    with right:
        inc = db.get_incident(inc_id)
        with st.form(f"recovery_{inc_id}", clear_on_submit=True):
            st.markdown("**Log recovery update**")
            stages = list(db.RECOVERY_STAGES)
            stage = st.selectbox("Stage", stages, index=stages.index(inc["recovery_stage"]))
            prog = st.slider("Progress %", 0, 100, int(inc["recovery_progress"]), step=5,
                             help="Reaching 90%+ on an open incident marks it Resolved.")
            note = st.text_area("Update note", placeholder="e.g. Hotfix deployed to 50% of nodes")
            if st.form_submit_button("Add update", type="primary"):
                db.add_recovery_update(inc_id, stage, prog, note.strip())
                st.session_state["flash"] = f"Recovery update logged for {inc_id}."
                st.rerun()


def page_export(df: pd.DataFrame) -> None:
    banner("Export & Admin", "Download reports as CSV and manage demonstration data")
    flash()
    with db.get_conn() as conn:
        updates = pd.read_sql_query("SELECT * FROM incident_updates ORDER BY incident_id, logged_at", conn)
    av = db.load_availability()
    av_summary = (av.groupby(["service", "category", "target_availability"])
                  .agg(availability_pct=("availability", "mean"), downtime_min=("downtime_min", "sum"))
                  .round(3).reset_index())
    full = df.drop(columns=["is_open", "is_overdue"]).copy()
    sla_cols = ["id", "title", "service", "severity", "status", "reported_at", "resolved_at", "sla_target_hrs",
                "sla_due", "elapsed_hrs", "sla_used_pct", "sla_status", "hours_overdue"]
    today = date.today()
    reports = [
        ("Full incident register", "All incidents with SLA fields", full, "incident_register"),
        ("Open incidents", "Incidents not yet resolved", full[df["is_open"]], "open_incidents"),
        ("Overdue incidents", "Open incidents past SLA target", full[df["is_overdue"]], "overdue_incidents"),
        ("SLA report", "SLA performance for every incident", df[sla_cols], "sla_report"),
        ("Availability summary", "Per-service availability (full history)", av_summary, "availability_summary"),
        ("Daily availability", "Daily availability by service", av[["day", "service", "category", "availability", "downtime_min"]], "daily_availability"),
        ("Recovery update log", "All incident timeline entries", updates, "recovery_updates"),
    ]
    cols = st.columns(2)
    for i, (name, desc, data, fname) in enumerate(reports):
        with cols[i % 2].container(border=True):
            st.markdown(f"**{name}** · {len(data)} rows")
            st.caption(desc)
            st.download_button(f"⬇️ Download {fname}.csv", to_csv(data), file_name=f"{fname}_{today}.csv",
                               mime="text/csv", key=f"dl_{fname}", disabled=data.empty)

    st.divider()
    st.subheader("Admin")
    st.caption(f"Database file: `{db.DB_PATH}`")
    with st.expander("♻️ Reset demonstration data"):
        st.warning("This deletes all incidents (including any you created) and reloads the fictional sample data.")
        ok = st.checkbox("I understand — reset the database")
        if st.button("Reset demo data", disabled=not ok):
            db.init_db(force_reset=True)
            for k in ("edit_target", "register_table"):
                st.session_state.pop(k, None)
            st.session_state["flash"] = "Demo data reset."
            st.rerun()


# --------------------------------------------------------------------------
# Layout
# --------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 🛡️ ResilientOps")
    st.caption("Technology Operational Resilience Monitoring")
    page = st.radio("Navigation", PAGES, key="nav", label_visibility="collapsed")
    st.divider()
    incidents = db.load_incidents()
    if not incidents.empty:
        st.metric("Open incidents", int(incidents["is_open"].sum()))
        st.metric("Overdue", int(incidents["is_overdue"].sum()))
    st.caption(f"Data as of {db.now():%d %b %Y %H:%M}")
    if st.button("🔄 Refresh", width="stretch"):
        st.rerun()
    st.divider()
    st.caption("⚠️ Demonstration prototype with fictional data. "
               "Not a real-time production monitoring system.")

# Leaving the edit page clears any "open from register" target
if page != PAGES[2] and st.session_state.get("_last_page") == PAGES[2]:
    st.session_state.pop("edit_target", None)
st.session_state["_last_page"] = page

if incidents.empty and page not in (PAGES[2], PAGES[6]):
    st.info("No incidents recorded. Create one or reset demo data from Export & Admin.")
elif page == PAGES[0]:
    page_dashboard(incidents)
elif page == PAGES[1]:
    page_register(incidents)
elif page == PAGES[2]:
    page_manage(incidents)
elif page == PAGES[3]:
    page_availability()
elif page == PAGES[4]:
    page_sla(incidents)
elif page == PAGES[5]:
    page_recovery(incidents)
elif page == PAGES[6]:
    page_export(incidents)
