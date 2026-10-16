"""Model Lab: configure, train and compare forecasting models with a chronological holdout."""

import numpy as np
import pandas as pd
import streamlit as st

from components import charts
from components.layout import page_context
from components.metric_cards import badge, banner, empty_state, footer, section_header
from services.api_client import get_client
from services.data_service import prepare_series
from services.forecast_service import (BACKEND_MODELS, DEFAULT_PARAMS, LOCAL_MODELS, chronological_split,
                                       evaluate_local_model)
from services.state import dataset_selector, select_id, settings, touch
from utils.formatting import fmt_date, fmt_energy

ss = st.session_state
proj, ds = page_context("Model Lab", "Train candidate models on a chronological split and compare how they perform on unseen data.")
cfg = settings()
unit = cfg["unit"]
experiments = ss.experiments.setdefault(proj["id"], [])

GLOSSARY = {
    "MAE": "Mean Absolute Error — the average size of a miss, in energy units. Lower is better.",
    "RMSE": "Root Mean Squared Error — like MAE but punishes large misses more. Lower is better.",
    "MAPE": "Mean Absolute Percentage Error — average miss as % of actual. Undefined when actuals are near zero.",
    "R²": "Coefficient of determination — share of variation explained. 1 is perfect, 0 equals predicting the mean.",
}

tab_cfg, tab_res, tab_det = st.tabs(["Configure & train", f"Results ({len(experiments)})", "Experiment details"])

