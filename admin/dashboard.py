"""
Healthcare Administrator Evaluation Dashboard.
Provides high-level metrics, analytical charts, drill-down session inspection, and AI-powered insights.
Updated for 5 Healthcare Camp Feedback Questions:
1. Patient Name & Village
2. Health Problems & Symptoms
3. Health Assistant Service Rating
4. Treatment Explanation Clarity
5. Camp Improvement Suggestions
"""
import streamlit as st
import pandas as pd

# Safe optional import of plotly
try:
    import plotly.express as px
    HAS_PLOTLY = True
except ImportError:
    px = None
    HAS_PLOTLY = False
from database.repository import (
    get_analytics_summary,
    get_all_sessions,
    get_all_feedback_records,
    count_feedback_records,
    get_feedback_by_session
)
from agent.questions import get_question
from services.feedback_analysis import generate_admin_report_summary, analyze_session_feedback

# Charts and reports operate on a bounded recent window; the full dataset is
# reachable through server-side pagination and CSV export.
CHART_WINDOW = 2000
PAGE_SIZE_OPTIONS = [25, 50, 100]
EXPORT_ROW_LIMIT = 20000


def _cache_scope() -> str:
    """Cache key part so RLS-scoped data is never shared between users."""
    return (
        f"{st.session_state.get('sb_user_id') or 'local'}|"
        f"{st.session_state.get('sb_role') or '-'}|"
        f"{st.session_state.get('sb_camp_id') or '-'}"
    )


@st.cache_data(ttl=30, show_spinner=False)
def _cached_records(scope, limit, offset=0, language=None, status=None,
                    search=None, date_prefix=None):
    return get_all_feedback_records(
        limit=limit, offset=offset, language=language, status=status,
        search=search, date_prefix=date_prefix
    )


@st.cache_data(ttl=30, show_spinner=False)
def _cached_count(scope, language=None, status=None, search=None, date_prefix=None):
    return count_feedback_records(
        language=language, status=status, search=search, date_prefix=date_prefix
    )


@st.cache_data(ttl=30, show_spinner=False)
def _cached_summary(scope):
    return get_analytics_summary()


