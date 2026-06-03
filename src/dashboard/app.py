"""RuleForge Dashboard — Module 7 (Streamlit web UI).

A browser front-end over the whole pipeline. Upload (or pick) a COBOL program
and instantly see:
  - Program metrics (LOC, paragraphs, data items)
  - Extracted business rules (filterable table)
  - Generated decision tables
  - Audit: rule conflicts + decision-table completeness gaps
  - Optional LLM plain-English descriptions with grounding scores
  - One-click export to JSON / DMN / Markdown / CSV / HTML

Run:
    streamlit run src/dashboard/app.py

(Run from the project root so the `src` package imports resolve.)
"""

import sys
from pathlib import Path

# Ensure project root is importable when launched via `streamlit run`.
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import tempfile
import pandas as pd
import streamlit as st

from src.parser.cobol_parser import CobolParser
from src.extraction.rule_detector import RuleDetector
from src.extraction.decision_table import DecisionTableGenerator
from src.export.export_engine import ExportBundle, ExportEngine
from src.generation.llm_client import LLMClient
from src.analysis.conflict_detector import RuleConflictDetector
from src.analysis.completeness import CompletenessScorer


# ─────────────────────────────────────────────────────────────
# Page config
# ─────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="RuleForge",
    page_icon="⚙️",
    layout="wide",
)


# ─────────────────────────────────────────────────────────────
# Cached pipeline (so re-renders don't re-parse)
# ─────────────────────────────────────────────────────────────
@st.cache_data(show_spinner=False)
def run_pipeline(source_text: str, filename: str):
    """Parse → detect rules → build tables. Returns plain dicts/objects.

    Cached on the file content so Streamlit's reruns are instant.
    """
    # Parser reads from a path, so stage the upload to a temp file.
    tmp = Path(tempfile.gettempdir()) / filename
    tmp.write_text(source_text, encoding="utf-8")

    program = CobolParser().parse_file(tmp)
    rules = RuleDetector(program).detect_all_rules()
    tables = DecisionTableGenerator().generate_all(rules)
    conflicts = RuleConflictDetector().detect(rules)
    completeness = CompletenessScorer().score_all(tables)
    return program, rules, tables, conflicts, completeness


def list_corpus_files():
    """Find bundled sample COBOL files, ranked by size (proxy for richness)."""
    corpus = ROOT / "data" / "cobol_corpus"
    if not corpus.exists():
        return []
    files = sorted(corpus.rglob("*.cbl"), key=lambda f: f.stat().st_size, reverse=True)
    return files


# ─────────────────────────────────────────────────────────────
# Sidebar — input selection
# ─────────────────────────────────────────────────────────────
st.sidebar.title("⚙️ RuleForge")
st.sidebar.caption("AI business-rule extraction from legacy COBOL")

source_mode = st.sidebar.radio(
    "COBOL source", ["Sample from corpus", "Upload a file"], index=0
)

source_text = None
filename = None

if source_mode == "Upload a file":
    uploaded = st.sidebar.file_uploader("Upload .cbl / .cob", type=["cbl", "cob", "txt"])
    if uploaded:
        source_text = uploaded.read().decode("utf-8", errors="replace")
        filename = uploaded.name
else:
    corpus = list_corpus_files()
    if corpus:
        labels = [f"{f.name}  ({f.stat().st_size // 1024} KB)" for f in corpus]
        pick = st.sidebar.selectbox("Pick a sample program", range(len(corpus)),
                                    format_func=lambda i: labels[i])
        chosen = corpus[pick]
        source_text = chosen.read_text(encoding="utf-8", errors="replace")
        filename = chosen.name
    else:
        st.sidebar.warning("No corpus found. Download it or upload a file.")

# LLM availability indicator
_client = LLMClient()
_llm_online = _client.is_available()
st.sidebar.divider()
if _llm_online:
    st.sidebar.success(f"🟢 Ollama online ({_client.model})")
else:
    st.sidebar.error("🔴 Ollama offline — LLM docs disabled")


# ─────────────────────────────────────────────────────────────
# Main area
# ─────────────────────────────────────────────────────────────
st.title("RuleForge")
st.caption("Turn undocumented COBOL into business rules, decision tables, and plain English.")

if not source_text:
    st.info("👈 Pick a sample program or upload a COBOL file to begin.")
    st.stop()

