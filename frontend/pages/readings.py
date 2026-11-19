"""My Readings: manual data entry, quick add, editable records table, and reading/daily cost analysis."""

from datetime import datetime, time

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from components import charts
from components.layout import page_context
from components.metric_cards import badge, banner, empty_state, footer, kpi_card, section_header
from components.styles import COLORS
from services.api_client import get_client
from services.state import (active_project, append_reading, create_empty_dataset, dataset_selector,
                            project_datasets, settings, update_dataset_df)
from utils.formatting import fmt_date, fmt_energy, fmt_money, unit_factor

ss = st.session_state
cfg = settings()
unit = cfg["unit"]
tariff = float(cfg["tariff"])
currency = cfg["currency"]

proj = active_project()
if proj is None:
    empty_state("No project selected", "Readings belong to a project. Create or select a project first.", "folder")
    st.page_link("pages/projects.py", label="Go to Projects", icon=":material/arrow_forward:")
    st.stop()

# Ensure project has at least one dataset, or offer one-click log initialization
dsets = project_datasets(proj["id"])
if not dsets:
    st.title("My Readings")
    empty_state(
        "No readings log found in this project",
        f"“{proj['name']}” does not have any recorded readings or datasets yet.",
        "table_chart",
    )
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("🚀 Load 60 days of sample data", type="primary", icon=":material/rocket_launch:", width="stretch"):
            from services.state import load_demo_workspace
            load_demo_workspace(proj["id"])
            st.toast("Sample readings loaded!", icon=":material/check_circle:")
            st.rerun()
    with c2:
        if st.button("Initialize empty readings log", icon=":material/add_chart:", width="stretch"):
            did = create_empty_dataset(proj["id"], f"{proj['name']} — Meter Log")
            st.toast("Created empty readings log.", icon=":material/check_circle:")
            st.rerun()
    with c3:
        st.page_link("pages/datasets.py", label="Upload CSV / Excel file", icon=":material/upload_file:")
    footer()
    st.stop()

# Dataset selection
top_col1, top_col2 = st.columns([1.5, 1], vertical_alignment="bottom")
with top_col1:
    ds = dataset_selector("Select dataset / meter log", key="readings_ds")
with top_col2:
    if st.button("Create additional reading log", icon=":material/add:", width="stretch"):
        did = create_empty_dataset(proj["id"], f"{proj['name']} — Log {len(dsets) + 1}")
        st.toast("New readings log created.", icon=":material/check_circle:")
        st.rerun()

if ds is None:
    st.stop()

df = ds["df"].copy()
time_col = ds["time_col"]
target_col = ds["target_col"]

# Ensure timestamp is datetime
if time_col in df.columns:
    df[time_col] = pd.to_datetime(df[time_col], errors="coerce")
    df = df.dropna(subset=[time_col]).sort_values(time_col).reset_index(drop=True)

# ----------------- TABS -----------------
tab_table, tab_entry, tab_avp = st.tabs([
    f"My Data Table ({len(df):,} records)",
    "Manual Data Entry & Quick Add",
    "Actual vs Predicted",
])


