"""Exercise 5 — Streamlit approval UI for the HITL PR review agent.

Run with:
    uv run streamlit run app.py

Goal: wrap the LangGraph built in exercises 1–4 in a web UI that adapts to
the confidence bucket of each PR.

Routing thresholds (common/schemas.py):
    > 72%        auto_approve     UI shows a success card; reviewer does nothing
    58 – 72%     human_approval   UI shows Approve / Reject / Edit buttons
    <  58%       escalate         UI shows a question form for the reviewer
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
import uuid

import streamlit as st
from dotenv import load_dotenv
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command

from common.db import db_path
from exercises.exercise_4_audit import build_graph


load_dotenv()


def get_recent_sessions():
    """Retrieve recent review sessions from audit_events for the sidebar."""
    path = db_path()
    if not os.path.exists(path):
        return []
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT thread_id,
                       pr_url,
                       MIN(timestamp)  AS started,
                       MAX(timestamp)  AS last_event,
                       MAX(risk_level) AS worst_risk,
                       COUNT(*)        AS events
                  FROM audit_events
                 GROUP BY thread_id, pr_url
                 ORDER BY MAX(timestamp) DESC
                 LIMIT 15
                """
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


def get_session_events(thread_id: str):
    """Retrieve all audit events for a given thread_id."""
    path = db_path()
    if not os.path.exists(path):
        return []
    try:
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(
                """
                SELECT id, timestamp, action, confidence, risk_level,
                       reviewer_id, decision, reason, execution_time_ms
                  FROM audit_events
                 WHERE thread_id = ?
                 ORDER BY id
                """,
                (thread_id,)
            )
            return [dict(r) for r in cur.fetchall()]
    except Exception:
        return []


# ─── Session state ─────────────────────────────────────────────────────────
if "thread_id" not in st.session_state:
    st.session_state.thread_id = None
if "pr_url" not in st.session_state:
    st.session_state.pr_url = ""
if "interrupt_payload" not in st.session_state:
    st.session_state.interrupt_payload = None
if "final" not in st.session_state:
    st.session_state.final = None


# ─── Page setup ────────────────────────────────────────────────────────────
st.set_page_config(page_title="HITL PR Review", page_icon="🤖", layout="wide")
st.title("🤖 HITL PR Review Agent")


# ─── Sidebar — recent sessions ─────────────────────────────────────────────
with st.sidebar:
    st.header("Recent Sessions")
    sessions = get_recent_sessions()
    if sessions:
        for s in sessions:
            tid_short = s["thread_id"][:8]
            risk = s["worst_risk"]
            risk_badge = "🔴" if risk == "high" else ("🟡" if risk == "med" else "🟢")
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{risk_badge} `{tid_short}`**")
                st.caption(f"{s['pr_url']}\n\nLast: {s['last_event'][:19]}")
            with col_b:
                if st.button("Load", key=f"btn_{s['thread_id']}"):
                    st.session_state.thread_id = s["thread_id"]
                    st.session_state.pr_url = s["pr_url"]
                    st.session_state.interrupt_payload = None
                    st.session_state.final = None
                    st.rerun()
            st.divider()
    else:
        st.caption("No sessions recorded yet.")


# ─── Top form — start a new review ─────────────────────────────────────────
with st.form("start"):
    pr_url = st.text_input(
        "PR URL", value=st.session_state.pr_url,
        placeholder="https://github.com/VinUni-AI20k/PR-Demo/pull/1",
    )
    submitted = st.form_submit_button("Run review", type="primary")


# ─── Renderers per interrupt kind ──────────────────────────────────────────
def render_approval_card(payload: dict) -> dict | None:
    """58–72% bucket: show the LLM review + 3 buttons. Return resume dict or None."""
    conf = payload["confidence"]
    st.subheader(f"Approval requested — confidence {conf:.0%}")
    st.caption(payload.get("confidence_reasoning", ""))
    st.markdown(payload.get("summary", ""))

    for c in payload.get("comments", []):
        st.markdown(f"- **[{c['severity']}]** `{c['file']}:{c.get('line') or '?'}` — {c['body']}")

    if payload.get("diff_preview"):
        with st.expander("Diff Preview"):
            st.code(payload.get("diff_preview", ""), language="diff")

    feedback = st.text_input("Feedback (optional)", key="approval_feedback")
    col1, col2, col3 = st.columns(3)

    if col1.button("Approve", type="primary", use_container_width=True):
        return {"choice": "approve", "feedback": feedback}
    if col2.button("Reject", use_container_width=True):
        return {"choice": "reject", "feedback": feedback}
    if col3.button("Edit", use_container_width=True):
        return {"choice": "edit", "feedback": feedback}
    return None


