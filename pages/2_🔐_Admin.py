"""
Admin Backend  —  GADMS Student Management
==========================================
DSCD 606 Data Management Techniques  |  University of Ghana
"""

import sys
from pathlib import Path
from datetime import date

import streamlit as st
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent.parent))
from db import get_connection, q, run_write, is_postgres  # noqa: E402

# =====================================================================
# PAGE CONFIG
# =====================================================================
st.set_page_config(
    page_title="GADMS Admin",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)
st.markdown("""
<style>
  .block-container { padding-top: 2rem; padding-bottom: 2rem; }
  h1 { color: #1F3864; } h2, h3 { color: #2E75B6; }
  .stAlert { border-radius: 8px; }
</style>
""", unsafe_allow_html=True)


# =====================================================================
# PASSWORD GATE
# =====================================================================
def _get_admin_pw() -> str:
    try:
        pw = st.secrets.get("ADMIN_PASSWORD")
        if pw:
            return str(pw)
    except Exception:
        pass
    return "gadms2026"


def _password_check() -> None:
    if st.session_state.get("admin_auth"):
        return
    st.title("🔐 GADMS Admin — Login")
    pw_input = st.text_input("Password", type="password", key="pw_field")
    if st.button("Login", type="primary"):
        if pw_input == _get_admin_pw():
            st.session_state["admin_auth"] = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()


_password_check()


# =====================================================================
# HELPERS
# =====================================================================
def _esc(s: str) -> str:
    return str(s).replace("'", "''")


def _next_student_id() -> str:
    try:
        max_df = q("SELECT MAX(StudentID) AS m FROM Student")
        mid = str(max_df.iloc[0]["m"])
        if mid and mid.startswith("UG") and len(mid) >= 9:
            return f"UG{mid[2:6]}{str(int(mid[6:]) + 1).zfill(3)}"
    except Exception:
        pass
    return f"UG{date.today().year}101"


def _next_serial_id(table: str, id_col: str) -> int:
    """Get next available ID for a table — works with persistent DuckDB."""
    con = get_connection()
    row = con.execute(
        f"SELECT COALESCE(MAX({id_col}), 0) + 1 AS nid FROM {table}"
    ).fetchone()
    return int(row[0])


def _ok(msg: str):
    st.success(msg)
    st.info("Navigate to **📊 app** in the sidebar — changes are already live.")


# =====================================================================
# HEADER
# =====================================================================
st.title("🔐 GADMS Admin Backend")
st.caption("DSCD 606 Data Management Techniques  •  University of Ghana")

# Correct status message — DuckDB file IS persistent
st.success(
    "🟢 **DuckDB (persistent file)** — every change is permanently saved "
    "to `gadms_v3.duckdb` and immediately visible on the dashboard."
)

if st.sidebar.button("🚪 Logout"):
    st.session_state["admin_auth"] = False
    st.rerun()

st.divider()

# =====================================================================
# TABS
# =====================================================================
tab_add, tab_manage, tab_enroll, tab_fee, tab_lec, tab_prog = st.tabs([
    "➕ Add Student",
    "📋 Manage Students",
    "📚 Enrol in Course",
    "💰 Fee Management",
    "👨‍🏫 Lecturers & Courses",
    "🎓 Programmes",
])


