# GADMS Analytics Dashboard

A live, interactive analytics dashboard for the **Governed Academic Data Management System (GADMS)** — built on top of the PostgreSQL implementation from DSCD 606 Data Management Techniques at the University of Ghana.

🎓 **What it shows**
Programme enrolment, performance and grade distribution, LMS engagement vs outcome (early-warning), fee governance, and a free-form SQL query lab.

🔐 **Admin backend**
A password-protected admin page lets staff add new students, update statuses, and enrol students in courses. Changes take effect on the dashboard immediately.

🛠️ **Stack**
Streamlit · Plotly · pandas · PostgreSQL (production) / DuckDB (embedded fallback)

---

## Two ways to run it

### 1. Local, zero-setup (uses embedded DuckDB)

```bash
git clone <your-repo-url>
cd gadms-dashboard
pip install -r requirements.txt
streamlit run app.py
```

The app auto-detects that no `DATABASE_URL` is configured and loads `TEAM_ALPHA.sql` into an in-memory DuckDB. Opens at <http://localhost:8501>.

> **Admin panel in local mode:** Students added via the admin panel are visible on the dashboard for the current session. They reset when you restart the app. For permanent storage, connect a PostgreSQL database.

### 2. Live database (PostgreSQL on Supabase, Render, Neon, or local)

Set a `DATABASE_URL` environment variable or paste it into `.streamlit/secrets.toml`:

```toml
DATABASE_URL = "postgresql://USER:PASSWORD@HOST:5432/DBNAME"
```

The app shows a green "Postgres (live)" badge. All admin changes are permanently saved.

---

## Deploy free in 15 minutes

The cheapest portfolio setup is **Supabase (free Postgres) + Streamlit Community Cloud (free hosting)**.

### Step 1 — Spin up a free Postgres on Supabase

1. Sign up at <https://supabase.com> → New Project. The free tier gives you a permanent Postgres database.
2. Open the **SQL Editor**, paste the contents of `TEAM_ALPHA.sql`, click Run. Your 12 tables and 1,019 records load in seconds.
3. Open **Project Settings → Database → Connection string → URI**. Copy it (looks like `postgresql://postgres:...@db.xxxxx.supabase.co:5432/postgres`).

### Step 2 — Push this folder to GitHub

```bash
git init
git add .
git commit -m "GADMS dashboard with admin backend"
gh repo create gadms-dashboard --public --source=. --push
```

(`.streamlit/secrets.toml` is gitignored — never committed.)

### Step 3 — Deploy to Streamlit Cloud

1. Visit <https://share.streamlit.io> → New app → pick your GitHub repo → main file `app.py`.
2. Click **Advanced settings → Secrets** and paste:
   ```toml
   DATABASE_URL = "postgresql://...your supabase URL..."
   ADMIN_PASSWORD = "your_secure_password"
   ```
3. Deploy. You get a public URL like `https://gadms-yourhandle.streamlit.app`.

---

## Admin Panel

Navigate to **🔐 Admin** in the sidebar. Default password is `gadms2026`.

To change it, add to Streamlit secrets (or `.streamlit/secrets.toml` locally):

```toml
ADMIN_PASSWORD = "your_secure_password"
```

### What the admin can do

| Feature | Description |
|---|---|
| **Add Student** | Form with all student fields. StudentID is auto-generated. |
| **Manage Students** | Search, filter, and browse the full student list. Export CSV. |
| **Quick Update** | Change a student's status or programme by entering their ID. |
| **Enrol in Course** | Assign a student to a course offering. |

Changes hit the database immediately and are visible on the dashboard within 30 seconds (or instantly on the next page navigation).

---

## Dashboard tour

| Tab | What it shows |
|---|---|
| **📊 Overview** | Students per programme, gender split, status distribution, programme × gender |
| **🎯 Performance** | Avg weighted mark per programme, grade distribution, coursework vs exam scatter |
| **💻 LMS Engagement** | Minutes vs events coloured by grade — surfaces high-effort/low-grade students |
| **💰 Finance** | Payment-method volumes, outstanding-balance worklist |
| **🗂️ Data Explorer** | Browse any of the 11 tables, download as CSV |
| **🧪 Query Lab** | Free-form read-only SQL for ad-hoc analysis |

Three sidebar filters (programme, status, gender) cascade through every chart.

---

## Project structure

```
gadms-dashboard/
├── app.py                 # Main dashboard (Streamlit + Plotly)
├── db.py                  # Shared DB connection & query utilities
├── pages/
│   └── 2_🔐_Admin.py     # Admin backend (add/edit students)
├── TEAM_ALPHA.sql         # Schema + 1,019 records (PostgreSQL DDL/DML)
├── requirements.txt
├── .streamlit/
│   ├── config.toml        # Theme + headless server settings
│   ├── secrets.toml       # (gitignored) DATABASE_URL + ADMIN_PASSWORD
│   └── secrets.toml.example
├── .gitignore
└── README.md
```

---

## Credits

Built by **Team Alpha** as a portfolio extension of the DSCD 606 mini project on the Governed Academic Data Management System.

University of Ghana · School of Physical and Mathematical Sciences · Department of Computer Science · MPhil Data Science · 2026