# =========================================================================
# TAB 1: My Data Table & Edit/Delete Records & Cost Breakdown
# =========================================================================
with tab_table:
    if df.empty:
        st.info("No records in this dataset. Switch to the 'Manual Data Entry' tab to add your first reading.")
    else:
        min_date = df[time_col].min().date()
        max_date = df[time_col].max().date()

        # Date and search filters
        f_col1, f_col2, f_col3 = st.columns([1.4, 1.2, 1], vertical_alignment="bottom")
        with f_col1:
            date_filter = st.date_input(
                "Filter by date",
                value=(max(min_date, max_date - pd.Timedelta(days=29)), max_date),
                min_value=min_date,
                max_value=max_date,
                key="tbl_date_filter",
            )
        with f_col2:
            quick_f = st.segmented_control("Quick range", ["7D", "30D", "90D", "All"], default=None, key="tbl_quick")
        with f_col3:
            search_query = st.text_input("Search notes/data", placeholder="Filter rows...", key="tbl_search")

        if quick_f:
            q_days = {"7D": 7, "30D": 30, "90D": 90}.get(quick_f)
            start_dt = pd.Timestamp(min_date) if q_days is None else pd.Timestamp(max_date) - pd.Timedelta(days=q_days - 1)
            end_dt = pd.Timestamp(max_date)
        elif isinstance(date_filter, (tuple, list)) and len(date_filter) == 2:
            start_dt = pd.Timestamp(date_filter[0])
            end_dt = pd.Timestamp(date_filter[1])
        else:
            start_dt, end_dt = pd.Timestamp(min_date), pd.Timestamp(max_date)

        filtered_mask = (df[time_col].dt.date >= start_dt.date()) & (df[time_col].dt.date <= end_dt.date())
        view_df = df[filtered_mask].copy()

        if search_query.strip():
            q = search_query.strip().lower()
            str_cols = view_df.select_dtypes(include=["object", "string"]).columns
            text_mask = view_df[str_cols].apply(lambda row: row.astype(str).str.lower().str.contains(q).any(), axis=1) if len(str_cols) else False
            view_df = view_df[text_mask]

        # Calculate costs per reading
        f_unit = unit_factor(unit)
        view_df["reading_cost"] = (view_df[target_col] * tariff).round(4)

        # Summary KPIs
        k1, k2, k3, k4 = st.columns(4)
        with k1:
            kpi_card("Readings in view", f"{len(view_df):,}", f"of {len(df):,} total", icon_name="activity", tone="navy")
        with k2:
            tot_energy = float(view_df[target_col].sum())
            kpi_card("Total consumption", fmt_energy(tot_energy, unit), f"{start_dt:%d %b} – {end_dt:%d %b %Y}", icon_name="zap", tone="blue")
        with k3:
            tot_cost = float(view_df["reading_cost"].sum())
            kpi_card("Total estimated cost", fmt_money(tot_cost, currency), f"Tariff: {tariff:.3f} {currency}/kWh", icon_name="dollar", tone="green")
        with k4:
            n_days = max(1, (end_dt.date() - start_dt.date()).days + 1)
            avg_daily_cost = tot_cost / n_days
            kpi_card("Avg cost per day", fmt_money(avg_daily_cost, currency), f"across {n_days} days", icon_name="trending-up", tone="amber")

        st.write("")
        section_header(
            "Editable records table",
            "Directly edit values or delete rows. Click 'Save Changes' to update the dataset.",
        )

        # Prepare editable view
        display_df = view_df.copy()
        
        # Format columns for display in editor
        column_config = {
            time_col: st.column_config.DatetimeColumn(
                "Timestamp *",
                help="Date and time of the meter reading",
                format="YYYY-MM-DD HH:mm",
                required=True,
            ),
            target_col: st.column_config.NumberColumn(
                f"Consumption ({unit}) *",
                help=f"Energy consumption in {unit}",
                format="%.3f",
                min_value=0.0,
                required=True,
            ),
            "reading_cost": st.column_config.NumberColumn(
                f"Cost ({currency})",
                help=f"Calculated reading cost at {tariff:.3f} {currency}/kWh",
                format=f"{currency} %.4f" if currency != "USD" else "$%.4f",
                disabled=True,
            ),
        }

        edited_data = st.data_editor(
            display_df,
            num_rows="dynamic",
            use_container_width=True,
            column_config=column_config,
            key=f"editor_{ds['id']}_{len(view_df)}",
        )

        b1, b2, b3 = st.columns([1.2, 1.2, 1.5])
        with b1:
            save_clicked = st.button("Save changes", type="primary", icon=":material/save:", width="stretch")
        with b2:
            if st.button("Reset changes", icon=":material/restart_alt:", width="stretch"):
                st.rerun()
        with b3:
            st.download_button(
                "Download table (CSV)",
                view_df.to_csv(index=False).encode("utf-8"),
                file_name=f"{ds['name'].replace(' ', '_').lower()}_readings.csv",
                mime="text/csv",
                icon=":material/download:",
                width="stretch",
            )

        # Process and validate edits on save
        if save_clicked:
            validation_errors = []
            
            # Check for missing required columns
            if time_col not in edited_data.columns or target_col not in edited_data.columns:
                validation_errors.append("Required columns (timestamp or consumption) are missing.")
            else:
                # 1. Missing values
                null_ts = int(edited_data[time_col].isna().sum())
                null_target = int(edited_data[target_col].isna().sum())
                if null_ts > 0:
                    validation_errors.append(f"{null_ts} row(s) have missing timestamps.")
                if null_target > 0:
                    validation_errors.append(f"{null_target} row(s) have missing consumption values.")

                # 2. Negative values
                numeric_target = pd.to_numeric(edited_data[target_col], errors="coerce")
                neg_count = int((numeric_target < 0).sum())
                if neg_count > 0:
                    validation_errors.append(f"{neg_count} reading(s) have negative consumption. Values must be ≥ 0.")

                # 3. Duplicate timestamps
                parsed_ts = pd.to_datetime(edited_data[time_col], errors="coerce")
                dup_count = int(parsed_ts.duplicated().sum())
                if dup_count > 0:
                    validation_errors.append(f"{dup_count} duplicate timestamp(s) found. Each reading must have a unique timestamp.")

            if validation_errors:
                for err in validation_errors:
                    st.error(err, icon=":material/error:")
            else:
                # Merge edited view back into the full dataframe
                # Clean up computed columns before storing
                clean_edited = edited_data.drop(columns=["reading_cost"], errors="ignore").copy()
                clean_edited[time_col] = pd.to_datetime(clean_edited[time_col])

                # Replace the rows in the filtered period with the edited ones
                other_rows = df[~filtered_mask].copy()
                merged_df = pd.concat([other_rows, clean_edited], ignore_index=True)
                merged_df = merged_df.sort_values(time_col).reset_index(drop=True)

                update_dataset_df(ds["id"], merged_df)
                st.toast("Reading records updated successfully!", icon=":material/check_circle:")
                st.rerun()

        # ----------------- Daily Cost Breakdown Section -----------------
        st.divider()
        section_header(
            "Cost of each day",
            "Daily breakdown showing aggregated consumption and the exact electricity cost per day.",
        )

        daily_df = view_df.copy()
        daily_df["date"] = daily_df[time_col].dt.date
        daily_summary = daily_df.groupby("date").agg(
            readings_count=(target_col, "count"),
            daily_consumption=(target_col, "sum"),
            daily_cost=("reading_cost", "sum"),
            peak_reading=(target_col, "max"),
        ).reset_index()

        c_left, c_right = st.columns([1.5, 1])
        with c_left:
            # Bar chart of daily cost
            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=[d.strftime("%a %d %b") for d in daily_summary["date"]],
                y=daily_summary["daily_cost"],
                marker_color=COLORS["green"],
                name="Cost",
                hovertemplate="%{x}<br>Cost: " + currency + " %{y:,.2f}<extra></extra>",
            ))
            fig.update_layout(
                height=300,
                margin=dict(l=8, r=8, t=12, b=8),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(family="Inter, Segoe UI, sans-serif", size=12, color="#334155"),
                hovermode="x unified",
                xaxis=dict(showgrid=False, linecolor=COLORS["border"]),
                yaxis=dict(gridcolor="#EEF2F6", title=dict(text=f"Cost ({currency})", font=dict(size=11, color=COLORS["muted"]))),
            )
            charts.show(fig, key="daily_cost_chart")

        with c_right:
            display_daily = daily_summary.copy()
            display_daily["date"] = pd.to_datetime(display_daily["date"])
            st.dataframe(
                display_daily,
                hide_index=True,
                use_container_width=True,
                height=300,
                column_config={
                    "date": st.column_config.DateColumn("Date", format="DD/MM/YYYY"),
                    "readings_count": st.column_config.NumberColumn("Readings"),
                    "daily_consumption": st.column_config.NumberColumn(f"Total ({unit})", format="%.2f"),
                    "daily_cost": st.column_config.NumberColumn(f"Cost ({currency})", format=f"{currency} %.2f"),
                    "peak_reading": st.column_config.NumberColumn(f"Peak ({unit})", format="%.2f"),
                },
            )


