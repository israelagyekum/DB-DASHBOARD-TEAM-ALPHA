"""
db.py  —  Shared database utilities for GADMS Dashboard
Persistent DuckDB file — no external database required.
Uses hardcoded DuckDB-compatible DDL + INSERT-only loading from TEAM_ALPHA.sql.
"""
import re
from pathlib import Path
import pandas as pd
import streamlit as st

SQL_FILE = Path(__file__).parent / "TEAM_ALPHA.sql"
DB_FILE  = Path(__file__).parent / "gadms_v3.duckdb"

# DuckDB-compatible schema (no FK constraints, no CHECK constraints)
_DDL = """
CREATE TABLE IF NOT EXISTS Department (
    DepartmentID   INTEGER PRIMARY KEY,
    DepartmentName VARCHAR(100),
    Faculty        VARCHAR(100),
    OfficeLocation VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS Programme (
    ProgrammeID   INTEGER PRIMARY KEY,
    DepartmentID  INTEGER,
    ProgrammeCode VARCHAR(10),
    ProgrammeName VARCHAR(100),
    DegreeType    VARCHAR(50),
    DurationYears INTEGER
);
CREATE TABLE IF NOT EXISTS Course (
    CourseID     INTEGER PRIMARY KEY,
    DepartmentID INTEGER,
    CourseCode   VARCHAR(10),
    CourseTitle  VARCHAR(150),
    CreditHours  INTEGER
);
CREATE TABLE IF NOT EXISTS Lecturer (
    LecturerID   VARCHAR(15) PRIMARY KEY,
    DepartmentID INTEGER,
    LecturerName VARCHAR(100),
    Rank         VARCHAR(50),
    Email        VARCHAR(100)
);
CREATE TABLE IF NOT EXISTS Semester (
    SemesterID   INTEGER PRIMARY KEY,
    SemesterName VARCHAR(40),
    StartDate    DATE,
    EndDate      DATE
);
CREATE TABLE IF NOT EXISTS Student (
    StudentID     VARCHAR(15) PRIMARY KEY,
    ProgrammeID   INTEGER,
    FirstName     VARCHAR(50),
    LastName      VARCHAR(50),
    Gender        VARCHAR(10),
    DateOfBirth   DATE,
    Email         VARCHAR(100),
    PhoneNumber   VARCHAR(20),
    AdmissionYear INTEGER,
    Status        VARCHAR(20) DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS Admission (
    AdmissionID     INTEGER PRIMARY KEY,
    ProgrammeID     INTEGER,
    ApplicantName   VARCHAR(100),
    AdmissionDate   DATE,
    AdmissionStatus VARCHAR(30)
);
CREATE TABLE IF NOT EXISTS CourseOffering (
    CourseOfferingID INTEGER PRIMARY KEY,
    CourseID         INTEGER,
    LecturerID       VARCHAR(15),
    SemesterID       INTEGER,
    AcademicYear     VARCHAR(9)
);
CREATE TABLE IF NOT EXISTS Enrollment (
    EnrollmentID     INTEGER PRIMARY KEY,
    StudentID        VARCHAR(15),
    CourseOfferingID INTEGER,
    EnrollmentDate   DATE,
    EnrollmentStatus VARCHAR(20) DEFAULT 'Active'
);
CREATE TABLE IF NOT EXISTS AssessmentResult (
    ResultID        INTEGER PRIMARY KEY,
    EnrollmentID    INTEGER,
    CourseworkScore DECIMAL(5,2),
    ExamScore       DECIMAL(5,2),
    FinalGrade      VARCHAR(3)
);
CREATE TABLE IF NOT EXISTS FeePayment (
    PaymentID     INTEGER PRIMARY KEY,
    StudentID     VARCHAR(15),
    AmountPaid    DECIMAL(10,2),
    PaymentDate   DATE,
    PaymentMethod VARCHAR(30),
    Balance       DECIMAL(10,2)
);
CREATE TABLE IF NOT EXISTS LMSActivity (
    ActivityID       INTEGER PRIMARY KEY,
    StudentID        VARCHAR(15),
    CourseOfferingID INTEGER,
    LoginTimestamp   TIMESTAMP,
    ActivityType     VARCHAR(50),
    DurationMinutes  INTEGER
);
"""


@st.cache_resource(show_spinner="Loading GADMS database...")
def get_connection():
    import duckdb

    # Remove any old/corrupt DB files from previous attempts
    for old in Path(__file__).parent.glob("gadms*.duckdb"):
        if old.name != DB_FILE.name:
            try:
                old.unlink()
            except Exception:
                pass

    first_run = not DB_FILE.exists()
    con = duckdb.connect(str(DB_FILE))
    try:
        con.execute("SET preserve_identifier_case = false")
    except Exception:
        pass

    if first_run:
        _bootstrap(con)
    else:
        # Health check — rebuild if data is missing
        try:
            n = con.execute("SELECT COUNT(*) FROM Programme").fetchone()[0]
            if n == 0:
                raise Exception("empty")
        except Exception:
            con.close()
            try:
                DB_FILE.unlink()
            except Exception:
                pass
            con = duckdb.connect(str(DB_FILE))
            try:
                con.execute("SET preserve_identifier_case = false")
            except Exception:
                pass
            _bootstrap(con)

    return con