def render_escalation_card(payload: dict) -> dict | None:
    """< 58% bucket: show risk factors + question form. Return {question: answer} or None."""
    conf = payload["confidence"]
    st.subheader(f"Strong escalation — confidence {conf:.0%}")
    st.caption(payload.get("confidence_reasoning", ""))
    if payload.get("risk_factors"):
        st.error("Risks: " + ", ".join(payload["risk_factors"]))
    st.markdown(payload.get("summary", ""))

    with st.form("escalation"):
        st.markdown("### Escalation Questions from Senior Reviewer")
        answers: dict[str, str] = {}
        for i, q in enumerate(payload.get("questions", [])):
            answers[q] = st.text_input(f"Q: {q}", key=f"esc_q_{i}")
        submitted_esc = st.form_submit_button("Submit answers", type="primary")
        if submitted_esc:
            return answers
    return None


# ─── Drive the graph ───────────────────────────────────────────────────────
async def run_graph(pr_url: str, thread_id: str, resume_value=None):
    """Invoke the graph once. Returns the final result or {'__interrupt__': ...}."""
    async with AsyncSqliteSaver.from_conn_string(db_path()) as cp:
        await cp.setup()
        app = build_graph(cp)
        cfg = {"configurable": {"thread_id": thread_id}}

        if resume_value is None:
            result = await app.ainvoke(
                {"pr_url": pr_url, "thread_id": thread_id}, cfg
            )
        else:
            result = await app.ainvoke(
                Command(resume=resume_value), cfg
            )
        return result


# ─── Main flow ─────────────────────────────────────────────────────────────
if submitted and pr_url:
    st.session_state.pr_url = pr_url
    st.session_state.thread_id = str(uuid.uuid4())
    st.session_state.interrupt_payload = None
    st.session_state.final = None

    with st.spinner("Fetching PR + asking the LLM..."):
        result = asyncio.run(run_graph(pr_url, st.session_state.thread_id))

    if "__interrupt__" in result:
        st.session_state.interrupt_payload = result["__interrupt__"][0].value
    else:
        st.session_state.final = result

# Render the current interrupt card, if any
payload = st.session_state.interrupt_payload
if payload is not None:
    kind = payload.get("kind")
    answer = render_approval_card(payload) if kind == "approval_request" else render_escalation_card(payload)
    if answer is not None:
        with st.spinner("Resuming..."):
            result = asyncio.run(run_graph(
                st.session_state.pr_url, st.session_state.thread_id, resume_value=answer,
            ))
        if "__interrupt__" in result:
            st.session_state.interrupt_payload = result["__interrupt__"][0].value
        else:
            st.session_state.interrupt_payload = None
            st.session_state.final = result
        st.rerun()

# Render final state, if reached
if st.session_state.final is not None:
    final = st.session_state.final
    action = final.get("final_action", "?")
    if action.startswith("auto") or action.startswith("committed"):
        if action.startswith("auto"):
            st.success("✓ Auto-Approved — high confidence, review comment posted automatically!")
        else:
            st.success(f"✓ {action} — comment posted to {st.session_state.pr_url}")
        st.markdown(f"[View PR on GitHub]({st.session_state.pr_url})")
    elif action == "rejected":
        st.warning("Rejected — no comment posted")
    else:
        st.info(f"final_action = {action}")

    if "analysis" in final:
        analysis = final["analysis"]
        st.markdown(f"**Confidence:** {analysis.confidence:.0%}")
        st.markdown(f"**Reasoning:** {analysis.confidence_reasoning}")
        st.markdown(f"**Summary:** {analysis.summary}")
        if analysis.comments:
            with st.expander("Review Comments"):
                for c in analysis.comments:
                    st.markdown(f"- **[{c.severity}]** `{c.file}:{c.line or '?'}` — {c.body}")

    st.caption(f"thread_id = `{st.session_state.thread_id}`  ·  replay: "
               f"`uv run python -m audit.replay --thread {st.session_state.thread_id}`")

# Always show timeline of current session if thread_id is set
if st.session_state.thread_id:
    events = get_session_events(st.session_state.thread_id)
    if events:
        with st.expander("Session Audit Trail", expanded=False):
            st.dataframe(events, use_container_width=True)
