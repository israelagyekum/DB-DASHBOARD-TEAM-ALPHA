"""
GADMS Analytics Dashboard
=========================
Portfolio dashboard for the Governed Academic Data Management System.

Two connection modes (auto-detected):
  1. Cloud Postgres  -- if a DATABASE_URL is in st.secrets or env vars
  2. Local DuckDB    -- loads ./TEAM_ALPHA.sql into an in-memory database
                        so the app runs anywhere with zero setup.

DSCD 606 Data Management Techniques  |  University of Ghana
"""

import pandas as pd
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go

# Shared DB utilities — connection is cached at process level so the
# Admin page (pages/2_🔐_Admin.py) writes to the same DuckDB instance.
from db import get_connection, q

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="GADMS Analytics",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Light custom styling
st.markdown("""
<style>
  .block-container { padding-top: 2rem; padding-bottom: 2rem; }
  [data-testid="stMetricValue"] { font-size: 2rem; font-weight: 700; color: #1F3864; }
  [data-testid="stMetricLabel"] { font-size: 0.9rem; color: #555; }
  h1 { color: #1F3864; }
  h2, h3 { color: #2E75B6; }
  .stTabs [data-baseweb="tab-list"] { gap: 8px; }
  .stTabs [data-baseweb="tab"] {
      background-color: #F2F6FB; border-radius: 6px 6px 0 0; padding: 8px 16px;
  }
  .stTabs [aria-selected="true"] { background-color: #1F3864 !important; color: white !important; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# HEADER
# =====================================================================
col_l, col_r = st.columns([4, 1])
with col_l:
    st.title("🎓 GADMS Analytics Dashboard")
    st.caption(
        "Governed Academic Data Management System  •  "
        "DSCD 606 Data Management Techniques  •  University of Ghana"
    )
with col_r:
    kind, _ = get_connection()
    badge = "🟢 Postgres (live)" if kind == "postgres" else "🦆 DuckDB (embedded)"
    st.markdown(
        f"<div style='text-align:right; padding-top:1.2rem;'>"
        f"<span style='background:#1F3864;color:white;padding:6px 12px;"
        f"border-radius:6px;font-size:0.85rem;'>{badge}</span></div>",
        unsafe_allow_html=True,
    )

st.divider()

# =====================================================================
# SIDEBAR  — global filters
# =====================================================================
st.sidebar.header("🔎 Filters")

programmes = q("SELECT DISTINCT ProgrammeName FROM Programme ORDER BY ProgrammeName")["ProgrammeName"].tolist()
sel_programmes = st.sidebar.multiselect("Programme", programmes, default=programmes)

statuses = q("SELECT DISTINCT Status FROM Student ORDER BY Status")["Status"].tolist()
sel_statuses = st.sidebar.multiselect("Student status", statuses, default=statuses)

genders = q("SELECT DISTINCT Gender FROM Student WHERE Gender IS NOT NULL ORDER BY Gender")["Gender"].tolist()
sel_genders = st.sidebar.multiselect("Gender", genders, default=genders)

st.sidebar.divider()
st.sidebar.markdown(
    "**About**  \n"
    "Built on the GADMS PostgreSQL schema: 12 tables, 1,019 records, "
    "fully constrained with referential integrity.  \n\n"
    "**Tech**  \n"
    "Streamlit · Plotly · pandas · PostgreSQL / DuckDB"
)


def _in_clause(values):
    if not values:
        return "('__none__')"
    escaped = ",".join("'" + v.replace("'", "''") + "'" for v in values)
    return f"({escaped})"


P_FILTER = _in_clause(sel_programmes)
S_FILTER = _in_clause(sel_statuses)
G_FILTER = _in_clause(sel_genders)

STUDENT_WHERE = f"""
  s.Status   IN {S_FILTER}
  AND s.Gender IN {G_FILTER}
  AND p.ProgrammeName IN {P_FILTER}
"""

# =====================================================================
# KPI ROW
# =====================================================================
kpi_sql = f"""
SELECT
  (SELECT COUNT(*) FROM Student s JOIN Programme p ON s.ProgrammeID=p.ProgrammeID
   WHERE {STUDENT_WHERE}) AS students,
  (SELECT COUNT(*) FROM Enrollment e
   JOIN Student s ON s.StudentID=e.StudentID
   JOIN Programme p ON p.ProgrammeID=s.ProgrammeID
   WHERE {STUDENT_WHERE}) AS enrollments,
  (SELECT COUNT(*) FROM AssessmentResult) AS results,
  (SELECT ROUND(AVG(0.4*CourseworkScore + 0.6*ExamScore)::numeric, 2)
     FROM AssessmentResult) AS avg_mark,
  (SELECT COALESCE(SUM(Balance),0) FROM FeePayment) AS outstanding,
  (SELECT COUNT(*) FROM LMSActivity) AS lms_events
"""
# DuckDB needs ::DOUBLE not ::numeric
if get_connection()[0] == "duckdb":
    kpi_sql = kpi_sql.replace("::numeric", "::DOUBLE")

kpi = q(kpi_sql).iloc[0]

c1, c2, c3, c4, c5, c6 = st.columns(6)
c1.metric("👥 Students", f"{int(kpi['Students']):,}")
c2.metric("📚 Enrollments", f"{int(kpi['Enrollments']):,}")
c3.metric("📝 Graded results", f"{int(kpi['Results']):,}")
c4.metric("📊 Avg weighted mark", f"{float(kpi['avg_mark']):.2f}")
c5.metric("💰 Outstanding (GHS)", f"{float(kpi['Outstanding']):,.0f}")
c6.metric("💻 LMS events", f"{int(kpi['lms_events']):,}")

st.divider()

# =====================================================================
# TABS
# =====================================================================
tab_o, tab_p, tab_l, tab_f, tab_d, tab_q = st.tabs(
    ["📊 Overview", "🎯 Performance", "💻 LMS Engagement", "💰 Finance", "🗂️ Data Explorer", "🧪 Query Lab"]
)


# ---------- OVERVIEW ----------
with tab_o:
    st.subheader("Programme & demographic mix")

    a, b = st.columns(2)
    with a:
        df = q(f"""
            SELECT p.ProgrammeName, COUNT(*) AS Students
            FROM Student s JOIN Programme p ON s.ProgrammeID = p.ProgrammeID
            WHERE {STUDENT_WHERE}
            GROUP BY p.ProgrammeName ORDER BY Students DESC
        """)
        fig = px.bar(df, x="ProgrammeName", y="Students", text="Students",
                     color="Students", color_continuous_scale="Blues",
                     title="Students per programme")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, coloraxis_showscale=False,
                          xaxis_title="", yaxis_title="Students")
        st.plotly_chart(fig, use_container_width=True)

    with b:
        df = q(f"""
            SELECT s.Gender, COUNT(*) AS Students
            FROM Student s JOIN Programme p ON s.ProgrammeID = p.ProgrammeID
            WHERE {STUDENT_WHERE}
            GROUP BY s.Gender ORDER BY Students DESC
        """)
        fig = px.pie(df, names="Gender", values="Students", hole=0.5,
                     color_discrete_sequence=["#1F3864", "#2E75B6", "#8FAADC"],
                     title="Gender split")
        st.plotly_chart(fig, use_container_width=True)

    c, d = st.columns(2)
    with c:
        df = q(f"""
            SELECT s.Status, COUNT(*) AS Students
            FROM Student s JOIN Programme p ON s.ProgrammeID = p.ProgrammeID
            WHERE {STUDENT_WHERE}
            GROUP BY s.Status ORDER BY Students DESC
        """)
        fig = px.bar(df, x="Status", y="Students", text="Students",
                     color="Status", title="Status distribution",
                     color_discrete_sequence=px.colors.qualitative.Set2)
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Students")
        st.plotly_chart(fig, use_container_width=True)
    with d:
        df = q(f"""
            SELECT p.ProgrammeName, s.Gender, COUNT(*) AS n
            FROM Student s JOIN Programme p ON s.ProgrammeID = p.ProgrammeID
            WHERE {STUDENT_WHERE}
            GROUP BY p.ProgrammeName, s.Gender
        """)
        fig = px.bar(df, x="ProgrammeName", y="n", color="Gender", barmode="stack",
                     title="Programme × Gender",
                     color_discrete_sequence=["#1F3864", "#2E75B6", "#8FAADC"])
        fig.update_layout(xaxis_title="", yaxis_title="Students")
        st.plotly_chart(fig, use_container_width=True)


# ---------- PERFORMANCE ----------
with tab_p:
    st.subheader("Academic performance")

    a, b = st.columns([2, 1])
    with a:
        df = q(f"""
            SELECT p.ProgrammeName,
                   ROUND(AVG(0.4*ar.CourseworkScore + 0.6*ar.ExamScore)::{ 'DOUBLE' if get_connection()[0]=='duckdb' else 'numeric' }, 2) AS AvgMark,
                   COUNT(*) AS Results
            FROM Programme p
            JOIN Student s        ON p.ProgrammeID = s.ProgrammeID
            JOIN Enrollment e     ON s.StudentID   = e.StudentID
            JOIN AssessmentResult ar ON ar.EnrollmentID = e.EnrollmentID
            WHERE {STUDENT_WHERE}
            GROUP BY p.ProgrammeName
            ORDER BY AvgMark DESC
        """)
        fig = px.bar(df, x="ProgrammeName", y="AvgMark", text="AvgMark",
                     color="AvgMark", color_continuous_scale="Tealgrn",
                     title="Average weighted mark by programme (40% CW + 60% Exam)")
        fig.update_traces(textposition="outside")
        fig.update_layout(yaxis_title="Avg mark", xaxis_title="",
                          coloraxis_showscale=False, yaxis_range=[0, 100])
        st.plotly_chart(fig, use_container_width=True)

    with b:
        df = q("""
            SELECT FinalGrade AS Grade, COUNT(*) AS Count
            FROM AssessmentResult GROUP BY FinalGrade
            ORDER BY CASE FinalGrade
                WHEN 'A' THEN 1 WHEN 'B+' THEN 2 WHEN 'B' THEN 3
                WHEN 'C+' THEN 4 WHEN 'C' THEN 5 WHEN 'D+' THEN 6
                WHEN 'D' THEN 7 WHEN 'F' THEN 8 ELSE 9 END
        """)
        fig = px.bar(df, x="Grade", y="Count", text="Count",
                     color="Grade", title="Grade distribution",
                     color_discrete_sequence=px.colors.qualitative.Bold)
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, xaxis_title="", yaxis_title="Count")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Coursework vs Exam — each dot is one assessment result")
    df = q(f"""
        SELECT ar.CourseworkScore, ar.ExamScore, ar.FinalGrade,
               p.ProgrammeName
        FROM AssessmentResult ar
        JOIN Enrollment e ON e.EnrollmentID = ar.EnrollmentID
        JOIN Student s    ON s.StudentID = e.StudentID
        JOIN Programme p  ON p.ProgrammeID = s.ProgrammeID
        WHERE {STUDENT_WHERE}
    """)
    fig = px.scatter(df, x="CourseworkScore", y="ExamScore", color="FinalGrade",
                     symbol="ProgrammeName", opacity=0.75,
                     color_discrete_sequence=px.colors.qualitative.Bold,
                     title=None)
    fig.add_shape(type="line", x0=0, y0=50, x1=100, y1=50,
                  line=dict(color="grey", dash="dot"))
    fig.add_shape(type="line", x0=50, y0=0, x1=50, y1=100,
                  line=dict(color="grey", dash="dot"))
    fig.update_layout(xaxis_title="Coursework score", yaxis_title="Exam score",
                      xaxis_range=[0, 100], yaxis_range=[0, 100])
    st.plotly_chart(fig, use_container_width=True)


# ---------- LMS ----------
with tab_l:
    st.subheader("LMS engagement vs outcome — early-warning view")

    df = q(f"""
        SELECT s.StudentID,
               s.FirstName || ' ' || s.LastName AS FullName,
               p.ProgrammeName,
               co.CourseOfferingID,
               COUNT(l.ActivityID) AS Events,
               COALESCE(SUM(l.DurationMinutes),0) AS Minutes,
               ar.FinalGrade
        FROM Student s
        JOIN Programme p     ON p.ProgrammeID = s.ProgrammeID
        JOIN Enrollment e    ON e.StudentID = s.StudentID
        JOIN CourseOffering co ON co.CourseOfferingID = e.CourseOfferingID
        LEFT JOIN LMSActivity l ON l.StudentID = s.StudentID
                              AND l.CourseOfferingID = co.CourseOfferingID
        LEFT JOIN AssessmentResult ar ON ar.EnrollmentID = e.EnrollmentID
        WHERE {STUDENT_WHERE}
        GROUP BY s.StudentID, s.FirstName, s.LastName, p.ProgrammeName,
                 co.CourseOfferingID, ar.FinalGrade
    """)

    a, b = st.columns(2)
    with a:
        fig = px.scatter(
            df, x="Minutes", y="Events", color="FinalGrade", size_max=14,
            hover_data=["FullName", "ProgrammeName", "CourseOfferingID"],
            color_discrete_sequence=px.colors.qualitative.Bold,
            title="LMS minutes vs LMS events  (colour = final grade)"
        )
        fig.update_layout(xaxis_title="Total minutes", yaxis_title="LMS events")
        st.plotly_chart(fig, use_container_width=True)

    with b:
        atype = q("""
            SELECT ActivityType, COUNT(*) AS n
            FROM LMSActivity GROUP BY ActivityType ORDER BY n DESC
        """)
        fig = px.bar(atype, x="ActivityType", y="n", text="n",
                     color="n", color_continuous_scale="Purples",
                     title="Activity-type breakdown")
        fig.update_traces(textposition="outside")
        fig.update_layout(showlegend=False, coloraxis_showscale=False,
                          xaxis_title="", yaxis_title="Events")
        st.plotly_chart(fig, use_container_width=True)

    st.markdown("##### Top 15 by LMS minutes (potential at-risk if minutes high but grade low)")
    st.dataframe(
        df.sort_values("Minutes", ascending=False).head(15).reset_index(drop=True),
        use_container_width=True, hide_index=True
    )


# ---------- FINANCE ----------
with tab_f:
    st.subheader("Fee governance")

    a, b = st.columns(2)
    with a:
        df = q("""
            SELECT PaymentMethod, COUNT(*) AS Payments, SUM(AmountPaid) AS Total
            FROM FeePayment GROUP BY PaymentMethod ORDER BY Total DESC
        """)
        fig = px.bar(df, x="PaymentMethod", y="Total", text="Payments",
                     color="Total", color_continuous_scale="Greens",
                     title="Payment volume by method (bar=GHS, label=#tx)")
        fig.update_traces(textposition="outside")
        fig.update_layout(coloraxis_showscale=False,
                          xaxis_title="", yaxis_title="Total amount (GHS)")
        st.plotly_chart(fig, use_container_width=True)

    with b:
        out = q(f"""
            SELECT s.StudentID,
                   s.FirstName || ' ' || s.LastName AS FullName,
                   p.ProgrammeName,
                   SUM(f.AmountPaid) AS Paid,
                   SUM(f.Balance) AS Outstanding
            FROM Student s
            JOIN Programme p   ON p.ProgrammeID = s.ProgrammeID
            JOIN FeePayment f  ON f.StudentID   = s.StudentID
            WHERE {STUDENT_WHERE}
            GROUP BY s.StudentID, s.FirstName, s.LastName, p.ProgrammeName
            HAVING SUM(f.Balance) > 0
            ORDER BY Outstanding DESC
        """)
        st.markdown("##### Students with outstanding balances")
        st.dataframe(out, use_container_width=True, hide_index=True,
                     column_config={
                        "Paid": st.column_config.NumberColumn(format="GHS %.2f"),
                        "Outstanding": st.column_config.NumberColumn(format="GHS %.2f"),
                     })


# ---------- DATA EXPLORER ----------
with tab_d:
    st.subheader("Browse any table")
    tables = ["Department", "Programme", "Course", "Lecturer", "Semester",
              "CourseOffering", "Student", "Enrollment", "AssessmentResult",
              "FeePayment", "LMSActivity"]
    pick = st.selectbox("Table", tables, index=tables.index("Student"))
    df = q(f"SELECT * FROM {pick}")
    st.caption(f"{len(df):,} rows  ·  {len(df.columns)} columns")
    st.dataframe(df, use_container_width=True, hide_index=True)
    st.download_button(
        f"⬇️ Download {pick}.csv",
        df.to_csv(index=False).encode(),
        file_name=f"{pick}.csv",
        mime="text/csv",
    )


# ---------- QUERY LAB ----------
with tab_q:
    st.subheader("Run your own SQL")
    st.caption(
        "Read-only. Backed by your live GADMS database. Use this to demo "
        "ad-hoc analytics during an interview."
    )

    default_query = """SELECT p.ProgrammeName,
       ROUND(AVG(0.4*ar.CourseworkScore + 0.6*ar.ExamScore), 2) AS AvgMark,
       COUNT(*) AS Results
FROM Programme p
JOIN Student s        ON p.ProgrammeID = s.ProgrammeID
JOIN Enrollment e     ON s.StudentID   = e.StudentID
JOIN AssessmentResult ar ON ar.EnrollmentID = e.EnrollmentID
GROUP BY p.ProgrammeName
ORDER BY AvgMark DESC;"""

    sql_input = st.text_area("SQL", value=default_query, height=180)
    if st.button("▶ Run", type="primary"):
        sql = sql_input.strip().rstrip(";")
        forbidden = ("INSERT", "UPDATE", "DELETE", "DROP", "ALTER",
                     "TRUNCATE", "CREATE", "GRANT", "REVOKE")
        if any(w in sql.upper().split() for w in forbidden):
            st.error("Only read-only SELECT queries are allowed.")
        else:
            try:
                df = q(sql)
                st.success(f"Returned {len(df):,} rows.")
                st.dataframe(df, use_container_width=True, hide_index=True)
            except Exception as ex:
                st.error(f"Query failed: {ex}")


# =====================================================================
# FOOTER
# =====================================================================
st.divider()
st.caption(
    "Built by the GADMS team · DSCD 606 Data Management Techniques · "
    "University of Ghana · Data: 100 students, 302 enrolments, 302 results, "
    "100 payments, 500 LMS events"
)
