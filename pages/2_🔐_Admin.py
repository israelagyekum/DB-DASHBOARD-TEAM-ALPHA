"""
Admin Backend  —  GADMS Student Management
==========================================
Allows authorised staff to add, view, and update students.
Changes are written to the same database the dashboard reads from,
so they take effect on the dashboard immediately (within 30 seconds,
or instantly on the next dashboard page load after a write).

Password: set ADMIN_PASSWORD in Streamlit secrets.
          Falls back to "gadms2026" if not configured.

DSCD 606 Data Management Techniques  |  University of Ghana
"""

import sys
from pathlib import Path
from datetime import date

import streamlit as st
import pandas as pd

# Make db.py importable (project root is one level above pages/)
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
  h1 { color: #1F3864; }
  h2, h3 { color: #2E75B6; }
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
    """Block the page until the correct admin password is entered."""
    if st.session_state.get("admin_auth"):
        return  # already authenticated this session

    st.title("🔐 GADMS Admin — Login")
    st.markdown("Enter the admin password to access student management.")
    pw_input = st.text_input("Password", type="password", key="pw_field")
    if st.button("Login", type="primary"):
        if pw_input == _get_admin_pw():
            st.session_state["admin_auth"] = True
            st.rerun()
        else:
            st.error("Incorrect password. Please try again.")
    st.stop()


_password_check()


# =====================================================================
# HELPERS
# =====================================================================
def _esc(s: str) -> str:
    """Escape single quotes for inline SQL strings."""
    return str(s).replace("'", "''")


def _next_student_id() -> str:
    """Auto-generate the next StudentID based on the current MAX."""
    try:
        max_df = q("SELECT MAX(StudentID) AS m FROM Student")
        max_id = str(max_df.iloc[0]["m"])
        if max_id and max_id.startswith("UG") and len(max_id) >= 9:
            year = max_id[2:6]
            num  = int(max_id[6:]) + 1
            return f"UG{year}{str(num).zfill(3)}"
    except Exception:
        pass
    return f"UG{date.today().year}101"


def _next_serial_id(table: str, id_col: str) -> int:
    """
    Return MAX(id_col) + 1 directly from the live connection (no cache).
    Used to supply explicit IDs when running on DuckDB, where identity
    sequences may not update automatically after bulk inserts.
    """
    _, conn = get_connection()
    row = conn.execute(
        f"SELECT COALESCE(MAX({id_col}), 0) + 1 AS nid FROM {table}"
    ).fetchone()
    return int(row[0])


# =====================================================================
# HEADER & CONNECTION STATUS
# =====================================================================
st.title("🔐 GADMS Admin Backend")
st.caption("DSCD 606 Data Management Techniques  •  University of Ghana")

_kind = get_connection()[0]
if _kind == "postgres":
    st.success(
        "🟢 **PostgreSQL (live)** — every change is permanently saved to the "
        "database and immediately visible on the dashboard."
    )
else:
    st.warning(
        "⚠️ **DuckDB (embedded mode)** — changes are saved in memory for this "
        "session and will reflect on the dashboard immediately. They reset when "
        "the app restarts. For permanent storage, add `DATABASE_URL` to your "
        "Streamlit secrets and load `TEAM_ALPHA.sql` into that database."
    )

if st.sidebar.button("🚪 Logout"):
    st.session_state["admin_auth"] = False
    st.rerun()

st.divider()

# =====================================================================
# TABS
# =====================================================================
tab_add, tab_manage, tab_enroll = st.tabs(
    ["➕ Add Student", "📋 Manage Students", "📚 Enrol in Course"]
)


# ─────────────────────────────────────────────────────────────────────
# TAB 1 — ADD STUDENT
# ─────────────────────────────────────────────────────────────────────
with tab_add:
    st.subheader("Add a New Student")
    st.markdown(
        "Fill in the details below. Required fields are marked \\*. "
        "The Student ID is auto-generated but you can change it."
    )

    # Programme dropdown populated live from the database
    programmes_df = q(
        "SELECT ProgrammeID, ProgrammeName, DegreeType FROM Programme ORDER BY ProgrammeName"
    )
    prog_map = {
        f"{row['ProgrammeName']} ({row['DegreeType']})": int(row["ProgrammeID"])
        for _, row in programmes_df.iterrows()
    }

    with st.form("add_student_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            student_id = st.text_input(
                "Student ID *",
                value=_next_student_id(),
                help="Auto-generated. Format: UGYYYYnnn",
            )
            first_name = st.text_input("First Name *")
            last_name  = st.text_input("Last Name *")
            email = st.text_input(
                "Email",
                placeholder="firstname.lastnameN@st.ug.edu.gh",
                help="Must be unique across all students.",
            )
            phone = st.text_input("Phone Number", placeholder="e.g. 0244123456")

        with col2:
            programme_label = st.selectbox("Programme *", list(prog_map.keys()))
            gender = st.selectbox("Gender", ["Male", "Female", "Other"])
            dob = st.date_input(
                "Date of Birth",
                value=date(2000, 1, 1),
                min_value=date(1950, 1, 1),
                max_value=date.today(),
            )
            admission_year = st.number_input(
                "Admission Year",
                min_value=2000, max_value=2100,
                value=date.today().year, step=1,
            )
            status = st.selectbox(
                "Status", ["Active", "Suspended", "Graduated", "Withdrawn"]
            )

        submitted = st.form_submit_button(
            "➕ Add Student", type="primary", use_container_width=True
        )

    if submitted:
        errors = []
        if not student_id.strip():
            errors.append("Student ID is required.")
        if not first_name.strip():
            errors.append("First Name is required.")
        if not last_name.strip():
            errors.append("Last Name is required.")

        if errors:
            for e in errors:
                st.error(e)
        else:
            prog_id   = prog_map[programme_label]
            dob_str   = dob.strftime("%Y-%m-%d")
            email_sql = f"'{_esc(email)}'" if email.strip() else "NULL"
            phone_sql = f"'{_esc(phone)}'" if phone.strip() else "NULL"

            insert_sql = f"""
                INSERT INTO Student
                  (StudentID, ProgrammeID, FirstName, LastName,
                   Gender, DateOfBirth, Email, PhoneNumber, AdmissionYear, Status)
                VALUES (
                  '{_esc(student_id.strip())}', {prog_id},
                  '{_esc(first_name.strip())}', '{_esc(last_name.strip())}',
                  '{gender}', '{dob_str}',
                  {email_sql}, {phone_sql},
                  {int(admission_year)}, '{status}'
                )
            """
            try:
                run_write(insert_sql)
                st.success(
                    f"✅ **{first_name.strip()} {last_name.strip()}** "
                    f"(ID: `{student_id.strip()}`) added successfully!"
                )
                st.info(
                    "Navigate to **📊 GADMS Analytics** in the sidebar — "
                    "the student count and charts have already updated."
                )
            except Exception as ex:
                err = str(ex)
                if "UNIQUE" in err.upper() or "unique" in err.lower():
                    st.error(
                        "A student with that ID or email already exists. "
                        "Please choose a different value."
                    )
                else:
                    st.error(f"Failed to add student: {ex}")


# ─────────────────────────────────────────────────────────────────────
# TAB 2 — MANAGE STUDENTS
# ─────────────────────────────────────────────────────────────────────
with tab_manage:
    st.subheader("All Students")

    col_search, col_filter = st.columns([3, 1])
    with col_search:
        search = st.text_input(
            "Search", placeholder="Name, ID, or email…",
            label_visibility="collapsed"
        )
    with col_filter:
        status_filter = st.selectbox(
            "Status", ["All", "Active", "Suspended", "Graduated", "Withdrawn"],
            label_visibility="collapsed",
        )

    students_df = q("""
        SELECT s.StudentID, s.FirstName, s.LastName,
               p.ProgrammeName, s.Gender, s.Status,
               s.Email, s.AdmissionYear
        FROM Student s
        JOIN Programme p ON p.ProgrammeID = s.ProgrammeID
        ORDER BY s.StudentID
    """)

    if search.strip():
        mask = (
            students_df["StudentID"].str.contains(search, case=False, na=False)
            | students_df["FirstName"].str.contains(search, case=False, na=False)
            | students_df["LastName"].str.contains(search, case=False, na=False)
            | students_df["Email"].str.contains(search, case=False, na=False)
        )
        students_df = students_df[mask]

    if status_filter != "All":
        students_df = students_df[students_df["Status"] == status_filter]

    st.caption(f"Showing **{len(students_df):,}** student(s)")
    st.dataframe(students_df, use_container_width=True, hide_index=True)

    st.download_button(
        "⬇️ Download student list (.csv)",
        data=students_df.to_csv(index=False).encode(),
        file_name="students_export.csv",
        mime="text/csv",
    )

    # ── Quick update form ──
    st.divider()
    st.subheader("Quick Update")

    with st.form("update_form"):
        u1, u2 = st.columns(2)
        with u1:
            sid_upd = st.text_input("Student ID", placeholder="e.g. UG2026001")
        with u2:
            field_upd = st.selectbox("Field to update", ["Status", "Programme"])

        if field_upd == "Status":
            new_val = st.selectbox(
                "New value", ["Active", "Suspended", "Graduated", "Withdrawn"]
            )
        else:
            prog_df2 = q(
                "SELECT ProgrammeID, ProgrammeName FROM Programme ORDER BY ProgrammeName"
            )
            prog_map2 = {
                row["ProgrammeName"]: int(row["ProgrammeID"])
                for _, row in prog_df2.iterrows()
            }
            new_val = st.selectbox("New programme", list(prog_map2.keys()))

        upd_btn = st.form_submit_button("✏️ Apply Update", type="primary")

    if upd_btn:
        if not sid_upd.strip():
            st.error("Enter a Student ID.")
        else:
            if field_upd == "Status":
                upd_sql = (
                    f"UPDATE Student SET Status = '{new_val}' "
                    f"WHERE StudentID = '{_esc(sid_upd.strip())}'"
                )
            else:
                upd_sql = (
                    f"UPDATE Student SET ProgrammeID = {prog_map2[new_val]} "
                    f"WHERE StudentID = '{_esc(sid_upd.strip())}'"
                )
            try:
                run_write(upd_sql)
                st.success(
                    f"✅ **{field_upd}** updated to **{new_val}** "
                    f"for student `{sid_upd.strip()}`."
                )
            except Exception as ex:
                st.error(f"Update failed: {ex}")


# ─────────────────────────────────────────────────────────────────────
# TAB 3 — ENROL IN COURSE
# ─────────────────────────────────────────────────────────────────────
with tab_enroll:
    st.subheader("Enrol a Student in a Course Offering")
    st.markdown(
        "Creates an Enrollment record. The enrollment appears in the Data "
        "Explorer and LMS tabs on the dashboard straight away."
    )

    offerings_df = q("""
        SELECT co.CourseOfferingID,
               c.CourseCode || ' — ' || c.CourseTitle AS CourseName,
               co.AcademicYear,
               l.LecturerName
        FROM CourseOffering co
        JOIN Course    c ON c.CourseID   = co.CourseID
        JOIN Lecturer  l ON l.LecturerID = co.LecturerID
        ORDER BY co.CourseOfferingID
    """)
    offering_map = {
        (
            f"[{row['CourseOfferingID']}] {row['CourseName']} "
            f"({row['AcademicYear']}) — {row['LecturerName']}"
        ): int(row["CourseOfferingID"])
        for _, row in offerings_df.iterrows()
    }

    with st.form("enroll_form"):
        e1, e2 = st.columns(2)
        with e1:
            enroll_sid = st.text_input(
                "Student ID *", placeholder="e.g. UG2026101"
            )
        with e2:
            offering_label = st.selectbox(
                "Course Offering *", list(offering_map.keys())
            )

        enroll_date   = st.date_input("Enrollment Date", value=date.today())
        enroll_status = st.selectbox(
            "Status", ["Active", "Completed", "Dropped", "Failed"]
        )
        enroll_btn = st.form_submit_button(
            "📚 Enrol Student", type="primary"
        )

    if enroll_btn:
        if not enroll_sid.strip():
            st.error("Student ID is required.")
        else:
            oid      = offering_map[offering_label]
            sid_safe = _esc(enroll_sid.strip())
            dt_str   = enroll_date.strftime("%Y-%m-%d")

            # On DuckDB, provide the EnrollmentID explicitly because the identity
            # sequence may not have been updated after bulk data loading.
            if is_postgres():
                enroll_sql = f"""
                    INSERT INTO Enrollment
                      (StudentID, CourseOfferingID, EnrollmentDate, EnrollmentStatus)
                    VALUES ('{sid_safe}', {oid}, '{dt_str}', '{enroll_status}')
                """
            else:
                next_eid = _next_serial_id("Enrollment", "EnrollmentID")
                enroll_sql = f"""
                    INSERT INTO Enrollment
                      (EnrollmentID, StudentID, CourseOfferingID, EnrollmentDate, EnrollmentStatus)
                    VALUES ({next_eid}, '{sid_safe}', {oid}, '{dt_str}', '{enroll_status}')
                """

            try:
                run_write(enroll_sql)
                course_short = offering_label.split("]")[1].split("(")[0].strip()
                st.success(
                    f"✅ Student `{enroll_sid.strip()}` enrolled in "
                    f"**{course_short}** successfully!"
                )
            except Exception as ex:
                err = str(ex)
                if "UNIQUE" in err.upper():
                    st.error(
                        "This student is already enrolled in that course offering."
                    )
                elif "FOREIGN KEY" in err.upper() or "violates foreign key" in err.lower():
                    st.error(
                        "Student ID not found. Please add the student first "
                        "using the **Add Student** tab."
                    )
                else:
                    st.error(f"Enrollment failed: {ex}")
