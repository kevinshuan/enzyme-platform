"""Streamlit dashboard for the AI-Designed Carbon-Reducing Enzyme Platform."""
from __future__ import annotations

import io
import time

import pandas as pd
import plotly.graph_objects as go
import requests
import streamlit as st

_API_BASE = "http://localhost:8000"

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Enzyme Platform",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.title("AI-Designed Carbon-Reducing Enzyme Platform")
st.warning(
    "Scores are simulation proxies — not biological predictions. "
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

    generate_button = st.button("Generate", type="primary", width="stretch")

# ── Helpers ───────────────────────────────────────────────────────────────────

def _sequence_diff_html(base: str, mutated: str, mutation_positions: list[int]) -> str:
    """Render mutated sequence as HTML with mutation positions highlighted."""
    mut_set = set(mutation_positions)
    parts: list[str] = []
    for i, aa in enumerate(mutated):
        if i in mut_set:
            orig = base[i] if i < len(base) else "?"
            parts.append(
                f'<span title="{orig}{i+1}{aa}" style="'
                f'background:#e74c3c;color:#fff;'
                f'border-radius:3px;padding:1px 3px;'
                f'font-family:monospace;font-size:13px">{aa}</span>'
            )
        else:
            parts.append(
                f'<span style="font-family:monospace;font-size:13px">{aa}</span>'
            )
    # Wrap in 60-char rows for readability
    chars_per_row = 60
    rows: list[str] = []
    flat = "".join(parts)
    # Re-chunk by original characters (not HTML tags)
    raw_parts = []
    i = 0
    for aa in mutated:
        if i in set(mutation_positions):
            orig = base[i] if i < len(base) else "?"
            raw_parts.append(
                f'<span title="{orig}{i+1}{aa}" style="'
                f'background:#e74c3c;color:#fff;'
                f'border-radius:3px;padding:1px 3px;'
                f'font-family:monospace;font-size:13px">{aa}</span>'
            )
        else:
            raw_parts.append(
                f'<span style="font-family:monospace;font-size:13px">{aa}</span>'
            )
        i += 1

    for start in range(0, len(raw_parts), chars_per_row):
        pos_label = f'<span style="color:#888;font-size:11px;font-family:monospace">{start+1:4d} </span>'
        row_html = "".join(raw_parts[start : start + chars_per_row])
        rows.append(pos_label + row_html)

    return "<br>".join(rows)


def _render_3dmol(pdb_string: str, plddt: list[float]) -> str:
    """Return an HTML string with embedded 3Dmol.js viewer coloured by pLDDT."""
    # Escape backticks and backslashes in PDB for JS template literal
    safe_pdb = pdb_string.replace("\\", "\\\\").replace("`", "\\`")
    mean_val = sum(plddt) / len(plddt) if plddt else 0
    return f"""
    <html>
    <head>
      <script src="https://cdnjs.cloudflare.com/ajax/libs/3Dmol/2.4.2/3Dmol-min.js"></script>
      <style>
        body {{ margin:0; padding:0; background:#1e1e2e; }}
        #viewer {{ width:100%; height:480px; position:relative; }}
        #legend {{
          position:absolute; bottom:12px; left:12px;
          background:rgba(0,0,0,0.6); color:#fff;
          font-family:monospace; font-size:12px;
          padding:8px 12px; border-radius:6px; line-height:1.8;
        }}
        .dot {{
          display:inline-block; width:12px; height:12px;
          border-radius:50%; margin-right:6px; vertical-align:middle;
        }}
      </style>
    </head>
    <body>
      <div style="position:relative">
        <div id="viewer"></div>
        <div id="legend">
          <b>pLDDT colour (B-factor)</b><br>
          <span class="dot" style="background:#1565c0"></span>&gt; 90 Very high<br>
          <span class="dot" style="background:#42a5f5"></span>70–90 High<br>
          <span class="dot" style="background:#ffee58"></span>50–70 Low<br>
          <span class="dot" style="background:#ef5350"></span>&lt; 50 Very low<br>
          <br><b>Mean pLDDT: {mean_val:.1f}</b>
        </div>
      </div>
      <script>
        (function() {{
          var pdbData = `{safe_pdb}`;
          var viewer = $3Dmol.createViewer(
            document.getElementById('viewer'),
            {{ backgroundColor: '#1e1e2e' }}
          );
          viewer.addModel(pdbData, 'pdb');
          viewer.setStyle({{}}, {{
            cartoon: {{
              colorfunc: function(atom) {{
                var b = atom.b;
                if (b >= 90) return '#1565c0';
                if (b >= 70) return '#42a5f5';
                if (b >= 50) return '#ffee58';
                return '#ef5350';
              }}
            }}
          }});
          viewer.addSurface($3Dmol.SurfaceType.SAS, {{
            opacity: 0.08,
            color: 'white'
          }});
          viewer.zoomTo();
          viewer.render();
        }})();
      </script>
    </body>
    </html>
    """


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

        try:
            resp = requests.post(f"{_API_BASE}/generate", json=payload, timeout=10)
        except requests.ConnectionError:
            st.error("API not running — start it with:\n\n```\nmake api\n```")
            st.stop()

        if resp.status_code == 422:
            st.error(f"Validation error: {resp.json().get('detail', '')}")
            st.stop()
        elif resp.status_code != 200:
            st.error(f"API error {resp.status_code}: {resp.text}")
            st.stop()

        job = resp.json()
        st.session_state["pending_job_id"] = job["job_id"]
        st.session_state["base_sequence"] = base_sequence.strip()
        st.session_state.pop("fold_cache", None)
        st.rerun()

# ── Job polling ───────────────────────────────────────────────────────────────
if "pending_job_id" in st.session_state:
    job_id = st.session_state["pending_job_id"]
    try:
        poll = requests.get(f"{_API_BASE}/jobs/{job_id}", timeout=5).json()
    except Exception:
        st.error("Lost connection to API while polling.")
        del st.session_state["pending_job_id"]
        st.stop()

    status = poll.get("status", "unknown")
    progress = poll.get("progress", 0)
    total = poll.get("total", 0)
    pct = int(progress / total * 100) if total else 0

    if status in ("pending", "running"):
        st.info(f"Generating candidates… {progress}/{total}  ({pct}%)")
        st.progress(pct / 100)
        time.sleep(1)
        st.rerun()
    elif status == "complete":
        data = poll["result"]
        st.session_state["result"] = data
        st.session_state["seed_used"] = data.get("seed")
        del st.session_state["pending_job_id"]
        st.rerun()
    else:
        st.error(f"Generation failed: {poll.get('error', 'unknown error')}")
        del st.session_state["pending_job_id"]
        st.stop()

# ── Display results ───────────────────────────────────────────────────────────
if "result" in st.session_state:
    data = st.session_state["result"]
    ranked = data.get("ranked_candidates", [])
    base_seq = st.session_state.get("base_sequence", "")
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

    # Score distribution histogram
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
        st.plotly_chart(fig_hist, width="stretch")

    # Carbon vs Feasibility scatter
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
        st.plotly_chart(fig_scatter, width="stretch")

    # ── Top 10 tab ────────────────────────────────────────────────────────────
    with tab_table:
        top10 = df_all.head(10).copy()
        top10.insert(0, "Rank", range(1, len(top10) + 1))

        # Score table
        st.subheader("Top 10 Ranked Candidates")
        display_cols = [
            "Rank", "id", "mutation_count",
            "bio_score", "carbon_score", "feasibility_score", "final_score",
        ]
        display_df = top10[display_cols].copy()
        display_df["id"] = display_df["id"].str[:12] + "…"
        display_df = display_df.rename(columns={"id": "ID (truncated)"})
        st.dataframe(
            display_df.style.format(
                {
                    "bio_score": "{:.4f}",
                    "carbon_score": "{:.4f}",
                    "feasibility_score": "{:.4f}",
                    "final_score": "{:.4f}",
                }
            ),
            width="stretch",
        )

        # ── Sequence viewer ───────────────────────────────────────────────────
        st.subheader("Mutated Sequence Viewer")
        st.caption(
            "Red highlighted residues = mutation positions. "
            "Hover over a residue to see the original → mutated substitution."
        )

        rank_options = [f"Rank #{r['Rank']}  mutations={r['mutation_count']}  score={r['final_score']:.4f}"
                        for _, r in top10.iterrows()]
        selected_label = st.selectbox("Select candidate", rank_options, key="seq_select")
        selected_idx = rank_options.index(selected_label)
        selected_row = top10.iloc[selected_idx]

        mut_positions: list[int] = selected_row["mutation_positions"]
        mutated_seq: str = selected_row["mutated_sequence"]

        col_meta, col_seq = st.columns([1, 3])
        with col_meta:
            st.metric("Rank", f"#{selected_row['Rank']}")
            st.metric("Mutations", selected_row["mutation_count"])
            st.metric("Final Score", f"{selected_row['final_score']:.4f}")
            st.metric("Bio Score", f"{selected_row['bio_score']:.4f}")
            st.metric("Carbon Score", f"{selected_row['carbon_score']:.4f}")
            st.metric("Feasibility", f"{selected_row['feasibility_score']:.4f}")

        with col_seq:
            st.markdown("**Mutated Sequence** (red = mutated positions):")
            seq_html = _sequence_diff_html(base_seq, mutated_seq, mut_positions)
            st.markdown(
                f'<div style="background:#0e1117;padding:12px;border-radius:8px;'
                f'border:1px solid #333;line-height:1.9">{seq_html}</div>',
                unsafe_allow_html=True,
            )

            if mut_positions:
                st.caption(
                    "Substitutions: " +
                    ", ".join(
                        f"**{base_seq[p] if p < len(base_seq) else '?'}"
                        f"{p+1}"
                        f"{mutated_seq[p]}**"
                        for p in mut_positions
                    )
                )

        # ── ESMFold 3D structure ──────────────────────────────────────────────
        st.divider()
        st.subheader("ESMFold 3D Structure")
        st.caption(
            "Folds the selected candidate with NVIDIA NIM ESMFold. "
            "Colour = pLDDT confidence (blue=high, red=low). Takes ~5–15 s."
        )

        fold_key = f"fold_{selected_row['id']}"

        if st.button("Fold with ESMFold", key="fold_btn", type="primary"):
            with st.spinner("Calling ESMFold NIM… (~5–15 s)"):
                try:
                    fold_resp = requests.post(
                        f"{_API_BASE}/fold",
                        json={"sequence": mutated_seq},
                        timeout=120,
                    )
                    if fold_resp.status_code == 200:
                        fold_data = fold_resp.json()
                        st.session_state.setdefault("fold_cache", {})[fold_key] = fold_data
                    elif fold_resp.status_code == 503:
                        st.error(
                            "ESMFold NIM unavailable. "
                            "Set BIONEMO_API_KEY in .env and restart the API."
                        )
                    else:
                        st.error(f"Fold API error {fold_resp.status_code}: {fold_resp.text[:200]}")
                except requests.ConnectionError:
                    st.error("API not running — start it with `make api`")

        fold_cache = st.session_state.get("fold_cache", {})
        if fold_key in fold_cache:
            fd = fold_cache[fold_key]
            plddt_list: list[float] = fd["plddt"]
            mean_val: float = fd["mean_plddt"]

            st.success(f"ESMFold complete — Mean pLDDT: **{mean_val:.1f}**")

            # pLDDT bar chart
            fig_plddt = go.Figure(
                go.Bar(
                    x=list(range(1, len(plddt_list) + 1)),
                    y=plddt_list,
                    marker=dict(
                        color=plddt_list,
                        colorscale=[
                            [0.0, "#ef5350"],
                            [0.5, "#ffee58"],
                            [0.7, "#42a5f5"],
                            [1.0, "#1565c0"],
                        ],
                        cmin=0,
                        cmax=100,
                        showscale=True,
                        colorbar=dict(title="pLDDT"),
                    ),
                )
            )
            fig_plddt.update_layout(
                title=f"Per-residue pLDDT  (mean={mean_val:.1f})",
                xaxis_title="Residue position",
                yaxis_title="pLDDT",
                yaxis=dict(range=[0, 100]),
                height=280,
                margin=dict(t=40, b=40),
            )
            st.plotly_chart(fig_plddt, width="stretch")

            # 3D molecular viewer
            html_3d = _render_3dmol(fd["pdb"], plddt_list)
            st.components.v1.html(html_3d, height=500, scrolling=False)

            # PDB download
            st.download_button(
                label="Download PDB",
                data=fd["pdb"],
                file_name=f"candidate_{selected_row['id'][:8]}.pdb",
                mime="chemical/x-pdb",
            )

    # CSV download
    with tab_csv:
        csv_cols = [
            "id", "mutated_sequence", "mutation_positions",
            "mutation_count", "bio_score", "carbon_score",
            "feasibility_score", "final_score",
        ]
        df_csv = df_all[csv_cols].copy()
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
            width="stretch",
        )
        st.caption(f"Includes all {len(df_all)} ranked candidates.")