# =========================================================================
# TAB 2: Manual Data Entry Form & Quick Add Reading
# =========================================================================
with tab_entry:
    section_header(
        "Manual Data Entry Form",
        "Log a new meter reading. Values are validated immediately for missing fields, negative values, and duplicates.",
    )

    # Fetch last reading for Quick Add defaults
    last_reading = ss.get("last_manual_reading")
    if not last_reading and not df.empty:
        last_row = df.iloc[-1]
        last_reading = {
            "consumption": float(last_row[target_col]),
            "temp": float(last_row["temperature_c"]) if "temperature_c" in last_row and pd.notna(last_row["temperature_c"]) else 25.0,
            "humid": float(last_row["humidity_pct"]) if "humidity_pct" in last_row and pd.notna(last_row["humidity_pct"]) else 60.0,
            "notes": str(last_row["notes"]) if "notes" in last_row and pd.notna(last_row["notes"]) else "",
        }

    # Quick Add Button Bar
    qa_col1, qa_col2 = st.columns([2, 1], vertical_alignment="center")
    with qa_col1:
        st.markdown(
            "💡 **Quick add reading**: Automatically populates the current date, time, and your last logged readings."
        )
    with qa_col2:
        if st.button("⚡ Quick Add (Now + Last values)", icon=":material/bolt:", width="stretch", type="secondary"):
            ss["entry_date"] = datetime.now().date()
            ss["entry_time"] = datetime.now().time()
            if last_reading:
                ss["entry_consumption"] = float(last_reading.get("consumption", 5.0))
                ss["entry_temp"] = float(last_reading.get("temp", 25.0))
                ss["entry_humid"] = float(last_reading.get("humid", 60.0))
                ss["entry_notes"] = str(last_reading.get("notes", "Quick add reading"))
            st.toast("Pre-filled form with current timestamp and last values.", icon=":material/check_circle:")
            st.rerun()

    st.write("")

    # Form inputs with session defaults
    now_dt = datetime.now()
    default_date = ss.get("entry_date", now_dt.date())
    default_time = ss.get("entry_time", now_dt.time())
    default_val = ss.get("entry_consumption", float(last_reading["consumption"]) if last_reading else 5.0)
    default_temp = ss.get("entry_temp", float(last_reading["temp"]) if last_reading else 25.0)
    default_humid = ss.get("entry_humid", float(last_reading["humid"]) if last_reading else 60.0)
    default_notes = ss.get("entry_notes", "")

    with st.form("manual_entry_form", border=True):
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            in_date = st.date_input("Date *", value=default_date, key="in_form_date")
        with col_t2:
            in_time = st.time_input("Time *", value=default_time, step=300, key="in_form_time")

        st.divider()

        col_v1, col_v2, col_v3 = st.columns(3)
        with col_v1:
            in_consumption = st.number_input(
                f"Consumption ({unit}) *",
                value=float(default_val),
                min_value=0.0,
                max_value=50000.0,
                step=0.1,
                format="%.3f",
                help="Meter reading or appliance energy consumption",
            )
        with col_v2:
            in_temp = st.number_input(
                "Temperature (°C) [optional]",
                value=float(default_temp),
                min_value=-50.0,
                max_value=60.0,
                step=0.5,
                format="%.1f",
            )
        with col_v3:
            in_humid = st.number_input(
                "Humidity (%) [optional]",
                value=float(default_humid),
                min_value=0.0,
                max_value=100.0,
                step=1.0,
                format="%.1f",
            )

        in_notes = st.text_input(
            "Notes / Tag [optional]",
            value=default_notes,
            placeholder="e.g. Afternoon peak, AC running, solar charging...",
            max_chars=120,
        )

        # Dynamic Cost Preview
        est_cost = in_consumption * tariff
        st.markdown(
            f"<div style='background-color:#F0FDF4; border:1px solid #BBF7D0; border-radius:6px; padding:10px; margin-top:8px;'>"
            f"💰 <b>Estimated reading cost:</b> <span style='color:#16A34A; font-weight:600;'>{fmt_money(est_cost, currency)}</span> "
            f"<span style='color:#64748B; font-size:0.85rem;'>(at {tariff:.3f} {currency}/kWh)</span></div>",
            unsafe_allow_html=True,
        )

        st.write("")
        submit_entry = st.form_submit_button("Add reading to project", type="primary", icon=":material/add:")

    # Real-time Input Validation & Submission Handling
    if submit_entry:
        selected_dt = datetime.combine(in_date, in_time)
        errors = []

        # 1. Missing timestamp or value
        if not in_date or not in_time:
            errors.append("Date and time are required.")
        if in_consumption is None:
            errors.append("Energy consumption value is required.")

        # 2. Negative validation
        if in_consumption < 0:
            errors.append("Negative energy consumption values are not permitted.")

        # 3. Out of range check
        if in_consumption > 10000.0:
            errors.append("Consumption exceeds typical safety limits (> 10,000 kWh). Please verify.")

        # 4. Duplicate reading check
        if time_col in df.columns:
            existing_timestamps = pd.to_datetime(df[time_col]).dt.floor("min")
            target_ts = pd.Timestamp(selected_dt).floor("min")
            if (existing_timestamps == target_ts).any():
                errors.append(f"Duplicate reading! A reading at {selected_dt.strftime('%Y-%m-%d %H:%M')} already exists in this project.")

        # Render errors or save
        if errors:
            for err in errors:
                st.error(err, icon=":material/error:")
        else:
            new_record = {
                time_col: selected_dt,
                target_col: float(in_consumption),
                "temperature_c": float(in_temp),
                "humidity_pct": float(in_humid),
                "notes": in_notes.strip(),
            }
            append_reading(ds["id"], new_record)

            # Save state for Quick Add
            ss["last_manual_reading"] = {
                "consumption": in_consumption,
                "temp": in_temp,
                "humid": in_humid,
                "notes": in_notes,
            }
            # Clear input state
            ss.pop("entry_date", None)
            ss.pop("entry_time", None)

            st.toast(
                f"Added reading: {in_consumption:.2f} {unit} on {selected_dt.strftime('%d %b %Y, %H:%M')}",
                icon=":material/check_circle:",
            )
            st.rerun()