# ======================= Configure =======================
with tab_cfg:
    left, right = st.columns([1, 1.25], gap="large")
    with left:
        section_header("Data", "What the models learn from")
        ds = dataset_selector("Dataset", key="ml_ds")
        df = ds["df"]
        cols = list(df.columns)
        numeric = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
        a, b = st.columns(2)
        time_col = a.selectbox("Time column", cols, index=cols.index(ds["time_col"]) if ds["time_col"] in cols else 0)
        target = b.selectbox("Target variable", numeric or cols,
                             index=(numeric or cols).index(ds["target_col"]) if ds["target_col"] in (numeric or cols) else 0)
        weather_opts = [c for c in numeric if c not in (time_col, target)]
        weather = st.multiselect("Exogenous features", weather_opts,
                                 default=[c for c in ds["weather_cols"] if c in weather_opts],
                                 help="Used only by Linear Regression when 'Use weather features' is on. "
                                      "Test-period weather is treated as known (an optimistic assumption).")
        series, native = prepare_series(df, time_col, target, weather)
        freq_opts = ["Daily", "Hourly"] if native == "hourly" else ["Daily"]
        freq_label = st.radio("Frequency", freq_opts, horizontal=True)
        freq = freq_label.lower()
        if freq == "daily" and native == "hourly":
            agg = {c: ("sum" if c == "y" else "mean") for c in series.columns}
            series = series.resample("D").agg(agg)

        section_header("Chronological split", "Time order is preserved — no random shuffling, so no look-ahead leakage")
        c1, c2 = st.columns(2)
        train_pct = c1.slider("Train %", 50, 85, 70, 5)
        val_pct = c2.slider("Validation %", 5, 25, 15, 5)
        test_pct = 100 - train_pct - val_pct
        if test_pct < 5:
            st.error("Test split must be at least 5%. Reduce train or validation.")
        else:
            tr, va, te = chronological_split(len(series), train_pct, val_pct)
            idx = series.index
            splits = {"train": (idx[tr][0], idx[tr][-1]), "val": (idx[va][0], idx[va][-1]), "test": (idx[te][0], idx[te][-1])}
            charts.show(charts.split_timeline(splits), key="ml_split")
            st.caption(f"Train {tr.stop - tr.start:,} · validation {va.stop - va.start:,} · test {te.stop - te.start:,} "
                       f"{'hours' if freq == 'hourly' else 'days'}  (test = {test_pct}%)")

    with right:
        section_header("Models", "Local models train here; backend models are sent to the FastAPI service")
        options = list(LOCAL_MODELS) + list(BACKEND_MODELS)
        chosen = st.multiselect("Models to train", options, default=list(LOCAL_MODELS),
                                format_func=lambda m: f"{m} · local" if m in LOCAL_MODELS else f"{m} · backend")
        params = {}
        for m in chosen:
            p = dict(DEFAULT_PARAMS.get(m, {}))
            with st.expander(f"{m} hyperparameters", icon=":material/tune:"):
                st.caption({**LOCAL_MODELS, **BACKEND_MODELS}[m])
                if m == "Seasonal Naive":
                    st.caption("No hyperparameters.")
                elif m == "Seasonal Average":
                    p["weeks"] = st.slider("Weeks to average", 1, 8, p["weeks"], key=f"hp_{m}_weeks")
                elif m == "Linear Regression":
                    p["alpha"] = st.number_input("Ridge alpha", 0.0, 100.0, float(p["alpha"]), 0.5, key=f"hp_{m}_alpha",
                                                 help="Regularisation strength. Higher values shrink coefficients.")
                    p["use_weather"] = st.checkbox("Use weather features", value=bool(weather), disabled=not weather,
                                                   key=f"hp_{m}_weather")
                else:
                    for k, v in p.items():
                        if isinstance(v, str):
                            p[k] = st.text_input(k, v, key=f"hp_{m}_{k}")
                        elif isinstance(v, int):
                            p[k] = st.number_input(k, value=v, step=1, key=f"hp_{m}_{k}")
                        else:
                            p[k] = st.number_input(k, value=float(v), format="%.3f", key=f"hp_{m}_{k}")
            params[m] = p

        backend_chosen = [m for m in chosen if m in BACKEND_MODELS]
        if backend_chosen:
            banner(f"{', '.join(backend_chosen)} will be submitted to <b>POST /training-jobs</b>. If the backend is not "
                   "reachable, they are reported as <b>not run</b> — no results are invented.", kind="info")
        train = st.button("Train models", type="primary", width="stretch", icon=":material/model_training:",
                          disabled=not chosen or test_pct < 5)

    if train:
        exp_id = f"EXP-{len(experiments) + 1:03d}"
        results = []
        progress = st.progress(0.0, text="Preparing data…")
        with st.status(f"Running {exp_id}…", expanded=True) as status:
            local = [m for m in chosen if m in LOCAL_MODELS]
            for i, m in enumerate(local):
                progress.progress(i / max(len(chosen), 1), text=f"Training {m} ({i + 1}/{len(chosen)})")
                st.write(f"Training **{m}** on the train split, scoring on validation and test…")
                try:
                    results.append(evaluate_local_model(series, freq, m, params[m], train_pct, val_pct))
                    st.write(f"✓ {m} finished in {results[-1]['duration_s']:.2f} s")
                except (ValueError, np.linalg.LinAlgError) as exc:
                    results.append({"model": m, "status": "Failed", "error": str(exc), "source": "local"})
                    st.write(f"✗ {m} failed: {exc}")
            backend_info = None
            if backend_chosen:
                progress.progress(len(local) / max(len(chosen), 1), text="Submitting backend models…")
                st.write(f"Submitting {', '.join(backend_chosen)} to the ML backend…")
                api = get_client().create_training_job({
                    "dataset_id": ds["id"], "target": target, "time_col": time_col, "frequency": freq,
                    "features": weather, "models": {m: params[m] for m in backend_chosen},
                    "split": {"train_pct": train_pct, "val_pct": val_pct, "test_pct": test_pct, "shuffle": False},
                })
                ss.backend_status = api.ok
                if api.ok:
                    job_id = (api.data or {}).get("job_id", "unknown")
                    backend_info = {"job_id": job_id, "status": "Submitted"}
                    st.write(f"✓ Backend job `{job_id}` submitted. Refresh it from the Results tab.")
                    results += [{"model": m, "status": "Submitted", "source": "backend", "job_id": job_id} for m in backend_chosen]
                else:
                    backend_info = {"error": api.error, "status": "Unavailable"}
                    st.write(f"✗ Backend unavailable: {api.error}")
                    results += [{"model": m, "status": "Not run", "source": "backend", "error": api.error} for m in backend_chosen]
            progress.progress(1.0, text="Done")
            n_ok = sum(r["status"] == "Completed" for r in results)
            status.update(label=f"{exp_id}: {n_ok} of {len(chosen)} models completed",
                          state="complete" if n_ok else "error", expanded=False)

        experiments.append({
            "id": exp_id, "created": pd.Timestamp.now(), "dataset_name": ds["name"], "dataset_source": ds["source"],
            "target": target, "time_col": time_col, "freq": freq, "features": weather,
            "split_pct": (train_pct, val_pct, test_pct), "results": results, "backend": backend_info,
        })
        touch(proj["id"])
        st.toast(f"{exp_id} finished — open the Results tab.", icon=":material/check_circle:")