def _bootstrap(con):
    """Create schema and load data from TEAM_ALPHA.sql."""
    # 1. Create tables using clean DuckDB DDL
    for stmt in _DDL.strip().split(";"):
        stmt = stmt.strip()
        if stmt:
            try:
                con.execute(stmt)
            except Exception:
                pass

    # 2. Load only INSERT statements from the SQL file
    if not SQL_FILE.exists():
        st.error(f"SQL file not found: {SQL_FILE}")
        st.stop()

    raw = SQL_FILE.read_text()
    raw = re.sub(r"SELECT setval\([^;]*\);", "", raw)

    buff, stmts = [], []
    for line in raw.split("\n"):
        buff.append(line)
        if line.strip().endswith(";"):
            stmts.append("\n".join(buff))
            buff = []

    c = {"e": 0, "a": 0, "f": 0, "l": 0}
    for st_ in stmts:
        # Strip comment lines
        s = "\n".join(
            ln for ln in st_.split("\n")
            if not ln.strip().startswith("--")
        ).strip()
        # Only process INSERT statements
        if not s or not s.upper().startswith("INSERT"):
            continue
        # Inject serial IDs for tables without explicit PKs
        if s.startswith("INSERT INTO Enrollment "):
            c["e"] += 1
            s = s.replace("(StudentID,", "(EnrollmentID, StudentID,")
            s = s.replace(") VALUES (", f") VALUES ({c['e']}, ", 1)
        elif s.startswith("INSERT INTO AssessmentResult "):
            c["a"] += 1
            s = s.replace("(EnrollmentID,", "(ResultID, EnrollmentID,")
            s = s.replace(") VALUES (", f") VALUES ({c['a']}, ", 1)
        elif s.startswith("INSERT INTO FeePayment "):
            c["f"] += 1
            s = s.replace("(StudentID,", "(PaymentID, StudentID,")
            s = s.replace(") VALUES (", f") VALUES ({c['f']}, ", 1)
        elif s.startswith("INSERT INTO LMSActivity "):
            c["l"] += 1
            s = s.replace("(StudentID,", "(ActivityID, StudentID,")
            s = s.replace(") VALUES (", f") VALUES ({c['l']}, ", 1)
        try:
            con.execute(s)
        except Exception:
            pass


_COL_MAP: dict[str, str] = {
    'departmentid': 'DepartmentID',        'departmentname': 'DepartmentName',
    'faculty': 'Faculty',                   'officelocation': 'OfficeLocation',
    'programmeid': 'ProgrammeID',           'programmecode': 'ProgrammeCode',
    'programmename': 'ProgrammeName',       'degreetype': 'DegreeType',
    'durationyears': 'DurationYears',
    'courseid': 'CourseID',                 'coursecode': 'CourseCode',
    'coursetitle': 'CourseTitle',           'credithours': 'CreditHours',
    'lecturerid': 'LecturerID',             'lecturername': 'LecturerName',
    'rank': 'Rank',                         'email': 'Email',
    'semesterid': 'SemesterID',             'semestername': 'SemesterName',
    'startdate': 'StartDate',               'enddate': 'EndDate',
    'studentid': 'StudentID',               'firstname': 'FirstName',
    'lastname': 'LastName',                 'gender': 'Gender',
    'dateofbirth': 'DateOfBirth',           'phonenumber': 'PhoneNumber',
    'admissionyear': 'AdmissionYear',       'status': 'Status',
    'admissionid': 'AdmissionID',           'applicantname': 'ApplicantName',
    'admissiondate': 'AdmissionDate',       'admissionstatus': 'AdmissionStatus',
    'courseofferingid': 'CourseOfferingID', 'academicyear': 'AcademicYear',
    'enrollmentid': 'EnrollmentID',         'enrollmentdate': 'EnrollmentDate',
    'enrollmentstatus': 'EnrollmentStatus',
    'resultid': 'ResultID',                 'courseworkscore': 'CourseworkScore',
    'examscore': 'ExamScore',               'finalgrade': 'FinalGrade',
    'paymentid': 'PaymentID',               'amountpaid': 'AmountPaid',
    'paymentdate': 'PaymentDate',           'paymentmethod': 'PaymentMethod',
    'balance': 'Balance',
    'activityid': 'ActivityID',             'logintimestamp': 'LoginTimestamp',
    'activitytype': 'ActivityType',         'durationminutes': 'DurationMinutes',
    'students': 'Students',                 'enrollments': 'Enrollments',
    'results': 'Results',                   'events': 'Events',
    'minutes': 'Minutes',                   'total': 'Total',
    'payments': 'Payments',                 'paid': 'Paid',
    'outstanding': 'Outstanding',           'count': 'Count',
    'fullname': 'FullName',                 'coursename': 'CourseName',
    'grade': 'Grade',                       'avgmark': 'AvgMark',
    'totalpaid': 'TotalPaid',               'totalbalance': 'TotalBalance',
    'numpayments': 'NumPayments',           'numsections': 'NumSections',
    'n': 'n',                               'label': 'label',
    'studentname': 'StudentName',
}


def _fix_columns(df: pd.DataFrame) -> pd.DataFrame:
    df.columns = [_COL_MAP.get(c.lower(), c) for c in df.columns]
    return df


@st.cache_data(ttl=5, show_spinner=False)
def q(sql: str) -> pd.DataFrame:
    """Execute a read SQL query. Cached for 5 seconds."""
    con = get_connection()
    df = con.execute(sql).fetchdf()
    return _fix_columns(df)


def run_write(sql: str) -> None:
    """Execute a write (INSERT/UPDATE/DELETE). Clears cache immediately."""
    con = get_connection()
    con.execute(sql)
    q.clear()


def is_postgres() -> bool:
    return False
