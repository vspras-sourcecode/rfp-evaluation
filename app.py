"""Streamlit front end for the Agentic RFP Evaluation mini project."""
import os
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st

import db
from llm_agent import DEFAULT_MODEL
from orchestrator import check_inputs, load_run, run_evaluation, to_json

st.set_page_config(page_title="Agentic RFP Evaluation", page_icon="📊", layout="wide")
db.init_db()

SAMPLE_DIR = Path(__file__).parent / "sample_pdfs"
SAMPLE_META = {  # demo defaults for the bundled sample PDFs
    "Apex_Systems.pdf": ("Apex Systems", date(2026, 3, 2), 4.5),
    "BrightPath_Tech.pdf": ("BrightPath Tech", date(2026, 3, 3), 2.5),
    "NexaWorks.pdf": ("NexaWorks", date(2026, 3, 1), 4.0),
    "Orbit_Digital.pdf": ("Orbit Digital", date(2026, 3, 4), 4.8),
}


class SampleFile:
    """Lets a bundled PDF behave like a Streamlit upload."""
    def __init__(self, path):
        self.path = Path(path)
        self.name = self.path.name
        self.size = self.path.stat().st_size

    def getvalue(self):
        return self.path.read_bytes()


def secret_key():
    try:
        return st.secrets.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_API_KEY") or ""
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")


# ---------------- sidebar ----------------
with st.sidebar:
    st.header("Evaluator")
    choice = st.radio("Scoring engine", ["Offline demo scorer (no API key)", "Claude API"],
                      help="The offline scorer is a keyword heuristic for testing. It is not an LLM.")
    provider = "mock" if choice.startswith("Offline") else "claude"
    api_key, model = None, None
    if provider == "claude":
        api_key = secret_key() or st.text_input("Anthropic API key", type="password")
        model = st.text_input("Model", value=DEFAULT_MODEL)
    st.divider()
    st.header("Saved runs")
    runs = db.list_runs()
    if runs:
        labels = {f"{r['rfp_run_id']} ({r['status']})": r["rfp_run_id"] for r in runs}
        picked = st.selectbox("Load a previous run", list(labels))
        if st.button("Load run"):
            st.session_state["run"] = load_run(labels[picked])
            st.rerun()
    else:
        st.caption("No saved runs yet.")

st.title("Agentic RFP Evaluation and Supplier Ranking")
tab_criteria, tab_input, tab_board, tab_cards, tab_run = st.tabs(
    ["1. Criteria", "2. Suppliers and evaluate", "3. Leaderboard", "4. Scorecards", "5. Run details"])

# ---------------- 1. criteria ----------------
with tab_criteria:
    active = db.get_active_criteria()
    total = sum(c["weight"] for c in active)
    st.subheader("Active evaluation criteria")
    if active:
        st.dataframe(pd.DataFrame(active)[["name", "description", "weight", "max_score"]]
                     .rename(columns={"name": "Criterion", "description": "What is inspected",
                                      "weight": "Weight (%)", "max_score": "Max score"}), hide_index=True)
    st.metric("Total weight", f"{total:g}%")
    if abs(total - 100) > 0.01:
        st.error("Active weights must total 100% before an evaluation can run.")
    with st.expander("Edit criteria (activate, deactivate, change weights)"):
        editable = pd.DataFrame(db.get_all_criteria())[["criterion_id", "name", "weight", "max_score", "is_active"]]
        edited = st.data_editor(editable, hide_index=True, disabled=["criterion_id", "name"], key="criteria_editor")
        if st.button("Save criteria"):
            for _, row in edited.iterrows():
                db.update_criterion(int(row["criterion_id"]), float(row["weight"]),
                                    float(row["max_score"]), bool(row["is_active"]))
            st.rerun()

# ---------------- 2. suppliers and evaluate ----------------
with tab_input:
    st.subheader("Upload supplier RFP responses")
    uploads = st.file_uploader("Supplier PDFs", type="pdf", accept_multiple_files=True)
    use_samples = st.checkbox("Use the four bundled sample PDFs instead")
    files = [SampleFile(SAMPLE_DIR / n) for n in SAMPLE_META if (SAMPLE_DIR / n).exists()] if use_samples \
        else list(uploads or [])

    inputs = []
    for i, f in enumerate(files):
        default_name, default_date, default_rating = SAMPLE_META.get(
            f.name, (Path(f.name).stem.replace("_", " "), date.today(), 3.0))
        c1, c2, c3, c4 = st.columns([3, 2, 2, 2])
        key = f"{i}_{f.name}_{use_samples}"
        name = c1.text_input("Supplier name", value=default_name, key=f"n_{key}")
        when = c2.date_input("Submission date", value=default_date, key=f"d_{key}")
        rating = c3.number_input("Experience rating (0-5)", 0.0, 5.0, float(default_rating), 0.1, key=f"r_{key}")
        c4.caption(f"File: {f.name}")
        inputs.append({"supplier_name": name, "submission_date": when, "experience_rating": rating,
                       "file": f, "filename": f.name})

    problems = check_inputs(inputs, db.get_active_criteria()) if inputs else []
    if provider == "claude" and not api_key:
        problems.append("Enter an Anthropic API key in the sidebar, or switch to the offline demo scorer.")
    if not inputs:
        st.info("Upload at least two supplier PDFs, or tick the sample option above.")
    for p in problems:
        st.warning(p)

    if st.button("Evaluate suppliers", type="primary", disabled=bool(problems) or not inputs):
        bar = st.progress(0.0, text="Starting")
        try:
            result = run_evaluation(inputs, provider, api_key, model,
                                    progress=lambda frac, msg: bar.progress(min(frac, 1.0), text=msg))
            st.session_state["run"] = result
            st.success(f"Run {result['rfp_run_id']} finished with status {result['status']}. "
                       "Open the Leaderboard tab.")
        except ValueError as exc:
            st.error(f"Input problem: {exc}")
        except Exception as exc:
            st.error(f"The run failed: {type(exc).__name__}: {exc}")