# ======================= Results =======================
def _ranking(exp: dict) -> pd.DataFrame:
    rows = []
    for r in exp["results"]:
        if r["status"] != "Completed":
            continue
        t, v = r["test_metrics"], r["val_metrics"]
        rows.append({"Model": r["model"], "MAE": t["MAE"], "RMSE": t["RMSE"], "MAPE": t["MAPE"], "R²": t["R2"],
                     "Val RMSE": v["RMSE"], "Duration (s)": r["duration_s"]})
    df = pd.DataFrame(rows)
    if not df.empty:
        df = df.sort_values("RMSE").reset_index(drop=True)
        df.insert(0, "Rank", range(1, len(df) + 1))
    return df


with tab_res:
    if not experiments:
        empty_state("No experiments yet", "Configure models in the first tab and select Train models.", "flask")
    else:
        eid = select_id("Experiment", {e["id"]: f"{e['id']} · {e['dataset_name']} · {fmt_date(e['created'], True)}"
                                       for e in experiments[::-1]})
        exp = next(e for e in experiments if e["id"] == eid)
        tag = (badge("Computed locally · synthetic demo data", "demo") if exp["dataset_source"] == "demo"
               else badge("Computed locally · uploaded data", "real"))
        st.markdown(f"Target `{exp['target']}` · {exp['freq']} · split {exp['split_pct'][0]}/{exp['split_pct'][1]}/"
                    f"{exp['split_pct'][2]} (train/val/test) &nbsp; {tag}", unsafe_allow_html=True)
        if exp["dataset_source"] == "demo":
            banner("These metrics were genuinely computed, but on synthetic data. They show how the workflow behaves, "
                   "not how accurate any model would be for a real site.", kind="demo", title="Demo evaluation.")

        rank = _ranking(exp)
        if rank.empty:
            st.warning("No model completed in this experiment.")
        else:
            best = rank.iloc[0]
            st.success(f"**{best['Model']}** ranks first with a test RMSE of {fmt_energy(best['RMSE'], unit, 1)}"
                       + (f" and MAPE of {best['MAPE']:.1f}%." if not np.isnan(best["MAPE"]) else "."),
                       icon=":material/emoji_events:")
            left, right = st.columns([1.3, 1])
            with left:
                section_header("Model ranking", "Ranked by RMSE on the test split")
                st.dataframe(rank, hide_index=True, width="stretch", column_config={
                    "MAE": st.column_config.NumberColumn(f"MAE ({'kWh'})", format="%.2f", help=GLOSSARY["MAE"]),
                    "RMSE": st.column_config.NumberColumn("RMSE (kWh)", format="%.2f", help=GLOSSARY["RMSE"]),
                    "MAPE": st.column_config.NumberColumn("MAPE %", format="%.2f", help=GLOSSARY["MAPE"]),
                    "R²": st.column_config.NumberColumn("R²", format="%.3f", help=GLOSSARY["R²"]),
                    "Val RMSE": st.column_config.NumberColumn(format="%.2f", help="RMSE on the validation split (model trained on train only)."),
                    "Duration (s)": st.column_config.NumberColumn(format="%.3f"),
                })
                st.download_button("Export results (CSV)", rank.assign(experiment=exp["id"], data_source=exp["dataset_source"])
                                   .to_csv(index=False).encode("utf-8"), f"{exp['id']}_results.csv", "text/csv",
                                   icon=":material/download:")
            with right:
                section_header("Compare models")
                metric = st.segmented_control("Metric", ["MAE", "RMSE", "MAPE", "R²"], default="RMSE", key="ml_metric") or "RMSE"
                charts.show(charts.model_comparison(rank, metric, height=max(200, 70 * len(rank)),
                                                    lower_is_better=metric != "R²"), key="ml_cmp")
                st.caption(GLOSSARY[metric])

        skipped = [r for r in exp["results"] if r["status"] != "Completed"]
        if skipped:
            section_header("Not completed")
            st.dataframe(pd.DataFrame([{"Model": r["model"], "Status": r["status"], "Where": r["source"],
                                        "Detail": r.get("error") or f"Job {r.get('job_id')}"} for r in skipped]),
                         hide_index=True, width="stretch")
            job = (exp.get("backend") or {}).get("job_id")
            if job and st.button("Refresh backend job status", icon=":material/refresh:"):
                api = get_client().get_training_job(job)
                ss.backend_status = api.ok
                if api.ok:
                    st.json(api.data)
                else:
                    st.error(api.error)

