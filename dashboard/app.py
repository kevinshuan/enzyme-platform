"""Streamlit dashboard for the AI-Designed Carbon-Reducing Enzyme Platform.

Calls the FastAPI backend at http://localhost:8000 via HTTP.
Start the API first: uvicorn app.main:app --port 8000
"""
from __future__ import annotations

import io

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

_API_BASE = "http://localhost:8000"

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enzyme Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("AI-Designed Carbon-Reducing Enzyme Platform")
st.warning(
    "⚠ Scores are simulation proxies — not biological predictions. "
    "No wet-lab validation has been performed."
)

# ── Sidebar: input form ───────────────────────────────────────────────────────
with st.sidebar:
    st.header("Parameters")

    base_sequence = st.text_area(
        "Base Amino Acid Sequence (≥ 50 chars)",
        value=(
            "ACDEFGHIKLMNPQRSTVWYACDEFGHIKLMNPQRSTVWY"
            "ACDEFGHIKLMNPQRSTVWY"
        ),
        height=120,
        help="Valid characters: ACDEFGHIKLMNPQRSTVWY",
    )

    mutation_rate = st.slider(
        "Mutation Rate",
        min_value=0.001,
        max_value=0.2,
        value=0.05,
        step=0.001,
        format="%.3f",
        help="Probability of mutating each non-conserved position.",
    )

    candidates = st.number_input(
        "Number of Candidates",
        min_value=1,
        max_value=1000,
        value=100,
        step=10,
        help="How many mutated variants to generate and rank.",
    )

    st.subheader("Scoring Weights")
    st.caption("Must sum to 1.0")

    bio_weight = st.slider("Bio Weight", 0.0, 1.0, 0.3, 0.05)
    carbon_weight = st.slider("Carbon Weight", 0.0, 1.0, 0.4, 0.05)
    feasibility_weight = st.slider("Feasibility Weight", 0.0, 1.0, 0.3, 0.05)

    weight_sum = bio_weight + carbon_weight + feasibility_weight
    if abs(weight_sum - 1.0) > 0.001:
        st.error(f"Weights sum to {weight_sum:.3f} — must equal 1.0 ±0.001")

    seed_input = st.number_input(
        "Seed (optional — leave 0 for random)",
        min_value=0,
        value=0,
        help="Set a non-zero seed for reproducible results.",
    )

    generate_button = st.button("Generate", type="primary", use_container_width=True)

# ── Generate on button click ──────────────────────────────────────────────────
if generate_button:
    if abs(weight_sum - 1.0) > 0.001:
        st.error("Fix scoring weights before generating.")
    else:
        payload: dict = {
            "base_sequence": base_sequence.strip(),
            "mutation_rate": mutation_rate,
            "candidates": int(candidates),
            "weights": {
                "bio_weight": bio_weight,
                "carbon_weight": carbon_weight,
                "feasibility_weight": feasibility_weight,
            },
        }
        if seed_input > 0:
            payload["seed"] = int(seed_input)

        with st.spinner("Generating candidates…"):
            try:
                resp = requests.post(f"{_API_BASE}/generate", json=payload, timeout=30)
            except requests.ConnectionError:
                st.error(
                    "API not running — start it with:\n\n"
                    "```\nuvicorn app.main:app --port 8000\n```"
                )
                st.stop()

        if resp.status_code == 422:
            detail = resp.json().get("detail", "Validation error")
            st.error(f"Validation error: {detail}")
            st.stop()
        elif resp.status_code != 200:
            st.error(f"API error {resp.status_code}: {resp.text}")
            st.stop()
        else:
            data = resp.json()
            st.session_state["result"] = data
            st.session_state["seed_used"] = data.get("seed")

# ── Display results ───────────────────────────────────────────────────────────
if "result" in st.session_state:
    data = st.session_state["result"]
    ranked = data.get("ranked_candidates", [])
    seed_used = st.session_state.get("seed_used")

    st.success(
        f"Generated **{data.get('total_generated', 0)}** candidates. "
        f"Seed: `{seed_used}` (include in request to reproduce exact results)."
    )

    df_all = pd.DataFrame(ranked)

    # ── Tab layout ────────────────────────────────────────────────────────────
    tab_hist, tab_scatter, tab_table, tab_csv = st.tabs(
        ["Score Distribution", "Carbon vs Feasibility", "Top 10", "Download CSV"]
    )

    # T025 — Score distribution histogram
    with tab_hist:
        fig_hist = go.Figure(
            go.Histogram(
                x=df_all["final_score"],
                nbinsx=30,
                marker_color="#4C72B0",
                opacity=0.85,
            )
        )
        fig_hist.update_layout(
            title="Score Distribution",
            xaxis_title="Final Score",
            yaxis_title="Count",
            bargap=0.05,
        )
        st.plotly_chart(fig_hist, use_container_width=True)

    # T026 — Carbon vs Feasibility scatter
    with tab_scatter:
        fig_scatter = go.Figure(
            go.Scatter(
                x=df_all["carbon_score"],
                y=df_all["feasibility_score"],
                mode="markers",
                marker=dict(
                    color=df_all["final_score"],
                    colorscale="Viridis",
                    showscale=True,
                    colorbar=dict(title="Final Score"),
                    size=6,
                    opacity=0.75,
                ),
                text=df_all.apply(
                    lambda r: (
                        f"ID: {r['id'][:8]}…<br>"
                        f"Bio: {r['bio_score']:.4f}<br>"
                        f"Carbon: {r['carbon_score']:.4f}<br>"
                        f"Feasibility: {r['feasibility_score']:.4f}<br>"
                        f"Final: {r['final_score']:.4f}"
                    ),
                    axis=1,
                ),
                hoverinfo="text",
            )
        )
        fig_scatter.update_layout(
            title="Carbon Score vs Feasibility Score",
            xaxis_title="Carbon Score",
            yaxis_title="Feasibility Score",
        )
        st.plotly_chart(fig_scatter, use_container_width=True)

    # T027 — Top 10 ranked table
    with tab_table:
        top10 = df_all.head(10).copy()
        top10.insert(0, "Rank", range(1, len(top10) + 1))
        top10["id"] = top10["id"].str[:12] + "…"
        display_cols = [
            "Rank", "id", "mutation_count",
            "bio_score", "carbon_score", "feasibility_score", "final_score",
        ]
        top10 = top10[display_cols].rename(columns={"id": "ID (truncated)"})
        st.dataframe(
            top10.style.format(
                {
                    "bio_score": "{:.4f}",
                    "carbon_score": "{:.4f}",
                    "feasibility_score": "{:.4f}",
                    "final_score": "{:.4f}",
                }
            ),
            use_container_width=True,
        )

    # T028 — CSV download (all candidates)
    with tab_csv:
        csv_cols = [
            "id", "mutated_sequence", "mutation_positions",
            "mutation_count", "bio_score", "carbon_score",
            "feasibility_score", "final_score",
        ]
        df_csv = df_all[csv_cols].copy()
        # Convert list → string for CSV compatibility
        df_csv["mutation_positions"] = df_csv["mutation_positions"].apply(
            lambda x: str(x) if isinstance(x, list) else x
        )

        buf = io.StringIO()
        df_csv.to_csv(buf, index=False)
        csv_string = buf.getvalue()

        st.download_button(
            label="Download CSV (all candidates)",
            data=csv_string,
            file_name="candidates.csv",
            mime="text/csv",
            use_container_width=True,
        )
        st.caption(f"Includes all {len(df_all)} ranked candidates.")