run = st.session_state.get("run")
NO_RUN = "No results yet. Run an evaluation in tab 2, or load a saved run from the sidebar."

# ---------------- 3. leaderboard ----------------
with tab_board:
    if not run:
        st.info(NO_RUN)
    else:
        st.subheader(f"Leaderboard: {run['rfp_run_id']}")
        top = run["suppliers"][0]
        st.metric("Rank 1", top["supplier_name"], f"PPI {top['ppi']:.2f}")
        table = pd.DataFrame([{"Rank": r["final_rank"], "Supplier": r["supplier_name"],
                               "Absolute score": r["absolute_score"], "PPI": r["ppi"],
                               "Submission date": r["submission_date"],
                               "Experience rating": r["experience_rating"]} for r in run["suppliers"]])
        st.dataframe(table, hide_index=True)
        st.bar_chart(table.set_index("Supplier")[["Absolute score", "PPI"]])
        for note in run["tie_break_notes"]:
            st.caption(note)

# ---------------- 4. scorecards ----------------
with tab_cards:
    if not run:
        st.info(NO_RUN)
    else:
        names = [f"#{r['final_rank']} {r['supplier_name']}" for r in run["suppliers"]]
        row = run["suppliers"][names.index(st.selectbox("Supplier", names))]
        m1, m2, m3 = st.columns(3)
        m1.metric("Final rank", row["final_rank"])
        m2.metric("Absolute score", f"{row['absolute_score']:.2f}")
        m3.metric("Peer Performance Index", f"{row['ppi']:.2f}")
        st.dataframe(pd.DataFrame([{
            "Criterion": c["name"], "Weight (%)": c["weight"], "Score": c["score"], "Max": c["max_score"],
            "Benchmark": c["benchmark"], "Gap": c["gap"], "Relative %": c["relative_pct"],
            "Weighted points": c["weighted_points"], "Valid": c["valid"]} for c in row["criteria"]]),
            hide_index=True)
        st.markdown("**Evidence and justification**")
        for c in row["criteria"]:
            with st.expander(f"{c['name']}: {c['score']:g} / {c['max_score']:g}"):
                st.write("**Justification:**", c["justification"] or "None provided")
                st.write("**Evidence:**", c["evidence"])
        if row["risks"]:
            st.markdown("**Risks identified**")
            for r in row["risks"]:
                st.write("-", r)
        if row["overall_summary"]:
            st.markdown("**Summary:** " + row["overall_summary"])
        for w in row.get("warnings", []):
            st.warning(w)
        st.markdown("**Peer comparison (scores by criterion)**")
        comparison = pd.DataFrame(
            {s["supplier_name"]: {c["name"]: c["score"] for c in s["criteria"]} for s in run["suppliers"]})
        comparison["Benchmark"] = pd.Series({b["name"]: b["benchmark_score"] for b in run["benchmarks"]})
        st.dataframe(comparison)

# ---------------- 5. run details ----------------
with tab_run:
    if not run:
        st.info(NO_RUN)
    else:
        st.subheader("Run details")
        d1, d2, d3 = st.columns(3)
        d1.metric("RFP_RUN_ID", run["rfp_run_id"])
        d2.metric("Status", run["status"])
        d3.metric("Engine", run["provider"] if not run["model"] else f"{run['provider']} / {run['model']}")
        if "reproducible" in run:
            st.success("Reloaded from SQLite and re-ranked: identical result." if run["reproducible"]
                       else "Warning: the re-ranked result differs from the stored result.")
        st.markdown("**Tie-break rule:** " + run["tie_break_order"])
        for note in run["tie_break_notes"]:
            st.write("-", note)
        st.markdown("**Benchmarks**")
        st.dataframe(pd.DataFrame([{"Criterion": b["name"], "Benchmark score": b["benchmark_score"],
                                    "Leader(s)": ", ".join(b["leaders"]) or "none"} for b in run["benchmarks"]]),
                     hide_index=True)
        st.markdown(f"**Warnings ({len(run['warnings'])})**")
        for w in run["warnings"] or ["None"]:
            st.write("-", w)
        st.markdown("**Formulas**")
        st.json(run["formulas"])
        if run["trace"]:
            st.markdown("**Workflow trace (tool calls in order)**")
            st.code("\n".join(run["trace"]))
        st.download_button("Download complete result as JSON", to_json(run),
                           file_name=f"{run['rfp_run_id']}.json", mime="application/json")