# ─────────────────────────────────────────────────────────────────────
# TAB 1 — ADD STUDENT
# ─────────────────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Add a New Student")

    programmes_df = q("SELECT ProgrammeID, ProgrammeName, DegreeType FROM Programme ORDER BY ProgrammeName")
    prog_map = {
        f"{r['ProgrammeName']} ({r['DegreeType']})": int(r["ProgrammeID"])
        for _, r in programmes_df.iterrows()
    }

    with st.form("add_student_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        with c1:
            student_id = st.text_input("Student ID *", value=_next_student_id())
            first_name = st.text_input("First Name *")
            last_name  = st.text_input("Last Name *")
            email      = st.text_input("Email", placeholder="firstname.lastnameN@st.ug.edu.gh")
            phone      = st.text_input("Phone Number")
        with c2:
            prog_label = st.selectbox("Programme *", list(prog_map.keys()))
            gender     = st.selectbox("Gender", ["Male", "Female", "Other"])
            dob        = st.date_input("Date of Birth", value=date(2000, 1, 1),
                                       min_value=date(1950, 1, 1), max_value=date.today())
            adm_year   = st.number_input("Admission Year", min_value=2000, max_value=2100,
                                         value=date.today().year, step=1)
            status     = st.selectbox("Status", ["Active", "Suspended", "Graduated", "Withdrawn"])
        submitted = st.form_submit_button("➕ Add Student", type="primary", use_container_width=True)

    if submitted:
        errs = [m for cond, m in [
            (not student_id.strip(), "Student ID is required."),
            (not first_name.strip(), "First Name is required."),
            (not last_name.strip(),  "Last Name is required."),
        ] if cond]
        if errs:
            for e in errs:
                st.error(e)
        else:
            email_sql = f"'{_esc(email)}'" if email.strip() else "NULL"
            phone_sql = f"'{_esc(phone)}'" if phone.strip() else "NULL"
            sql = f"""
                INSERT INTO Student (StudentID, ProgrammeID, FirstName, LastName,
                  Gender, DateOfBirth, Email, PhoneNumber, AdmissionYear, Status)
                VALUES ('{_esc(student_id.strip())}', {prog_map[prog_label]},
                  '{_esc(first_name.strip())}', '{_esc(last_name.strip())}',
                  '{gender}', '{dob.strftime('%Y-%m-%d')}',
                  {email_sql}, {phone_sql}, {int(adm_year)}, '{status}')
            """
            try:
                run_write(sql)
                _ok(f"✅ **{first_name.strip()} {last_name.strip()}** (ID: `{student_id.strip()}`) added!")
            except Exception as ex:
                st.error("Duplicate ID or email." if "UNIQUE" in str(ex).upper() else f"Error: {ex}")


# ─────────────────────────────────────────────────────────────────────
# TAB 2 — MANAGE STUDENTS
# ─────────────────────────────────────────────────────────────────────
with tab_manage:
    st.subheader("All Students")
    sc, sf = st.columns([3, 1])
    search        = sc.text_input("Search", placeholder="Name, ID, email…", label_visibility="collapsed")
    status_filter = sf.selectbox("Status", ["All", "Active", "Suspended", "Graduated", "Withdrawn"],
                                 label_visibility="collapsed")

    sdf = q("""SELECT s.StudentID, s.FirstName, s.LastName, p.ProgrammeName,
                      s.Gender, s.Status, s.Email, s.AdmissionYear
               FROM Student s JOIN Programme p ON p.ProgrammeID = s.ProgrammeID
               ORDER BY s.StudentID""")

    if search.strip():
        mask = (sdf["StudentID"].str.contains(search, case=False, na=False)
              | sdf["FirstName"].str.contains(search, case=False, na=False)
              | sdf["LastName"].str.contains(search, case=False, na=False)
              | sdf["Email"].str.contains(search, case=False, na=False))
        sdf = sdf[mask]
    if status_filter != "All":
        sdf = sdf[sdf["Status"] == status_filter]

    st.caption(f"**{len(sdf):,}** student(s)")
    st.dataframe(sdf, use_container_width=True, hide_index=True)
    st.download_button("⬇️ Download (.csv)", sdf.to_csv(index=False).encode(),
                       "students_export.csv", "text/csv")

    st.divider()
    st.subheader("Quick Update")
    with st.form("update_form"):
        u1, u2 = st.columns(2)
        sid_upd   = u1.text_input("Student ID", placeholder="e.g. UG2026001")
        field_upd = u2.selectbox("Field", ["Status", "Programme"])

        if field_upd == "Status":
            new_val = st.selectbox("New value", ["Active", "Suspended", "Graduated", "Withdrawn"])
            pm2 = {}
        else:
            p2  = q("SELECT ProgrammeID, ProgrammeName FROM Programme ORDER BY ProgrammeName")
            pm2 = {r["ProgrammeName"]: int(r["ProgrammeID"]) for _, r in p2.iterrows()}
            new_val = st.selectbox("New programme", list(pm2.keys()))

        if st.form_submit_button("✏️ Apply", type="primary"):
            if not sid_upd.strip():
                st.error("Enter a Student ID.")
            else:
                if field_upd == "Status":
                    upd = f"UPDATE Student SET Status = '{new_val}' WHERE StudentID = '{_esc(sid_upd.strip())}'"
                else:
                    upd = f"UPDATE Student SET ProgrammeID = {pm2[new_val]} WHERE StudentID = '{_esc(sid_upd.strip())}'"
                try:
                    run_write(upd)
                    st.success(f"✅ **{field_upd}** updated to **{new_val}** for `{sid_upd.strip()}`")
                except Exception as ex:
                    st.error(f"Update failed: {ex}")


# ─────────────────────────────────────────────────────────────────────
# TAB 3 — ENROL IN COURSE
# ─────────────────────────────────────────────────────────────────────
with tab_enroll:
    st.subheader("Enrol a Student in a Course Offering")

    off_df = q("""SELECT co.CourseOfferingID,
                         c.CourseCode || ' - ' || c.CourseTitle AS CourseName,
                         co.AcademicYear, l.LecturerName
                  FROM CourseOffering co
                  JOIN Course c ON c.CourseID = co.CourseID
                  JOIN Lecturer l ON l.LecturerID = co.LecturerID
                  ORDER BY co.CourseOfferingID""")
    off_map = {
        f"[{r['CourseOfferingID']}] {r['CourseName']} ({r['AcademicYear']}) - {r['LecturerName']}":
            int(r["CourseOfferingID"])
        for _, r in off_df.iterrows()
    }

    with st.form("enroll_form"):
        e1, e2        = st.columns(2)
        enroll_sid    = e1.text_input("Student ID *", placeholder="e.g. UG2026101")
        off_label     = e2.selectbox("Course Offering *", list(off_map.keys()))
        enroll_date   = st.date_input("Enrollment Date", value=date.today())
        enroll_status = st.selectbox("Status", ["Active", "Completed", "Dropped", "Failed"])
        enroll_btn    = st.form_submit_button("📚 Enrol", type="primary")

    if enroll_btn:
        if not enroll_sid.strip():
            st.error("Student ID required.")
        else:
            oid = off_map[off_label]
            nid = _next_serial_id("Enrollment", "EnrollmentID")
            sql = f"""INSERT INTO Enrollment
                      (EnrollmentID, StudentID, CourseOfferingID, EnrollmentDate, EnrollmentStatus)
                      VALUES ({nid}, '{_esc(enroll_sid.strip())}', {oid},
                              '{enroll_date.strftime('%Y-%m-%d')}', '{enroll_status}')"""
            try:
                run_write(sql)
                _ok(f"✅ Enrolled `{enroll_sid.strip()}` successfully!")
            except Exception as ex:
                err = str(ex)
                if "UNIQUE" in err.upper():
                    st.error("Already enrolled in that offering.")
                else:
                    st.error(f"Failed: {ex}")


# ─────────────────────────────────────────────────────────────────────
# TAB 4 — FEE MANAGEMENT
# ─────────────────────────────────────────────────────────────────────
with tab_fee:
    st.subheader("Fee Management")
    fee_sub1, fee_sub2 = st.tabs(["➕ Record Payment", "📊 Fee Summary"])

    with fee_sub1:
        st.markdown("Record a new fee payment for a student.")
        with st.form("fee_form", clear_on_submit=True):
            f1, f2     = st.columns(2)
            fee_sid    = f1.text_input("Student ID *", placeholder="e.g. UG2026001")
            fee_method = f2.selectbox("Payment Method", ["Mobile Money", "Bank", "Card", "Cash"])
            fee_amount = f1.number_input("Amount Paid (GHS) *", min_value=0.0, step=100.0, format="%.2f")
            fee_bal    = f2.number_input("Remaining Balance (GHS)", min_value=0.0, step=100.0, format="%.2f")
            fee_date   = st.date_input("Payment Date", value=date.today())
            fee_btn    = st.form_submit_button("💰 Record Payment", type="primary", use_container_width=True)

        if fee_btn:
            if not fee_sid.strip():
                st.error("Student ID is required.")
            elif fee_amount <= 0:
                st.error("Amount must be greater than 0.")
            else:
                nid = _next_serial_id("FeePayment", "PaymentID")
                sql = f"""INSERT INTO FeePayment
                          (PaymentID, StudentID, AmountPaid, PaymentDate, PaymentMethod, Balance)
                          VALUES ({nid}, '{_esc(fee_sid.strip())}', {fee_amount},
                                  '{fee_date.strftime('%Y-%m-%d')}', '{fee_method}', {fee_bal})"""
                try:
                    run_write(sql)
                    _ok(f"✅ Payment of **GHS {fee_amount:,.2f}** recorded for `{fee_sid.strip()}`.")
                except Exception as ex:
                    st.error(f"Failed: {ex}")

    with fee_sub2:
        st.markdown("Summary of all fee payments per student.")
        fee_search = st.text_input("Filter by Student ID or Name",
                                   placeholder="e.g. UG2026001 or Israel", key="fee_search")
        fee_sum = q("""
            SELECT s.StudentID,
                   s.FirstName || ' ' || s.LastName AS FullName,
                   p.ProgrammeName,
                   COUNT(f.PaymentID)  AS NumPayments,
                   SUM(f.AmountPaid)   AS TotalPaid,
                   SUM(f.Balance)      AS TotalBalance
            FROM Student s
            JOIN Programme p ON p.ProgrammeID = s.ProgrammeID
            LEFT JOIN FeePayment f ON f.StudentID = s.StudentID
            GROUP BY s.StudentID, s.FirstName, s.LastName, p.ProgrammeName
            ORDER BY TotalBalance DESC
        """)
        if fee_search.strip():
            mask = (fee_sum["StudentID"].str.contains(fee_search, case=False, na=False)
                  | fee_sum["FullName"].str.contains(fee_search, case=False, na=False))
            fee_sum = fee_sum[mask]

        st.caption(f"**{len(fee_sum):,}** students")
        st.dataframe(fee_sum, use_container_width=True, hide_index=True,
                     column_config={
                         "TotalPaid":    st.column_config.NumberColumn("Total Paid (GHS)",  format="GHS %.2f"),
                         "TotalBalance": st.column_config.NumberColumn("Outstanding (GHS)", format="GHS %.2f"),
                     })
        st.download_button("⬇️ Download fee summary (.csv)",
                           fee_sum.to_csv(index=False).encode(), "fee_summary.csv", "text/csv")

        st.divider()
        st.subheader("Payment History for a Student")
        hist_sid = st.text_input("Student ID", placeholder="e.g. UG2026001", key="hist_sid")
        if hist_sid.strip():
            hist = q(f"""SELECT PaymentID, AmountPaid, PaymentDate, PaymentMethod, Balance
                         FROM FeePayment
                         WHERE StudentID = '{_esc(hist_sid.strip())}'
                         ORDER BY PaymentDate DESC""")
            if hist.empty:
                st.info("No payment records found for that student.")
            else:
                st.dataframe(hist, use_container_width=True, hide_index=True,
                             column_config={
                                 "AmountPaid": st.column_config.NumberColumn(format="GHS %.2f"),
                                 "Balance":    st.column_config.NumberColumn(format="GHS %.2f"),
                             })


# ─────────────────────────────────────────────────────────────────────
# TAB 5 — LECTURERS & COURSES
# ─────────────────────────────────────────────────────────────────────
with tab_lec:
    st.subheader("Lecturers & Course Assignments")
    lec_sub1, lec_sub2, lec_sub3 = st.tabs(["➕ Add Lecturer", "📋 View Lecturers", "🔗 Assign to Course"])

    with lec_sub1:
        depts_df = q("SELECT DepartmentID, DepartmentName FROM Department ORDER BY DepartmentName")
        dept_map = {r["DepartmentName"]: int(r["DepartmentID"]) for _, r in depts_df.iterrows()}

        with st.form("add_lecturer_form", clear_on_submit=True):
            l1, l2   = st.columns(2)
            lec_id   = l1.text_input("Lecturer ID *", placeholder="e.g. LEC004")
            lec_name = l2.text_input("Full Name *", placeholder="e.g. Dr. Kwame Asante")
            lec_dept = l1.selectbox("Department *", list(dept_map.keys()))
            lec_rank = l2.selectbox("Rank", ["Lecturer", "Senior Lecturer", "Associate Professor",
                                              "Professor", "Teaching Assistant", "Adjunct"])
            lec_email = st.text_input("Email", placeholder="name@ug.edu.gh")
            lec_btn   = st.form_submit_button("➕ Add Lecturer", type="primary", use_container_width=True)

        if lec_btn:
            if not lec_id.strip() or not lec_name.strip():
                st.error("Lecturer ID and Name are required.")
            else:
                email_sql = f"'{_esc(lec_email)}'" if lec_email.strip() else "NULL"
                sql = f"""INSERT INTO Lecturer (LecturerID, DepartmentID, LecturerName, Rank, Email)
                          VALUES ('{_esc(lec_id.strip())}', {dept_map[lec_dept]},
                                  '{_esc(lec_name.strip())}', '{_esc(lec_rank)}', {email_sql})"""
                try:
                    run_write(sql)
                    _ok(f"✅ Lecturer **{lec_name.strip()}** (ID: `{lec_id.strip()}`) added!")
                except Exception as ex:
                    st.error("Duplicate Lecturer ID or email." if "UNIQUE" in str(ex).upper() else f"Error: {ex}")

    with lec_sub2:
        lec_df = q("""SELECT l.LecturerID, l.LecturerName, d.DepartmentName, l.Rank, l.Email
                      FROM Lecturer l JOIN Department d ON d.DepartmentID = l.DepartmentID
                      ORDER BY l.LecturerName""")
        st.caption(f"**{len(lec_df):,}** lecturer(s) on record")
        st.dataframe(lec_df, use_container_width=True, hide_index=True)

    with lec_sub3:
        st.markdown("Create a new **Course Offering** — links a course, lecturer, and semester.")

        courses_df   = q("SELECT CourseID, CourseCode, CourseTitle FROM Course ORDER BY CourseCode")
        course_map   = {f"{r['CourseCode']} - {r['CourseTitle']}": int(r["CourseID"])
                        for _, r in courses_df.iterrows()}

        lec_list_df  = q("SELECT LecturerID, LecturerName FROM Lecturer ORDER BY LecturerName")
        lec_list_map = {f"{r['LecturerName']} ({r['LecturerID']})": str(r["LecturerID"])
                        for _, r in lec_list_df.iterrows()}

        sems_df  = q("SELECT SemesterID, SemesterName FROM Semester ORDER BY SemesterID")
        sem_map  = {r["SemesterName"]: int(r["SemesterID"]) for _, r in sems_df.iterrows()}

        with st.form("offering_form", clear_on_submit=True):
            o1, o2     = st.columns(2)
            off_course = o1.selectbox("Course *", list(course_map.keys()))
            off_lec    = o2.selectbox("Lecturer *", list(lec_list_map.keys()))
            off_sem    = o1.selectbox("Semester *", list(sem_map.keys()))
            off_year   = o2.text_input("Academic Year *", value="2025/2026",
                                       placeholder="e.g. 2025/2026")
            off_btn    = st.form_submit_button("🔗 Create Offering", type="primary", use_container_width=True)

        if off_btn:
            if not off_year.strip():
                st.error("Academic Year is required.")
            else:
                cid     = course_map[off_course]
                lid     = lec_list_map[off_lec]
                sid_val = sem_map[off_sem]
                nid     = _next_serial_id("CourseOffering", "CourseOfferingID")
                sql = f"""INSERT INTO CourseOffering
                          (CourseOfferingID, CourseID, LecturerID, SemesterID, AcademicYear)
                          VALUES ({nid}, {cid}, '{_esc(lid)}', {sid_val}, '{_esc(off_year.strip())}')"""
                try:
                    run_write(sql)
                    _ok(f"✅ Course offering created for **{off_course.split('-')[0].strip()}**.")
                except Exception as ex:
                    st.error(f"Error: {ex}")

        st.divider()
        st.markdown("**Existing course offerings:**")
        off_view = q("""SELECT co.CourseOfferingID, c.CourseCode, c.CourseTitle,
                               l.LecturerName, s.SemesterName, co.AcademicYear
                        FROM CourseOffering co
                        JOIN Course   c ON c.CourseID   = co.CourseID
                        JOIN Lecturer l ON l.LecturerID = co.LecturerID
                        JOIN Semester s ON s.SemesterID = co.SemesterID
                        ORDER BY co.CourseOfferingID""")
        st.dataframe(off_view, use_container_width=True, hide_index=True)


# ─────────────────────────────────────────────────────────────────────
# TAB 6 — PROGRAMMES
# ─────────────────────────────────────────────────────────────────────
with tab_prog:
    st.subheader("Programme Management")
    prog_sub1, prog_sub2 = st.tabs(["➕ Add Programme", "📋 View Programmes"])

    with prog_sub1:
        st.markdown("Add a new academic programme to a department.")
        depts_df2 = q("SELECT DepartmentID, DepartmentName FROM Department ORDER BY DepartmentName")
        dept_map2 = {r["DepartmentName"]: int(r["DepartmentID"]) for _, r in depts_df2.iterrows()}

        with st.form("add_prog_form", clear_on_submit=True):
            p1, p2        = st.columns(2)
            prog_dept     = p1.selectbox("Department *", list(dept_map2.keys()))
            prog_code     = p2.text_input("Programme Code *", placeholder="e.g. AI-MS")
            prog_name     = p1.text_input("Programme Name *", placeholder="e.g. MSc Artificial Intelligence")
            prog_degree   = p2.selectbox("Degree Type *", ["MSc", "MPhil", "BSc", "PhD", "Diploma"])
            prog_duration = st.number_input("Duration (years)", min_value=1, max_value=6, value=2, step=1)
            prog_btn      = st.form_submit_button("🎓 Add Programme", type="primary", use_container_width=True)

        if prog_btn:
            if not prog_code.strip() or not prog_name.strip():
                st.error("Programme Code and Name are required.")
            else:
                nid = _next_serial_id("Programme", "ProgrammeID")
                sql = f"""INSERT INTO Programme
                          (ProgrammeID, DepartmentID, ProgrammeCode, ProgrammeName, DegreeType, DurationYears)
                          VALUES ({nid}, {dept_map2[prog_dept]}, '{_esc(prog_code.strip())}',
                                  '{_esc(prog_name.strip())}', '{prog_degree}', {int(prog_duration)})"""
                try:
                    run_write(sql)
                    _ok(f"✅ Programme **{prog_name.strip()}** ({prog_code.strip()}) added!")
                except Exception as ex:
                    st.error("Duplicate programme code." if "UNIQUE" in str(ex).upper() else f"Error: {ex}")

    with prog_sub2:
        prog_view = q("""SELECT p.ProgrammeID, p.ProgrammeName, p.ProgrammeCode,
                                p.DegreeType, p.DurationYears, d.DepartmentName
                         FROM Programme p
                         JOIN Department d ON d.DepartmentID = p.DepartmentID
                         ORDER BY p.ProgrammeName""")
        st.caption(f"**{len(prog_view):,}** programme(s) on record")
        st.dataframe(prog_view, use_container_width=True, hide_index=True)
        st.download_button("⬇️ Download (.csv)", prog_view.to_csv(index=False).encode(),
                           "programmes.csv", "text/csv")
