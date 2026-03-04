"""
F-35 Pilot Training Scheduler - MVP
A Streamlit app for scheduling F-35 pilot training events.
Future: Pyomo optimization integration for optimal scheduling.
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import random

# ─────────────────────────────────────────────
# CONFIG
# ─────────────────────────────────────────────
st.set_page_config(
    page_title="F-35 Pilot Training Scheduler",
    page_icon="✈️",
    layout="wide",
)

# ─────────────────────────────────────────────
# DATA DEFINITIONS
# ─────────────────────────────────────────────

TRAINING_EVENTS = {
    "SIM-BAS": {"label": "Basic Simulator", "duration_hrs": 2, "requires": [], "category": "Simulator"},
    "SIM-ADV": {"label": "Advanced Simulator", "duration_hrs": 3, "requires": ["SIM-BAS"], "category": "Simulator"},
    "SIM-WPN": {"label": "Weapons Systems Sim", "duration_hrs": 3, "requires": ["SIM-ADV"], "category": "Simulator"},
    "FLT-SOLO": {"label": "First Solo Flight", "duration_hrs": 1.5, "requires": ["SIM-ADV"], "category": "Flight"},
    "FLT-FORM": {"label": "Formation Flying", "duration_hrs": 2, "requires": ["FLT-SOLO"], "category": "Flight"},
    "FLT-NIT": {"label": "Night Flying", "duration_hrs": 2, "requires": ["FLT-SOLO"], "category": "Flight"},
    "FLT-WPN": {"label": "Live Weapons Training", "duration_hrs": 3, "requires": ["SIM-WPN", "FLT-FORM"], "category": "Flight"},
    "GND-ENG": {"label": "Aircraft Systems (Ground)", "duration_hrs": 4, "requires": [], "category": "Ground School"},
    "GND-TAC": {"label": "Tactical Doctrine", "duration_hrs": 4, "requires": [], "category": "Ground School"},
    "GND-EW":  {"label": "Electronic Warfare", "duration_hrs": 3, "requires": ["GND-TAC"], "category": "Ground School"},
    "MED-CHK": {"label": "Medical Checkup", "duration_hrs": 1, "requires": [], "category": "Admin"},
    "EVAL":    {"label": "Evaluation / Check Ride", "duration_hrs": 2, "requires": ["FLT-WPN", "GND-EW"], "category": "Evaluation"},
}

INSTRUCTORS = [
    {"id": "INS-01", "name": "Lt. Col. Sarah Mitchell", "specialties": ["Simulator", "Flight"]},
    {"id": "INS-02", "name": "Maj. James Ortega",       "specialties": ["Flight", "Evaluation"]},
    {"id": "INS-03", "name": "Capt. David Chen",        "specialties": ["Ground School", "Simulator"]},
    {"id": "INS-04", "name": "Lt. Col. Priya Nair",     "specialties": ["Ground School", "Evaluation"]},
]

RESOURCES = ["Simulator Bay A", "Simulator Bay B", "Aircraft #01", "Aircraft #02", "Classroom 1", "Classroom 2", "Medical Bay"]

CATEGORY_COLORS = {
    "Simulator":    "#4C72B0",
    "Flight":       "#DD8452",
    "Ground School":"#55A868",
    "Admin":        "#C44E52",
    "Evaluation":   "#8172B2",
}

# ─────────────────────────────────────────────
# SESSION STATE INIT
# ─────────────────────────────────────────────

def init_state():
    if "pilots" not in st.session_state:
        st.session_state.pilots = [
            {"id": "PLT-01", "name": "1Lt. Alex Rivera",  "status": "In Training", "completed": ["SIM-BAS", "GND-ENG"]},
            {"id": "PLT-02", "name": "1Lt. Morgan Kim",   "status": "In Training", "completed": ["SIM-BAS", "SIM-ADV", "GND-ENG", "GND-TAC"]},
            {"id": "PLT-03", "name": "2Lt. Tyler Brooks", "status": "Not Started", "completed": []},
        ]
    if "schedule" not in st.session_state:
        # Seed some sample scheduled events
        today = date.today()
        st.session_state.schedule = [
            {
                "id": 1, "pilot_id": "PLT-01", "event_code": "SIM-ADV",
                "date": str(today + timedelta(days=1)), "start_time": "09:00",
                "instructor_id": "INS-01", "resource": "Simulator Bay A", "status": "Scheduled",
            },
            {
                "id": 2, "pilot_id": "PLT-02", "event_code": "FLT-SOLO",
                "date": str(today + timedelta(days=1)), "start_time": "11:00",
                "instructor_id": "INS-02", "resource": "Aircraft #01", "status": "Scheduled",
            },
            {
                "id": 3, "pilot_id": "PLT-02", "event_code": "GND-EW",
                "date": str(today + timedelta(days=2)), "start_time": "08:00",
                "instructor_id": "INS-04", "resource": "Classroom 1", "status": "Scheduled",
            },
        ]
        st.session_state.next_id = 4

init_state()

# ─────────────────────────────────────────────
# HELPERS
# ─────────────────────────────────────────────

def get_pilot(pid):
    return next((p for p in st.session_state.pilots if p["id"] == pid), None)

def get_instructor(iid):
    return next((i for i in INSTRUCTORS if i["id"] == iid), None)

def pilot_can_take(pilot, event_code):
    """Check prerequisites are met."""
    reqs = TRAINING_EVENTS[event_code]["requires"]
    return all(r in pilot["completed"] for r in reqs)

def eligible_instructors(event_code):
    cat = TRAINING_EVENTS[event_code]["category"]
    return [i for i in INSTRUCTORS if cat in i["specialties"]]

def conflict_check(new_event):
    """Returns list of conflict messages."""
    conflicts = []
    new_date = new_event["date"]
    new_start = datetime.strptime(f"{new_date} {new_event['start_time']}", "%Y-%m-%d %H:%M")
    new_dur   = TRAINING_EVENTS[new_event["event_code"]]["duration_hrs"]
    new_end   = new_start + timedelta(hours=new_dur)

    for ev in st.session_state.schedule:
        if ev["id"] == new_event.get("id"):
            continue
        ev_date = ev["date"]
        ev_start = datetime.strptime(f"{ev_date} {ev['start_time']}", "%Y-%m-%d %H:%M")
        ev_dur   = TRAINING_EVENTS[ev["event_code"]]["duration_hrs"]
        ev_end   = ev_start + timedelta(hours=ev_dur)

        overlap = new_start < ev_end and new_end > ev_start
        if not overlap:
            continue

        # Pilot double-booked
        if ev["pilot_id"] == new_event["pilot_id"]:
            conflicts.append(f"⚠️ Pilot already has '{TRAINING_EVENTS[ev['event_code']]['label']}' at this time.")

        # Instructor double-booked
        if ev["instructor_id"] == new_event["instructor_id"]:
            conflicts.append(f"⚠️ Instructor already assigned at this time.")

        # Resource conflict
        if ev["resource"] == new_event["resource"]:
            conflicts.append(f"⚠️ Resource '{ev['resource']}' already in use at this time.")

    return conflicts

def schedule_df():
    rows = []
    for ev in st.session_state.schedule:
        pilot = get_pilot(ev["pilot_id"])
        inst  = get_instructor(ev["instructor_id"])
        info  = TRAINING_EVENTS[ev["event_code"]]
        start = datetime.strptime(f"{ev['date']} {ev['start_time']}", "%Y-%m-%d %H:%M")
        end   = start + timedelta(hours=info["duration_hrs"])
        rows.append({
            "ID": ev["id"],
            "Date": ev["date"],
            "Start": ev["start_time"],
            "End": end.strftime("%H:%M"),
            "Pilot": pilot["name"] if pilot else ev["pilot_id"],
            "Event": info["label"],
            "Category": info["category"],
            "Duration (hrs)": info["duration_hrs"],
            "Instructor": inst["name"] if inst else ev["instructor_id"],
            "Resource": ev["resource"],
            "Status": ev["status"],
        })
    return pd.DataFrame(rows).sort_values(["Date", "Start"]) if rows else pd.DataFrame()

def pilot_progress(pilot):
    all_events = list(TRAINING_EVENTS.keys())
    completed  = pilot["completed"]
    pct = len(completed) / len(all_events) * 100
    return pct, completed, [e for e in all_events if e not in completed]

# ─────────────────────────────────────────────
# UI
# ─────────────────────────────────────────────

st.title("✈️ F-35 Pilot Training Scheduler")
st.caption("MVP — Manual scheduling with conflict detection | Pyomo optimization: *coming soon*")

tabs = st.tabs(["📅 Schedule", "👨‍✈️ Pilots", "➕ Add Event", "📊 Dashboard"])

# ══════════════════════════════════════════════
# TAB 1: SCHEDULE VIEW
# ══════════════════════════════════════════════
with tabs[0]:
    st.subheader("Training Schedule")

    col1, col2, col3 = st.columns(3)
    with col1:
        filter_pilot = st.selectbox("Filter by Pilot", ["All"] + [p["name"] for p in st.session_state.pilots])
    with col2:
        filter_cat   = st.selectbox("Filter by Category", ["All"] + list(CATEGORY_COLORS.keys()))
    with col3:
        filter_status = st.selectbox("Filter by Status", ["All", "Scheduled", "Completed", "Cancelled"])

    df = schedule_df()
    if not df.empty:
        if filter_pilot != "All":
            df = df[df["Pilot"] == filter_pilot]
        if filter_cat != "All":
            df = df[df["Category"] == filter_cat]
        if filter_status != "All":
            df = df[df["Status"] == filter_status]

    if df.empty:
        st.info("No scheduled events match your filters.")
    else:
        def color_category(val):
            color = CATEGORY_COLORS.get(val, "#888")
            return f"background-color: {color}22; color: {color}; font-weight: bold;"

        styled = df.drop(columns=["ID"]).style.applymap(color_category, subset=["Category"])
        st.dataframe(styled, use_container_width=True, hide_index=True)

    # Quick actions on schedule
    st.divider()
    st.subheader("Mark Event Complete / Cancel")
    if not df.empty:
        full_df = schedule_df()
        event_opts = {f"[{row['ID']}] {row['Pilot']} — {row['Event']} on {row['Date']}": row["ID"]
                      for _, row in full_df.iterrows() if row["Status"] == "Scheduled"}
        if event_opts:
            selected_label = st.selectbox("Select event", list(event_opts.keys()))
            selected_id    = event_opts[selected_label]
            cola, colb = st.columns(2)
            with cola:
                if st.button("✅ Mark Complete"):
                    for ev in st.session_state.schedule:
                        if ev["id"] == selected_id:
                            ev["status"] = "Completed"
                            # Update pilot completed list
                            pilot = get_pilot(ev["pilot_id"])
                            if pilot and ev["event_code"] not in pilot["completed"]:
                                pilot["completed"].append(ev["event_code"])
                    st.success("Marked complete!")
                    st.rerun()
            with colb:
                if st.button("❌ Cancel Event"):
                    for ev in st.session_state.schedule:
                        if ev["id"] == selected_id:
                            ev["status"] = "Cancelled"
                    st.warning("Event cancelled.")
                    st.rerun()
        else:
            st.info("No scheduled events to action.")

# ══════════════════════════════════════════════
# TAB 2: PILOTS
# ══════════════════════════════════════════════
with tabs[1]:
    st.subheader("Pilot Roster & Training Progress")

    # Add pilot
    with st.expander("➕ Add New Pilot"):
        new_name = st.text_input("Pilot Name (e.g. 1Lt. Jane Smith)")
        if st.button("Add Pilot") and new_name.strip():
            new_id = f"PLT-{len(st.session_state.pilots)+1:02d}"
            st.session_state.pilots.append({"id": new_id, "name": new_name.strip(), "status": "Not Started", "completed": []})
            st.success(f"Added {new_name}")
            st.rerun()

    for pilot in st.session_state.pilots:
        pct, done, remaining = pilot_progress(pilot)
        with st.expander(f"**{pilot['name']}** — {pilot['status']} | {pct:.0f}% complete"):
            st.progress(pct / 100)

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**✅ Completed**")
                if done:
                    for code in done:
                        st.markdown(f"- {TRAINING_EVENTS[code]['label']}")
                else:
                    st.markdown("_None yet_")
            with c2:
                st.markdown("**🔲 Remaining**")
                if remaining:
                    for code in remaining:
                        prereqs = TRAINING_EVENTS[code]["requires"]
                        ready   = all(r in done for r in prereqs)
                        icon    = "🟢" if ready else "🔴"
                        st.markdown(f"{icon} {TRAINING_EVENTS[code]['label']}")
                else:
                    st.markdown("_All complete!_ 🎉")

            st.caption(f"Pilot ID: {pilot['id']}")

# ══════════════════════════════════════════════
# TAB 3: ADD EVENT
# ══════════════════════════════════════════════
with tabs[2]:
    st.subheader("Schedule a Training Event")

    col1, col2 = st.columns(2)
    with col1:
        sel_pilot = st.selectbox("Pilot", st.session_state.pilots, format_func=lambda p: p["name"])
        pilot_obj = sel_pilot

        # Filter to eligible events (prereqs met, not yet completed)
        eligible = {
            code: info for code, info in TRAINING_EVENTS.items()
            if code not in pilot_obj["completed"] and pilot_can_take(pilot_obj, code)
        }
        ineligible = {
            code: info for code, info in TRAINING_EVENTS.items()
            if code not in pilot_obj["completed"] and not pilot_can_take(pilot_obj, code)
        }

        if eligible:
            sel_event_code = st.selectbox(
                "Training Event",
                list(eligible.keys()),
                format_func=lambda c: f"[{TRAINING_EVENTS[c]['category']}] {TRAINING_EVENTS[c]['label']}"
            )
        else:
            st.warning("No eligible events for this pilot right now.")
            sel_event_code = None

        if ineligible:
            with st.expander(f"🔴 {len(ineligible)} events locked (prerequisites not met)"):
                for code, info in ineligible.items():
                    prereqs = ", ".join(TRAINING_EVENTS[r]["label"] for r in info["requires"] if r not in pilot_obj["completed"])
                    st.markdown(f"- **{info['label']}** — needs: _{prereqs}_")

    with col2:
        event_date  = st.date_input("Date", min_value=date.today())
        start_time  = st.time_input("Start Time", value=datetime.strptime("09:00", "%H:%M").time())

        if sel_event_code:
            inst_options = eligible_instructors(sel_event_code)
            sel_instructor = st.selectbox("Instructor", inst_options, format_func=lambda i: i["name"])

            # Suggest resource based on category
            cat = TRAINING_EVENTS[sel_event_code]["category"]
            resource_defaults = {
                "Simulator":    ["Simulator Bay A", "Simulator Bay B"],
                "Flight":       ["Aircraft #01", "Aircraft #02"],
                "Ground School":["Classroom 1", "Classroom 2"],
                "Admin":        ["Medical Bay"],
                "Evaluation":   ["Simulator Bay A", "Aircraft #01"],
            }
            suggested = resource_defaults.get(cat, RESOURCES)
            sel_resource = st.selectbox("Resource", suggested)

    if sel_event_code:
        info = TRAINING_EVENTS[sel_event_code]
        end_dt = datetime.combine(event_date, start_time) + timedelta(hours=info["duration_hrs"])
        st.info(f"⏱️ Duration: **{info['duration_hrs']} hrs** | End time: **{end_dt.strftime('%H:%M')}**")

        new_ev = {
            "id": st.session_state.next_id,
            "pilot_id": pilot_obj["id"],
            "event_code": sel_event_code,
            "date": str(event_date),
            "start_time": start_time.strftime("%H:%M"),
            "instructor_id": sel_instructor["id"],
            "resource": sel_resource,
            "status": "Scheduled",
        }

        conflicts = conflict_check(new_ev)
        if conflicts:
            for c in conflicts:
                st.warning(c)

        btn_label = "⚠️ Schedule Anyway" if conflicts else "✅ Schedule Event"
        if st.button(btn_label):
            st.session_state.schedule.append(new_ev)
            st.session_state.next_id += 1
            st.success(f"Scheduled **{info['label']}** for **{pilot_obj['name']}** on {event_date}.")
            st.rerun()

# ══════════════════════════════════════════════
# TAB 4: DASHBOARD
# ══════════════════════════════════════════════
with tabs[3]:
    st.subheader("Training Dashboard")

    df_all = schedule_df()
    total  = len(st.session_state.schedule)
    sched  = sum(1 for e in st.session_state.schedule if e["status"] == "Scheduled")
    done   = sum(1 for e in st.session_state.schedule if e["status"] == "Completed")
    canc   = sum(1 for e in st.session_state.schedule if e["status"] == "Cancelled")

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Events", total)
    m2.metric("Scheduled",    sched)
    m3.metric("Completed",    done)
    m4.metric("Cancelled",    canc)

    st.divider()

    if not df_all.empty:
        col1, col2 = st.columns(2)
        with col1:
            st.markdown("**Events by Category**")
            cat_counts = df_all["Category"].value_counts().reset_index()
            cat_counts.columns = ["Category", "Count"]
            st.bar_chart(cat_counts.set_index("Category"))

        with col2:
            st.markdown("**Pilot Progress (%)**")
            prog_data = {
                p["name"]: round(pilot_progress(p)[0], 1)
                for p in st.session_state.pilots
            }
            prog_df = pd.DataFrame(list(prog_data.items()), columns=["Pilot", "Progress (%)"])
            st.bar_chart(prog_df.set_index("Pilot"))

    st.divider()
    st.subheader("Instructor Workload")
    if not df_all.empty:
        wl = df_all[df_all["Status"] != "Cancelled"].groupby("Instructor")["Duration (hrs)"].sum().reset_index()
        wl.columns = ["Instructor", "Total Hours Assigned"]
        st.dataframe(wl, use_container_width=True, hide_index=True)

    st.divider()
    st.subheader("🔧 Optimization Placeholder")
    st.info(
        "**Pyomo integration coming next!**\n\n"
        "The optimizer will automatically find the best schedule by:\n"
        "- Minimizing total training duration\n"
        "- Respecting prerequisites & qualification windows\n"
        "- Balancing instructor workload\n"
        "- Avoiding resource conflicts\n"
        "- Factoring in pilot fatigue rules (max flight hrs/day)\n\n"
        "Once integrated, hit **'Auto-Schedule'** and Pyomo will generate an optimal plan."
    )
    if st.button("🚀 Run Optimizer (coming soon)", disabled=True):
        pass