# =========================================================================
# TAB 3: Actual vs Predicted
# =========================================================================
with tab_avp:
    section_header(
        "Actual vs Predicted Comparison",
        "Compare recorded energy consumption directly against ML model predictions.",
    )

    if df.empty:
        st.info("No readings available to compare.")
    else:
        # Check backend availability for inference
        client = get_client()
        with st.spinner("Checking model connection..."):
            health = client.health()

        c_info1, c_info2 = st.columns([2, 1])
        with c_info1:
            st.markdown(
                "Select a reading from your records to run through the trained energy prediction model."
            )
        with c_info2:
            if health.ok:
                badge("ML Model Ready", "real")
            else:
                badge("ML Backend Offline", "demo")

        recent_df = df.tail(30).copy()
        reading_options = {
            i: f"{r[time_col]:%d %b %Y %H:%M} — Actual: {r[target_col]:.2f} {unit}"
            for i, r in recent_df.iterrows()
        }

        selected_idx = st.selectbox(
            "Select recorded reading to evaluate",
            list(reading_options.keys()),
            format_func=lambda i: reading_options[i],
        )

        chosen = recent_df.loc[selected_idx]
        actual_val = float(chosen[target_col])
        ts_val = chosen[time_col]

        # In appliances dataset, unit is Wh or kWh
        actual_wh = actual_val if unit == "Wh" else actual_val * 1000.0

        st.write("")
        cmp1, cmp2, cmp3 = st.columns(3)
        with cmp1:
            kpi_card("Recorded actual", f"{actual_wh:,.1f} Wh", f"Logged on {ts_val:%d %b %Y, %H:%M}", icon_name="zap", tone="navy")

        # Call predict if backend is available or provide benchmark
        if health.ok:
            # Prepare payload matching backend model requirements
            payload = {
                "timestamp": ts_val.isoformat(),
                "lights": 10.0,
                "T1": float(chosen.get("temperature_c", 20.0)),
                "T2": float(chosen.get("temperature_c", 20.0)),
                "T3": float(chosen.get("temperature_c", 20.0)),
                "T4": float(chosen.get("temperature_c", 20.0)),
                "T5": float(chosen.get("temperature_c", 20.0)),
                "T6": float(chosen.get("temperature_c", 20.0)),
                "T7": float(chosen.get("temperature_c", 20.0)),
                "T8": float(chosen.get("temperature_c", 20.0)),
                "T9": float(chosen.get("temperature_c", 20.0)),
                "RH_1": float(chosen.get("humidity_pct", 50.0)),
                "RH_2": float(chosen.get("humidity_pct", 50.0)),
                "RH_3": float(chosen.get("humidity_pct", 50.0)),
                "RH_4": float(chosen.get("humidity_pct", 50.0)),
                "RH_5": float(chosen.get("humidity_pct", 50.0)),
                "RH_6": float(chosen.get("humidity_pct", 50.0)),
                "RH_7": float(chosen.get("humidity_pct", 50.0)),
                "RH_8": float(chosen.get("humidity_pct", 50.0)),
                "RH_9": float(chosen.get("humidity_pct", 50.0)),
                "T_out": float(chosen.get("temperature_c", 20.0)),
                "Press_mm_hg": 755.0,
                "RH_out": float(chosen.get("humidity_pct", 50.0)),
                "Windspeed": 4.0,
                "Visibility": 40.0,
                "Tdewpoint": 10.0,
            }
            res = client.predict(payload)
            if res.ok:
                pred_wh = res.data["predicted_energy_wh"]
                diff = actual_wh - pred_wh
                diff_pct = (diff / max(1.0, actual_wh)) * 100.0

                with cmp2:
                    kpi_card("Model predicted", f"{pred_wh:,.1f} Wh", res.data["model_name"], icon_name="check", tone="blue")
                with cmp3:
                    tone = "green" if abs(diff_pct) < 15 else "amber" if abs(diff_pct) < 30 else "red"
                    kpi_card("Variance (Actual − Pred)", f"{diff:+,.1f} Wh", f"{diff_pct:+.1f}% deviation", icon_name="activity", tone=tone)
            else:
                with cmp2:
                    kpi_card("Model predicted", "—", res.error or "Error", icon_name="info", tone="amber")
        else:
            with cmp2:
                kpi_card("Model predicted", "Backend offline", "Start backend server", icon_name="info", tone="amber")
            with cmp3:
                kpi_card("Variance", "—", "Awaiting backend", icon_name="activity", tone="navy")

footer()