with st.spinner("Parsing and extracting rules..."):
    program, rules, tables, conflicts, completeness = run_pipeline(source_text, filename)

# ── Metric cards ──
c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
c1.metric("Lines of Code", f"{program.loc:,}")
c2.metric("Paragraphs", len(program.paragraphs))
c3.metric("Data Items", len(program.data_items))
c4.metric("Business Rules", len(rules))
c5.metric("Decision Tables", len(tables))
c6.metric("Rule Conflicts", len(conflicts.conflicts),
          delta="clean" if not conflicts.has_conflicts else None,
          delta_color="off")
c7.metric("Incomplete Tables", completeness.num_incomplete,
          delta=f"{len(completeness.high_risk)} high-risk" if completeness.high_risk else "clean",
          delta_color="inverse" if completeness.high_risk else "off")

st.divider()

tab_rules, tab_tables, tab_audit, tab_llm, tab_export, tab_source = st.tabs(
    ["📋 Rules", "🔀 Decision Tables", "🛡️ Audit", "🧠 AI Descriptions",
     "📦 Export", "📄 Source"]
)

# ── Tab 1: Rules ──
with tab_rules:
    if not rules:
        st.warning("No business rules detected (may be infrastructure-only code).")
    else:
        df = pd.DataFrame([
            {
                "Paragraph": r.paragraph_name,
                "Type": r.rule_type.value,
                "Domain": r.domain.value,
                "Confidence": round(r.confidence, 2),
                "Variables": ", ".join(r.variables_involved[:5]),
                "Lines": f"{r.start_line}-{r.end_line}",
                "Description": r.description,
            }
            for r in rules
        ])

        fcol1, fcol2 = st.columns(2)
        domains = ["All"] + sorted(df["Domain"].unique().tolist())
        types = ["All"] + sorted(df["Type"].unique().tolist())
        sel_domain = fcol1.selectbox("Filter by domain", domains)
        sel_type = fcol2.selectbox("Filter by type", types)

        view = df
        if sel_domain != "All":
            view = view[view["Domain"] == sel_domain]
        if sel_type != "All":
            view = view[view["Type"] == sel_type]

        st.caption(f"Showing {len(view)} of {len(df)} rules")
        st.dataframe(view, use_container_width=True, hide_index=True)

        # Domain distribution
        st.subheader("Rules by domain")
        st.bar_chart(df["Domain"].value_counts())

# ── Tab 2: Decision Tables ──
with tab_tables:
    if not tables:
        st.warning("No decision tables generated.")
    else:
        st.caption(f"{len(tables)} decision tables")
        for i, t in enumerate(tables, 1):
            para = t.source_rule.paragraph_name if t.source_rule else f"Table {i}"
            with st.expander(f"Table {i}: {para}  ·  {t.table_type}  "
                             f"({t.num_conditions} conditions × {t.num_rules} rules)"):
                st.code(t.to_text(), language="text")

# ── Tab 3: Audit (conflicts + completeness) ──
with tab_audit:
    st.subheader("⚔️ Rule Conflicts")
    st.caption(
        "Pairs of rules whose conditions can be true at the same time but whose "
        "outcomes differ — the program resolves them silently by execution order, "
        "so the business specification is ambiguous."
    )
    if conflicts.has_conflicts:
        st.error(f"{len(conflicts.conflicts)} conflict(s) detected.")
        for k, c in enumerate(conflicts.conflicts, 1):
            with st.expander(
                f"Conflict {k}: {c.rule_a.paragraph_name} ↔ {c.rule_b.paragraph_name} "
                f"on {{{', '.join(c.shared_variables)}}}"
            ):
                st.write(c.reason)
                st.code(c.rule_a.source_code.strip(), language="text")
                st.code(c.rule_b.source_code.strip(), language="text")
    else:
        st.success("No provable rule conflicts detected.")
    st.caption(
        f"Conservative check: {conflicts.rules_modeled} of {conflicts.rules_considered} "
        "rules were modelable (others use OR / nesting / computed conditions and are "
        "skipped rather than guessed)."
    )

    st.divider()
    st.subheader("🧩 Decision-Table Completeness")
    st.caption(
        "Every combination of a table's conditions should map to a defined outcome. "
        "Gaps mean inputs with undefined business behaviour."
    )
    if not completeness.tables:
        st.info("No decision tables to score.")
    else:
        m1, m2, m3 = st.columns(3)
        m1.metric("Complete", completeness.num_complete)
        m2.metric("Incomplete", completeness.num_incomplete)
        mc = completeness.mean_coverage
        m3.metric("Mean coverage", f"{mc:.0%}" if mc is not None else "n/a")

        cov_df = pd.DataFrame([
            {
                "Paragraph": t.table_name,
                "Type": t.table_type,
                "Verdict": t.verdict,
                "Coverage": (round(t.coverage, 2) if t.coverage is not None else None),
                "High risk": "⚠️" if t.is_high_risk else "",
                "Note": t.note,
            }
            for t in completeness.tables
        ])
        st.dataframe(cov_df, use_container_width=True, hide_index=True)

        gaps = [t for t in completeness.tables if t.missing]
        if gaps:
            st.markdown("**Undefined input combinations**")
            for t in gaps:
                for m in t.missing:
                    st.markdown(f"- `{t.table_name}` → {m}")
        st.caption(
            "Boolean tables assume condition independence, so a flagged gap is an "
            "upper bound — verify it is reachable before acting on it."
        )