# ======================= Details =======================
with tab_det:
    done = [(e, r) for e in experiments for r in e["results"] if r["status"] == "Completed"]
    if not done:
        empty_state("Nothing to inspect yet", "Completed models from your experiments appear here.", "flask")
    else:
        labels = [f"{e['id']} · {r['model']}" for e, r in done][::-1]
        pick = st.selectbox("Experiment result", labels)
        exp, r = done[::-1][labels.index(pick)]
        c = st.columns(4)
        t = r["test_metrics"]
        c[0].metric("Test MAE", fmt_energy(t["MAE"], unit, 1), help=GLOSSARY["MAE"])
        c[1].metric("Test RMSE", fmt_energy(t["RMSE"], unit, 1), help=GLOSSARY["RMSE"])
        c[2].metric("Test MAPE", f"{t['MAPE']:.2f}%" if not np.isnan(t["MAPE"]) else "n/a", help=GLOSSARY["MAPE"])
        c[3].metric("Test R²", f"{t['R2']:.3f}" if not np.isnan(t["R2"]) else "n/a", help=GLOSSARY["R²"])

        left, right = st.columns([1.6, 1])
        with left, st.container(border=True):
            section_header("Actual vs predicted on the test split",
                           f"{fmt_date(r['split']['test'][0])} – {fmt_date(r['split']['test'][1])}")
            charts.show(charts.actual_vs_predicted(r["test_frame"], unit), key="ml_avp")
        with right, st.container(border=True):
            section_header("Feature importance")
            if r.get("importance") is not None:
                charts.show(charts.importance_chart(r["importance"]), key="ml_imp")
                st.caption("Share of absolute standardised ridge coefficients, grouped by feature family.")
            else:
                st.info(f"{r['model']} has no learned features, so importance is not applicable.")
        with st.expander("Configuration"):
            st.json({"experiment": exp["id"], "model": r["model"], "params": r["params"], "target": exp["target"],
                     "frequency": exp["freq"], "features": exp["features"],
                     "split": {k: [str(v[0]), str(v[1])] for k, v in r["split"].items()},
                     "duration_s": round(r["duration_s"], 4), "data_source": exp["dataset_source"]})

footer()