def render_admin_dashboard():
    st.markdown("""
    <div style="margin-bottom: 24px;">
        <div style="font-size: 0.78rem; font-weight: 700; color: #0D9488; text-transform: uppercase; letter-spacing: 0.06em; margin-bottom: 4px;">
            Clinical Operations & Quality Evaluation
        </div>
        <h2 style="font-size: 1.65rem; font-weight: 800; color: #0F172A; margin: 0 0 6px 0; letter-spacing: -0.02em;">
            🏥 Healthcare Camp Administrator Dashboard
        </h2>
        <p style="color: #64748B; font-size: 0.88rem; margin: 0;">
            Monitor patient experiences, evaluate health assistant services, and inspect English feedback across rural camp clusters.
        </p>
    </div>
    """, unsafe_allow_html=True)

    scope = _cache_scope()
    summary = _cached_summary(scope)

    # KPI Metric Cards
    kpi1, kpi2, kpi3, kpi4, kpi5 = st.columns(5)
    kpi1.metric("Total Patients", summary.get("total_sessions", 0))
    kpi2.metric("Completed", summary.get("completed_sessions", 0))
    kpi3.metric("Incomplete", summary.get("incomplete_sessions", 0))
    kpi4.metric("Avg Assistant Rating", f"⭐ {summary.get('avg_satisfaction', 0.0)} / 5")
    kpi5.metric("Hindi / Telugu", f"{summary.get('hindi_sessions', 0)} / {summary.get('telugu_sessions', 0)}")

    st.divider()

    records = _cached_records(scope, CHART_WINDOW)
    df = pd.DataFrame(records) if records else pd.DataFrame()

    tab1, tab2, tab3 = st.tabs(["📊 Analytics & Visualizations", "📋 Feedback Records & Detail", "🤖 AI Qualitative Insights"])

    with tab1:
        if df.empty:
            st.info("No feedback data recorded yet. Collect responses via the Patient Feedback view to populate analytics.")
        else:
            c1, c2 = st.columns(2)

            # 1. Language Distribution
            with c1:
                st.subheader("Language Distribution")
                lang_counts = df.drop_duplicates(subset=["session_id"])["language"].value_counts().reset_index()
                lang_counts.columns = ["Language", "Count"]
                lang_counts["Language"] = lang_counts["Language"].map({"hi": "Hindi (हिंदी)", "te": "Telugu (తెలుగు)"}).fillna(lang_counts["Language"])
                if HAS_PLOTLY:
                    fig_lang = px.pie(
                        lang_counts,
                        names="Language",
                        values="Count",
                        hole=0.48,
                        color_discrete_sequence=["#0D9488", "#3B82F6"]
                    )
                    fig_lang.update_layout(
                        margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Plus Jakarta Sans, Inter, sans-serif")
                    )
                    st.plotly_chart(
                        fig_lang, width="stretch", key="language_distribution_chart"
                    )
                else:
                    st.bar_chart(lang_counts.set_index("Language"))

            # 2. Health Assistant Service Rating Breakdown (Q3)
            with c2:
                st.subheader("Health Assistant Service Ratings (Q3)")
                ratings_df = df[df["rating"].notnull()]
                if not ratings_df.empty:
                    if HAS_PLOTLY:
                        fig_rating = px.histogram(
                            ratings_df,
                            x="rating",
                            nbins=5,
                            color_discrete_sequence=["#10B981"],
                            labels={"rating": "Service Rating (1 to 5 Stars)", "count": "Responses"}
                        )
                        fig_rating.update_layout(
                            xaxis=dict(tickmode="linear", tick0=1, dtick=1),
                            margin=dict(t=20, b=20, l=20, r=20),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Plus Jakarta Sans, Inter, sans-serif")
                        )
                        st.plotly_chart(
                            fig_rating, width="stretch", key="service_rating_chart"
                        )
                    else:
                        st.bar_chart(ratings_df["rating"].value_counts().sort_index())
                else:
                    st.write("No ratings recorded yet.")

            # 3. Question-Wise Responses Breakdown
            st.subheader("Question-Wise Response Status")
            q_df = df[df["question_number"].isin([1, 2, 3, 4, 5])].copy()
            if not q_df.empty:
                q_summary = q_df.groupby(["question_number", "response_type"]).size().reset_index(name="count")
                q_names = {
                    1: "Q1: Name & Village / పేరు, గ్రామం",
                    2: "Q2: Health Problems / సమస్యలు",
                    3: "Q3: Assistant Service / సేవ",
                    4: "Q4: Explanation / వివరణ",
                    5: "Q5: Camp Suggestions / సలహాలు"
                }
                q_summary["Question"] = q_summary["question_number"].map(q_names)
                if HAS_PLOTLY:
                    fig_q = px.bar(
                        q_summary,
                        x="Question",
                        y="count",
                        color="response_type",
                        barmode="group",
                        color_discrete_map={
                            "yes": "#10B981",
                            "no": "#EF4444",
                            "not_sure": "#F59E0B",
                            "rating": "#0D9488",
                            "open_response": "#6366F1"
                        },
                        labels={"count": "Responses Count", "response_type": "Response Type"}
                    )
                    fig_q.update_layout(
                        margin=dict(t=20, b=20, l=20, r=20),
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor="rgba(0,0,0,0)",
                        font=dict(family="Plus Jakarta Sans, Inter, sans-serif")
                    )
                    st.plotly_chart(
                        fig_q, width="stretch", key="question_response_chart"
                    )
                else:
                    pivot_df = q_summary.pivot(index="Question", columns="response_type", values="count").fillna(0)
                    st.bar_chart(pivot_df)

    with tab2:
        st.subheader("All Collected Feedback Submissions")

        # Filters: Language, Status, Date, Search — executed by the database
        # (server-side), so no full table is ever pulled into memory.
        f_col1, f_col2, f_col3, f_col4 = st.columns(4)
        with f_col1:
            lang_filter = st.selectbox("Filter by Language", options=["All", "Hindi (hi)", "Telugu (te)"])
        with f_col2:
            status_filter = st.selectbox("Filter by Status", options=["All", "completed", "in_progress", "resolved"])
        with f_col3:
            date_filter = st.date_input("Filter by Date", value=None)
        with f_col4:
            search_query = st.text_input("Search Code, Name or Transcript", "")

        language = {"Hindi (hi)": "hi", "Telugu (te)": "te"}.get(lang_filter)
        status = status_filter if status_filter != "All" else None
        date_prefix = date_filter.strftime("%Y-%m-%d") if date_filter else None
        search = search_query.strip() or None

        total_rows = _cached_count(scope, language, status, search, date_prefix)

        page_size = st.selectbox("Rows per page", PAGE_SIZE_OPTIONS, index=1,
                                 key="dash_page_size")
        total_pages = max(1, -(-int(total_rows) // int(page_size)))
        if "dash_page" not in st.session_state:
            st.session_state.dash_page = 1
        page = max(1, min(int(st.session_state.dash_page), total_pages))

        nav1, nav2, nav3 = st.columns([1, 2, 1])
        with nav1:
            if st.button("◀️ Previous", disabled=(page <= 1)):
                st.session_state.dash_page = page - 1
                st.rerun()
        with nav2:
            st.caption(f"Page {page} of {total_pages} · {total_rows} matching row(s)")
        with nav3:
            if st.button("Next ▶️", disabled=(page >= total_pages)):
                st.session_state.dash_page = page + 1
                st.rerun()

        offset = (page - 1) * int(page_size)
        page_records = _cached_records(scope, int(page_size), offset, language,
                                       status, search, date_prefix)
        filtered_df = pd.DataFrame(page_records) if page_records else pd.DataFrame()

        record_cols = [
            "session_id", "patient_code", "patient_name", "language", "session_status",
            "question_number", "response_type", "transcript", "english_translation", "translation_status", "rating", "session_date"
        ]

        if filtered_df.empty:
            st.info("No feedback records match the current filters.")
        else:
            # Ensure display columns exist
            for c in record_cols:
                if c not in filtered_df.columns:
                    filtered_df[c] = "-"

            clean_display_df = filtered_df[record_cols].copy()
            clean_display_df["patient_name"] = clean_display_df["patient_name"].fillna("-")
            clean_display_df["question_number"] = clean_display_df["question_number"].fillna("-")
            clean_display_df["response_type"] = clean_display_df["response_type"].fillna("-")
            english_answers = clean_display_df["english_translation"].fillna("").astype(str).str.strip()
            clean_display_df["english_answer"] = english_answers.mask(
                english_answers.eq(""),
                "(English translation unavailable)"
            )
            clean_display_df["translation_status"] = clean_display_df["translation_status"].fillna("pending")
            clean_display_df["rating"] = clean_display_df["rating"].fillna("-")
            clean_display_df = clean_display_df.drop(columns=["transcript", "english_translation"])
            clean_display_df = clean_display_df[
                [
                    "session_id", "patient_code", "patient_name", "language", "session_status",
                    "question_number", "response_type", "english_answer", "translation_status",
                    "rating", "session_date"
                ]
            ]

            st.dataframe(
                clean_display_df,
                width="stretch",
                height=320
            )

        # Export English answers only; cap the dataset to keep free-tier memory bounded.
        with st.spinner("Preparing English CSV export..."):
            export_records = _cached_records(scope, EXPORT_ROW_LIMIT, 0, language,
                                             status, search, date_prefix)
        if export_records:
            export_df = pd.DataFrame(export_records)
            for c in record_cols:
                if c not in export_df.columns:
                    export_df[c] = "-"
            export_df = export_df[record_cols].copy()
            english_answers = export_df["english_translation"].fillna("").astype(str).str.strip()
            export_df["english_answer"] = english_answers.mask(
                english_answers.eq(""),
                "(English translation unavailable)"
            )
            csv_cols = [
                "session_id", "patient_code", "patient_name", "language", "session_status",
                "question_number", "response_type", "english_answer", "translation_status", "rating", "session_date"
            ]
            csv_data = export_df[csv_cols].to_csv(index=False).encode("utf-8")
            if len(export_records) >= EXPORT_ROW_LIMIT:
                st.warning(f"Export capped at {EXPORT_ROW_LIMIT} rows — narrow the filters for the complete dataset.")
            st.download_button(
                label="📥 Export Feedback to CSV (English)",
                data=csv_data,
                file_name="healthcare_camp_english_feedback.csv",
                mime="text/csv"
            )
        else:
            st.info("Nothing to export for the current filters.")

        st.divider()

        # Session drill down
        st.subheader("🔍 Inspect Single Patient Session (English View)")
        sessions = get_all_sessions(limit=50)
        if sessions:
            session_options = {
                f"Session #{s['id']} - {s.get('patient_name') or s['patient_code']} ({s['language'].upper()})": s['id']
                for s in sessions
            }
            selected_session_label = st.selectbox("Choose a Session:", list(session_options.keys()))
            sel_id = session_options[selected_session_label]

            s_data = get_feedback_by_session(sel_id)
            if s_data:
                p_name = s_data.get('patient_name') or 'Not recorded'
                st.write(f"**Patient Name / Village:** `{p_name}` | **ID:** `{s_data.get('patient_code')}` | **Status:** `{s_data.get('status')}`")

                for a in s_data.get("answers", []):
                    q_info = get_question(a['question_number'])
                    en_text = q_info.get("en_text", "")
                    question_text = en_text or a["question_text"]
                    with st.expander(f"Question {a['question_number']}: {question_text}", expanded=True):
                        if en_text:
                            st.caption(f"🌐 **Question Translation:** {en_text}")
                        st.write(f"**Response:** `{a['response_type']}`" + (f" | **Rating:** {a['rating']} ⭐" if a.get('rating') else ""))

                        english_answer = (a.get("english_translation") or "").strip()
                        if english_answer:
                            st.markdown("##### English Answer")
                            st.write(english_answer)
                        else:
                            st.warning("English translation is unavailable for this answer.")

                # Single session AI summary
                if st.button("Generate AI Session Summary", key=f"ai_sum_{sel_id}"):
                    with st.spinner("Analyzing patient feedback..."):
                        analysis = analyze_session_feedback(s_data)
                        st.success(f"**Sentiment Assessment:** {analysis['sentiment']}")
                        if analysis.get("is_ai"):
                            st.info(f"🤖 **Workers AI Analysis ({analysis.get('model_used', '@cf/zai-org/glm-4.7-flash')}):**\n\n{analysis['summary']}")
                        else:
                            st.caption("ℹ️ *Analysis produced via local heuristic assessment (Text AI optional/fallback).*")
                            st.write(analysis['summary'])

    with tab3:
        st.subheader("🤖 Health Camp Summarization & Community Insights")
        st.caption("Aggregated intelligence powered by Cloudflare Workers AI with zero-cost local heuristic fallback.")

        all_ans = [dict(r) for r in records] if records else []
        analysis_data = generate_admin_report_summary(all_ans)

        c_rep1, c_rep2 = st.columns(2)
        with c_rep1:
            st.markdown("""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); margin-bottom: 16px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #EF4444; text-transform: uppercase; margin-bottom: 4px;">Triage Priority</div>
                <h4 style="margin: 0 0 12px 0; color: #0F172A; font-weight: 700;">⚠️ Operational Areas & Concerns</h4>
            """, unsafe_allow_html=True)
            breakdown = analysis_data.get("issues_breakdown", {})
            for cat, cnt in breakdown.items():
                st.write(f"- **{cat}**: {cnt} flagged item(s)")

            st.markdown("##### 🚨 Top Clinical Friction Points")
            for c in analysis_data.get("top_complaints", []):
                st.warning(c)
            st.markdown("</div>", unsafe_allow_html=True)

        with c_rep2:
            st.markdown("""
            <div style="background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 16px; padding: 20px; box-shadow: 0 1px 3px rgba(0,0,0,0.03); margin-bottom: 16px;">
                <div style="font-size: 0.75rem; font-weight: 700; color: #0D9488; text-transform: uppercase; margin-bottom: 4px;">Patient Voice</div>
                <h4 style="margin: 0 0 12px 0; color: #0F172A; font-weight: 700;">🩺 Health Needs & Camp Suggestions</h4>
            """, unsafe_allow_html=True)
            st.markdown("##### Reported Symptoms & Ailments (Q2)")
            for hp in analysis_data.get("reported_health_problems", [])[:4]:
                st.write(f"• *{hp}*")

            st.markdown("##### Community Suggestions (Q5)")
            for sug in analysis_data.get("recent_suggestions", [])[:4]:
                st.info(f'"{sug}"')
            st.markdown("</div>", unsafe_allow_html=True)