# ── Tab 4: AI Descriptions ──
with tab_llm:
    st.write("Generate plain-English descriptions with the local LLM. "
             "CPU inference is slow (~5–90s per rule), so pick a small number.")
    if not _llm_online:
        st.error("Ollama is offline. Start the Ollama app, then reload.")
    elif not rules:
        st.info("No rules to describe.")
    else:
        n = st.slider("How many top rules to document", 1, min(10, len(rules)), 2)
        if st.button("🧠 Generate descriptions", type="primary"):
            from src.generation.nl_generator import NLGenerator
            gen = NLGenerator(program, client=_client)
            top = sorted(rules, key=lambda r: r.confidence, reverse=True)[:n]
            progress = st.progress(0.0, text="Starting...")
            results = []
            for idx, r in enumerate(top, 1):
                progress.progress((idx - 1) / len(top),
                                  text=f"Documenting {r.paragraph_name} ({idx}/{len(top)})")
                results.append(gen.describe_rule(r))
            progress.progress(1.0, text="Done")
            st.session_state["llm_results"] = results

        for d in st.session_state.get("llm_results", []):
            if not d.success:
                st.error(f"**{d.paragraph_name}** — failed: {d.error}")
                continue
            badge = "✅ Trustworthy" if d.trustworthy else "⚠️ Needs review"
            color = "green" if d.trustworthy else "orange"
            st.markdown(f"#### {d.paragraph_name}  "
                        f":{color}[{badge} · grounding {d.grounding_score:.0%}]")
            st.write(d.description)
            if d.hallucinated_terms:
                st.caption(f"⚠️ Flagged (not in source): {', '.join(d.hallucinated_terms)}")
            st.divider()

# ── Tab 5: Export ──
with tab_export:
    st.write("Export the full analysis to standard formats.")
    include_llm = st.checkbox(
        "Include AI descriptions (uses results from the AI tab)",
        value=bool(st.session_state.get("llm_results")),
    )
    if st.button("📦 Generate export files", type="primary"):
        descriptions = st.session_state.get("llm_results", []) if include_llm else []
        bundle = ExportBundle(program, rules, tables, descriptions)
        out_dir = ROOT / "exports"
        engine = ExportEngine(bundle, out_dir=str(out_dir))
        outputs = engine.export_all()
        st.success(f"Exported to `{out_dir}`")
        # Offer downloads
        labels = {"json": "JSON", "dmn": "DMN 1.3 XML", "markdown": "Markdown",
                  "csv": "CSV", "html": "HTML report"}
        cols = st.columns(len(outputs))
        for col, (fmt, path) in zip(cols, outputs.items()):
            data = Path(path).read_bytes()
            col.download_button(
                f"⬇️ {labels.get(fmt, fmt)}",
                data=data,
                file_name=Path(path).name,
                mime="application/octet-stream",
                use_container_width=True,
            )

# ── Tab 6: Source ──
with tab_source:
    st.caption(f"{filename} · {program.loc:,} lines")
    st.code(source_text, language="cobol" if False else "text")
