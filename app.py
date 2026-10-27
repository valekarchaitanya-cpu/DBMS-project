

import os

from dotenv import load_dotenv

load_dotenv()

from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
from db import get_db_connection


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY")




@app.route("/")
def home():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status, client_id
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))
        account = cursor.fetchone()

        if not account or account["account_status"] != "active":
            session.clear()
            flash("Your account is inactive or unavailable.")
            return redirect(url_for("login"))

        role = account["role"]
        session["role"] = role

        total_cases = 0
        pending_cases = 0
        in_progress_cases = 0
        closed_cases = 0
        recent_cases = []
        my_cases = []

        if role == "admin":
            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM cases
            """)
            total_cases = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM cases
                WHERE status = 'Pending'
            """)
            pending_cases = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM cases
                WHERE status = 'In Progress'
            """)
            in_progress_cases = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT COUNT(*) AS total
                FROM cases
                WHERE status = 'Closed'
            """)
            closed_cases = cursor.fetchone()["total"]

            cursor.execute("""
                SELECT
                    c.case_id,
                    c.case_number,
                    c.title,
                    c.case_type,
                    c.status,
                    cl.full_name AS client_name,
                    l.full_name AS lawyer_name,
                    j.full_name AS judge_name,
                    h.hearing_date,
                    h.hearing_time,
                    h.court_room
                FROM cases c
                JOIN clients cl ON c.client_id = cl.client_id
                LEFT JOIN lawyers l ON c.lawyer_id = l.lawyer_id
                LEFT JOIN judges j ON c.judge_id = j.judge_id
                LEFT JOIN hearings h ON c.case_id = h.case_id
                ORDER BY c.case_id DESC
                LIMIT 8
            """)
            recent_cases = cursor.fetchall()

        elif role == "client":
            client_id = account["client_id"]

            if client_id is not None:
                cursor.execute("""
                    SELECT
                        c.case_id,
                        c.case_number,
                        c.title,
                        c.case_type,
                        c.status,
                        cl.full_name AS client_name,
                        l.full_name AS lawyer_name,
                        j.full_name AS judge_name,
                        h.hearing_date,
                        h.hearing_time,
                        h.court_room
                    FROM cases c
                    JOIN clients cl ON c.client_id = cl.client_id
                    LEFT JOIN lawyers l ON c.lawyer_id = l.lawyer_id
                    LEFT JOIN judges j ON c.judge_id = j.judge_id
                    LEFT JOIN hearings h ON c.case_id = h.case_id
                    WHERE c.client_id = %s
                    ORDER BY h.hearing_date IS NULL,
                             h.hearing_date, h.hearing_time
                """, (client_id,))
                my_cases = cursor.fetchall()

            recent_cases = my_cases
            total_cases = len(my_cases)
            pending_cases = sum(
                1 for case in my_cases
                if case["status"] == "Pending"
            )
            in_progress_cases = sum(
                1 for case in my_cases
                if case["status"] == "In Progress"
            )
            closed_cases = sum(
                1 for case in my_cases
                if case["status"] == "Closed"
            )

        else:
            flash("This dashboard is not configured for your account role.")
            return redirect(url_for("logout"))

        return render_template(
            "dashboard.html",
            total_cases=total_cases,
            pending_cases=pending_cases,
            in_progress_cases=in_progress_cases,
            closed_cases=closed_cases,
            recent_cases=recent_cases,
            my_cases=my_cases,
            role=role
        )

    finally:
        cursor.close()
        connection.close()


@app.route("/cases")
def cases_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        role = session.get("role")
        user_id = session["user_id"]

        base_query = """
            SELECT
                c.case_id,
                c.case_number,
                c.title,
                c.case_type,
                c.status,
                cl.full_name AS client_name,
                l.full_name AS lawyer_name,
                j.full_name AS judge_name
            FROM cases c
            JOIN clients cl ON c.client_id = cl.client_id
            LEFT JOIN lawyers l ON c.lawyer_id = l.lawyer_id
            LEFT JOIN judges j ON c.judge_id = j.judge_id
        """

        if role == "admin":
            cursor.execute(base_query + " ORDER BY c.case_id DESC")
        elif role == "client":
            cursor.execute("""
                SELECT c.case_id, c.case_number, c.title, c.case_type,
                       c.status, cl.full_name AS client_name,
                       l.full_name AS lawyer_name,
                       j.full_name AS judge_name
                FROM users u
                JOIN cases c ON c.client_id = u.client_id
                JOIN clients cl ON cl.client_id = c.client_id
                LEFT JOIN lawyers l ON l.lawyer_id = c.lawyer_id
                LEFT JOIN judges j ON j.judge_id = c.judge_id
                WHERE u.user_id = %s
                ORDER BY c.case_id DESC
            """, (user_id,))
        elif role == "lawyer":
            cursor.execute("""
                SELECT c.case_id, c.case_number, c.title, c.case_type,
                       c.status, cl.full_name AS client_name,
                       l.full_name AS lawyer_name,
                       j.full_name AS judge_name
                FROM users u
                JOIN cases c ON c.lawyer_id = u.lawyer_id
                JOIN clients cl ON cl.client_id = c.client_id
                LEFT JOIN lawyers l ON l.lawyer_id = c.lawyer_id
                LEFT JOIN judges j ON j.judge_id = c.judge_id
                WHERE u.user_id = %s
                ORDER BY c.case_id DESC
            """, (user_id,))
        elif role == "judge":
            cursor.execute("""
                SELECT c.case_id, c.case_number, c.title, c.case_type,
                       c.status, cl.full_name AS client_name,
                       l.full_name AS lawyer_name,
                       j.full_name AS judge_name
                FROM users u
                JOIN cases c ON c.judge_id = u.judge_id
                JOIN clients cl ON cl.client_id = c.client_id
                LEFT JOIN lawyers l ON l.lawyer_id = c.lawyer_id
                LEFT JOIN judges j ON j.judge_id = c.judge_id
                WHERE u.user_id = %s
                ORDER BY c.case_id DESC
            """, (user_id,))
        else:
            flash("You do not have permission to view cases.")
            cases = []
            return render_template("cases.html", cases=cases)

        cases = cursor.fetchall()
        return render_template("cases.html", cases=cases)

    finally:
        cursor.close()
        connection.close()


@app.route("/submit-case", methods=["GET", "POST"])
def submit_case():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "client":
        flash("Only client accounts can submit case applications.")
        return redirect(url_for("home"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT client_id
            FROM users
            WHERE user_id = %s
              AND role = 'client'
              AND account_status = 'active'
        """, (session["user_id"],))

        account = cursor.fetchone()

        if not account or account["client_id"] is None:
            flash("Your account is not linked to a client profile.")
            return redirect(url_for("home"))

        if request.method == "POST":
            application_title = request.form.get(
                "application_title", ""
            ).strip()
            case_type = request.form.get("case_type", "").strip()
            description = request.form.get("description", "").strip()

            allowed_types = {
                "Civil", "Criminal", "Family",
                "Property", "Consumer", "Other"
            }

            if (
                not application_title
                or len(application_title) > 200
                or case_type not in allowed_types
                or not description
                or len(description) > 5000
            ):
                flash("Please enter valid case application details.")
                return render_template("submit_case.html")

            cursor.execute("""
                INSERT INTO case_applications (
                    client_id,
                    application_title,
                    case_type,
                    description
                )
                VALUES (%s, %s, %s, %s)
            """, (
                account["client_id"],
                application_title,
                case_type,
                description
            ))

            connection.commit()
            flash("Your case application has been submitted successfully.")
            return redirect(url_for("my_applications"))

        return render_template("submit_case.html")

    finally:
        cursor.close()
        connection.close()


@app.route("/my-applications")
def my_applications():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "client":
        flash("This page is available to client accounts only.")
        return redirect(url_for("home"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT
                application_id,
                application_title,
                case_type,
                description,
                application_status,
                submitted_at,
                reviewed_at
            FROM case_applications
            WHERE client_id = (
                SELECT client_id
                FROM users
                WHERE user_id = %s
                  AND role = 'client'
                  AND account_status = 'active'
            )
            ORDER BY submitted_at DESC
        """, (session["user_id"],))

        applications = cursor.fetchall()

        return render_template(
            "my_applications.html",
            applications=applications
        )

    finally:
        cursor.close()
        connection.close()



@app.route("/admin/applications")
def admin_applications():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))

        account = cursor.fetchone()

        if (
            not account
            or account["role"] != "admin"
            or account["account_status"] != "active"
        ):
            flash("Only active administrators can review applications.")
            return redirect(url_for("home"))

        session["role"] = account["role"]

        cursor.execute("""
            SELECT
                a.application_id,
                a.application_title,
                a.case_type,
                a.description,
                a.application_status,
                a.submitted_at,
                cl.full_name AS client_name,
                cl.email AS client_email,
                cl.phone AS client_phone
            FROM case_applications a
            JOIN clients cl ON cl.client_id = a.client_id
            ORDER BY
                CASE
                    WHEN a.application_status = 'Pending' THEN 0
                    ELSE 1
                END,
                a.submitted_at DESC
        """)

        applications = cursor.fetchall()

        return render_template(
            "admin_applications.html",
            applications=applications
        )

    finally:
        cursor.close()
        connection.close()



@app.route("/admin/applications/<int:application_id>/review", methods=["POST"])
def review_application(application_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        # Verify the administrator directly against MySQL.
        cursor.execute("""
            SELECT role, account_status
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))

        account = cursor.fetchone()

        if (
            not account
            or account["role"] != "admin"
            or account["account_status"] != "active"
        ):
            flash("Only active administrators can review applications.")
            return redirect(url_for("home"))

        decision = request.form.get("decision", "").strip()

        if decision not in ("Approved", "Rejected"):
            flash("Invalid review decision.")
            return redirect(url_for("admin_applications"))

        # Lock the application while reviewing it.
        cursor.execute("""
            SELECT application_id, client_id, application_title,
                   case_type, description, application_status, case_id
            FROM case_applications
            WHERE application_id = %s
            FOR UPDATE
        """, (application_id,))

        application = cursor.fetchone()

        if not application:
            connection.rollback()
            flash("Application not found.")
            return redirect(url_for("admin_applications"))

        if application["application_status"] != "Pending":
            connection.rollback()
            flash("This application has already been reviewed.")
            return redirect(url_for("admin_applications"))

        if decision == "Rejected":
            cursor.execute("""
                UPDATE case_applications
                SET application_status = 'Rejected',
                    reviewed_at = CURRENT_TIMESTAMP,
                    reviewed_by = %s
                WHERE application_id = %s
                  AND application_status = 'Pending'
            """, (session["user_id"], application_id))

            connection.commit()
            flash("Application rejected.")
            return redirect(url_for("admin_applications"))

        # A lawyer is required by the current cases table.
        # Use the first existing lawyer as a temporary assignment;
        # the admin can change the assignment later.
        cursor.execute("""
            SELECT lawyer_id
            FROM lawyers
            ORDER BY lawyer_id
            LIMIT 1
        """)

        lawyer = cursor.fetchone()

        if not lawyer:
            connection.rollback()
            flash("No lawyer is available. Add a lawyer before approving.")
            return redirect(url_for("admin_applications"))

        # Create a unique official case number.
        case_number = f"CE-{application_id:06d}"

        cursor.execute("""
            SELECT case_id
            FROM cases
            WHERE case_number = %s
        """, (case_number,))

        if cursor.fetchone():
            connection.rollback()
            flash("This case number already exists. Please investigate before retrying.")
            return redirect(url_for("admin_applications"))

        cursor.execute("""
            INSERT INTO cases (
                case_number, title, case_type, client_id,
                lawyer_id, judge_id, filing_date, status, description
            )
            VALUES (%s, %s, %s, %s, %s, NULL, CURDATE(), 'Pending', %s)
        """, (
            case_number,
            application["application_title"],
            application["case_type"],
            application["client_id"],
            lawyer["lawyer_id"],
            application["description"]
        ))

        case_id = cursor.lastrowid

        cursor.execute("""
            UPDATE case_applications
            SET application_status = 'Approved',
                reviewed_at = CURRENT_TIMESTAMP,
                reviewed_by = %s,
                case_id = %s
            WHERE application_id = %s
              AND application_status = 'Pending'
        """, (session["user_id"], case_id, application_id))

        if cursor.rowcount != 1:
            connection.rollback()
            flash("The application could not be updated. No case was created.")
            return redirect(url_for("admin_applications"))

        connection.commit()
        flash(f"Application approved. Official case number: {case_number}")

        return redirect(url_for("admin_applications"))

    except Exception:
        connection.rollback()
        app.logger.exception("Application review failed")
        flash("The review could not be completed. Check the server log.")
        return redirect(url_for("admin_applications"))

    finally:
        cursor.close()
        connection.close()


@app.route("/clients")
def clients_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if session.get("role") == "admin":
            # Admin can view all clients.
            cursor.execute("""
                SELECT client_id, full_name, phone, email, address
                FROM clients
                ORDER BY client_id
            """)
            clients = cursor.fetchall()

        elif session.get("role") == "client":
            # Find the client record linked to this account.
            cursor.execute("""
                SELECT client_id
                FROM users
                WHERE user_id = %s
            """, (session["user_id"],))

            account = cursor.fetchone()

            if account and account["client_id"] is not None:
                cursor.execute("""
                    SELECT client_id, full_name, phone, email, address
                    FROM clients
                    WHERE client_id = %s
                """, (account["client_id"],))
                clients = cursor.fetchall()
            else:
                clients = []
                flash(
                    "Your account is not linked to a client profile yet."
                )

        else:
            flash("You do not have permission to view client records.")
            clients = []

        return render_template("clients.html", clients=clients)

    finally:
        cursor.close()
        connection.close()




@app.route("/lawyers")
def lawyers_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        if session.get("role") == "admin":
            cursor.execute("""
                SELECT lawyer_id, full_name, phone, email, specialization
                FROM lawyers
                ORDER BY lawyer_id
            """)
            lawyers = cursor.fetchall()

        elif session.get("role") == "client":
            cursor.execute("""
                SELECT DISTINCT
                    l.lawyer_id, l.full_name, l.phone,
                    l.email, l.specialization
                FROM users u
                JOIN cases c ON c.client_id = u.client_id
                JOIN lawyers l ON l.lawyer_id = c.lawyer_id
                WHERE u.user_id = %s
                ORDER BY l.full_name
            """, (session["user_id"],))
            lawyers = cursor.fetchall()

        else:
            flash("You do not have permission to view this directory.")
            lawyers = []

        return render_template("lawyers.html", lawyers=lawyers)

    finally:
        cursor.close()
        connection.close()



@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        full_name = request.form.get("full_name", "").strip()
        email = request.form.get("email", "").strip()
        phone = request.form.get("phone", "").strip()

        if not full_name or not email or not phone:
            flash("Please fill in your name, email, and phone.")
            return redirect(url_for("register"))

        if len(username) < 3 or len(username) > 50:
            flash("Username must be between 3 and 50 characters.")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.")
            return redirect(url_for("register"))

        connection = get_db_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "SELECT user_id FROM users WHERE username = %s",
                (username,)
            )

            if cursor.fetchone():
                flash("That username is already taken.")
                return redirect(url_for("register"))

            
            password_hash = generate_password_hash(password)

            # Create the login account first
            cursor.execute("""
                INSERT INTO users (username, password_hash, role, account_status)
                VALUES (%s, %s, %s, %s)
            """, (username, password_hash, "client", "active"))

            user_id = cursor.lastrowid

            # Create the corresponding client profile
            cursor.execute("""
                INSERT INTO clients (full_name, email, phone, address)
                VALUES (%s, %s, %s, %s)
            """, (full_name, email, phone, ""))

            client_id = cursor.lastrowid

            # Link the client profile to the login account
            cursor.execute("""
                UPDATE users
                SET client_id = %s
                WHERE user_id = %s
            """, (client_id, user_id))

            connection.commit()


            flash("Account created successfully! You can now log in.")
            return redirect(url_for("login"))

        except Exception:
            connection.rollback()
            flash("Unable to create your account. Please try again.")

        finally:
            cursor.close()
            connection.close()

        return redirect(url_for("register"))

    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        connection = get_db_connection()
        cursor = connection.cursor(dictionary=True)

        try:
            cursor.execute(
                """
                SELECT user_id, username, password_hash, role, account_status
                FROM users
                WHERE username = %s
                """,
                (username,)
            )

            user = cursor.fetchone()

            if (
                user
                and check_password_hash(user["password_hash"], password)
                and user["account_status"] == "active"
            ):
                session.clear()
                session["user_id"] = user["user_id"]
                session["username"] = user["username"]
                session["role"] = user["role"]

                flash("Login successful!")
                return redirect(url_for("home"))

            flash("Invalid username or password, or your account is disabled.")

        finally:
            cursor.close()
            connection.close()

    return render_template("login.html")


        

@app.route("/hearings")
def hearings_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        role = session.get("role")
        user_id = session["user_id"]

        query = """
            SELECT
                h.hearing_id,
                h.hearing_date,
                h.hearing_time,
                h.court_room,
                h.remarks,
                c.case_number,
                c.title AS case_title,
                c.status AS case_status,
                j.full_name AS judge_name,
                l.full_name AS lawyer_name
            FROM hearings h
            JOIN cases c ON h.case_id = c.case_id
            LEFT JOIN judges j ON c.judge_id = j.judge_id
            LEFT JOIN lawyers l ON c.lawyer_id = l.lawyer_id
        """

        if role == "admin":
            cursor.execute(query + """
                ORDER BY h.hearing_date, h.hearing_time
            """)

        elif role == "client":
            cursor.execute(query + """
                JOIN users u ON u.client_id = c.client_id
                WHERE u.user_id = %s
                ORDER BY h.hearing_date, h.hearing_time
            """, (user_id,))

        elif role == "lawyer":
            cursor.execute(query + """
                JOIN users u ON u.lawyer_id = c.lawyer_id
                WHERE u.user_id = %s
                ORDER BY h.hearing_date, h.hearing_time
            """, (user_id,))

        elif role == "judge":
            cursor.execute(query + """
                JOIN users u ON u.judge_id = c.judge_id
                WHERE u.user_id = %s
                ORDER BY h.hearing_date, h.hearing_time
            """, (user_id,))

        else:
            flash("You do not have permission to view hearings.")
            hearings = []
            return render_template("hearings.html", hearings=hearings)

        hearings = cursor.fetchall()

        return render_template("hearings.html", hearings=hearings)

    finally:
        cursor.close()
        connection.close()



@app.route("/judges")
def judges_page():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        role = session.get("role")
        user_id = session["user_id"]

        if role == "admin":
            cursor.execute("""
                SELECT judge_id, full_name, court_name, designation
                FROM judges
                ORDER BY judge_id
            """)

        elif role == "client":
            cursor.execute("""
                SELECT DISTINCT
                    j.judge_id, j.full_name, j.court_name, j.designation
                FROM users u
                JOIN cases c ON c.client_id = u.client_id
                JOIN judges j ON j.judge_id = c.judge_id
                WHERE u.user_id = %s
                ORDER BY j.full_name
            """, (user_id,))

        elif role == "lawyer":
            cursor.execute("""
                SELECT DISTINCT
                    j.judge_id, j.full_name, j.court_name, j.designation
                FROM users u
                JOIN cases c ON c.lawyer_id = u.lawyer_id
                JOIN judges j ON j.judge_id = c.judge_id
                WHERE u.user_id = %s
                ORDER BY j.full_name
            """, (user_id,))

        elif role == "judge":
            cursor.execute("""
                SELECT j.judge_id, j.full_name, j.court_name, j.designation
                FROM users u
                JOIN judges j ON j.judge_id = u.judge_id
                WHERE u.user_id = %s
                ORDER BY j.full_name
            """, (user_id,))

        else:
            flash("You do not have permission to view judges.")
            judges = []
            return render_template("judges.html", judges=judges)

        judges = cursor.fetchall()

        return render_template("judges.html", judges=judges)

    finally:
        cursor.close()
        connection.close()


@app.route("/logout")
def logout():
    session.clear()
    flash("You have been logged out successfully.")
    return redirect(url_for("login"))




@app.route("/test-audit")
def test_audit():
    if "user_id" not in session:
        return redirect(url_for("login"))

    if session.get("role") != "admin":
        return "Admin access required.", 403

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT case_id, case_number, status
            FROM cases
            WHERE case_id = 12
        """)
        case = cursor.fetchone()

        if not case:
            return "Test case not found.", 404

        cursor.execute("""
            SELECT audit_id, case_id, field_name,
                   old_value, new_value, changed_at
            FROM case_audit_log
            WHERE case_id = 12
            ORDER BY audit_id DESC
        """)
        logs = cursor.fetchall()

        return render_template(
            "test_audit.html",
            case=case,
            logs=logs
        )

    finally:
        cursor.close()
        connection.close()



@app.route("/admin/case-management/<int:case_id>/update", methods=["POST"])
def update_case_management(case_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))
        account = cursor.fetchone()

        if (
            not account
            or account["role"] != "admin"
            or account["account_status"] != "active"
        ):
            return "Access denied. Active admin account required.", 403

        lawyer_id = request.form.get("lawyer_id", type=int)
        judge_value = request.form.get("judge_id", "").strip()
        judge_id = int(judge_value) if judge_value else None
        status = request.form.get("status", "").strip()

        court_room = request.form.get("court_room", "").strip()
        hearing_date = request.form.get("hearing_date", "").strip()
        hearing_time = request.form.get("hearing_time", "").strip()

        if status not in {"Pending", "In Progress", "Closed"}:
            flash("Invalid case status.")
            return redirect(url_for("admin_case_management"))

        if not court_room or len(court_room) > 50:
            flash("Enter a valid courtroom name or number.")
            return redirect(url_for("admin_case_management"))

        if bool(hearing_date) != bool(hearing_time):
            flash("Enter both the hearing date and time.")
            return redirect(url_for("admin_case_management"))

        cursor.execute(
            "SELECT case_id FROM cases WHERE case_id = %s",
            (case_id,)
        )
        if not cursor.fetchone():
            flash("Case not found.")
            return redirect(url_for("admin_case_management"))

        cursor.execute(
            "SELECT lawyer_id FROM lawyers WHERE lawyer_id = %s",
            (lawyer_id,)
        )
        if not cursor.fetchone():
            flash("Select a valid lawyer.")
            return redirect(url_for("admin_case_management"))

        if judge_id is not None:
            cursor.execute(
                "SELECT judge_id FROM judges WHERE judge_id = %s",
                (judge_id,)
            )
            if not cursor.fetchone():
                flash("Select a valid judge.")
                return redirect(url_for("admin_case_management"))

        # Identify the administrator for the MySQL audit trigger.
        cursor.execute(
            "SET @courtease_user_id = %s",
            (session["user_id"],)
        )

        cursor.execute("""
            UPDATE cases
            SET lawyer_id = %s,
                judge_id = %s,
                status = %s
            WHERE case_id = %s
        """, (lawyer_id, judge_id, status, case_id))

        # Update the existing hearing, or create one if needed.
        cursor.execute("""
            SELECT hearing_id
            FROM hearings
            WHERE case_id = %s
            ORDER BY hearing_date DESC, hearing_time DESC
            LIMIT 1
            FOR UPDATE
        """, (case_id,))
        hearing = cursor.fetchone()

        if hearing_date and hearing_time:
            if hearing:
                cursor.execute("""
                    UPDATE hearings
                    SET hearing_date = %s,
                        hearing_time = %s,
                        court_room = %s
                    WHERE hearing_id = %s
                """, (
                    hearing_date,
                    hearing_time,
                    court_room,
                    hearing["hearing_id"]
                ))
            else:
                cursor.execute("""
                    INSERT INTO hearings (
                        case_id, hearing_date, hearing_time, court_room
                    )
                    VALUES (%s, %s, %s, %s)
                """, (
                    case_id, hearing_date, hearing_time, court_room
                ))
        elif hearing:
            cursor.execute("""
                UPDATE hearings
                SET court_room = %s
                WHERE hearing_id = %s
            """, (court_room, hearing["hearing_id"]))
        else:
            connection.rollback()
            flash("Enter a hearing date and time to allocate a courtroom.")
            return redirect(url_for("admin_case_management"))

        connection.commit()
        flash("Case assignments, status and hearing details saved.")

    except Exception:
        connection.rollback()
        app.logger.exception("Case management update failed")
        flash("Unable to update the case. Check the Flask terminal.")

    finally:
        cursor.close()
        connection.close()

    return redirect(url_for("admin_case_management"))


    



@app.route("/admin/case-management")
def admin_case_management():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))
        account = cursor.fetchone()

        if (
            not account
            or account["role"] != "admin"
            or account["account_status"] != "active"
        ):
            return "Access denied. Active admin account required.", 403

        cursor.execute("""
            SELECT
                c.case_id,
                c.case_number,
                c.title,
                c.case_type,
                c.status,
                cl.full_name AS client_name,
                c.lawyer_id,
                l.full_name AS lawyer_name,
                c.judge_id,
                j.full_name AS judge_name
            FROM cases c
            JOIN clients cl ON cl.client_id = c.client_id
            LEFT JOIN lawyers l ON l.lawyer_id = c.lawyer_id
            LEFT JOIN judges j ON j.judge_id = c.judge_id
            ORDER BY c.case_id DESC
        """)
        cases = cursor.fetchall()

        cursor.execute("""
            SELECT lawyer_id, full_name
            FROM lawyers
            ORDER BY full_name
        """)
        lawyers = cursor.fetchall()

        cursor.execute("""
            SELECT judge_id, full_name, court_name, designation
            FROM judges
            ORDER BY full_name
        """)
        judges = cursor.fetchall()

        cursor.execute("""
            SELECT
                hearing_id,
                case_id,
                hearing_date,
                hearing_time,
                court_room,
                remarks
            FROM hearings
            ORDER BY hearing_date, hearing_time
        """)
        hearings = cursor.fetchall()

        return render_template(
            "admin_case_management.html",
            cases=cases,
            lawyers=lawyers,
            judges=judges,
            hearings=hearings
        )

    finally:
        cursor.close()
        connection.close()

        
@app.route("/case-history/<int:case_id>")
def case_history(case_id):
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status, client_id
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))
        account = cursor.fetchone()

        if not account or account["account_status"] != "active":
            return "Access denied.", 403

        if account["role"] not in ("admin", "client"):
            return "Access denied.", 403

        cursor.execute("""
            SELECT
                c.case_id,
                c.case_number,
                c.title,
                c.case_type,
                c.status,
                c.client_id,
                cl.full_name AS client_name,
                l.full_name AS lawyer_name,
                j.full_name AS judge_name
            FROM cases c
            JOIN clients cl ON cl.client_id = c.client_id
            LEFT JOIN lawyers l ON l.lawyer_id = c.lawyer_id
            LEFT JOIN judges j ON j.judge_id = c.judge_id
            WHERE c.case_id = %s
        """, (case_id,))
        case = cursor.fetchone()

        if not case:
            return "Case not found.", 404

        # Clients may view only their own cases.
        if (
            account["role"] == "client"
            and account["client_id"] != case["client_id"]
        ):
            return "You cannot access this case.", 403

        cursor.execute("""
            SELECT
                a.audit_id,
                a.field_name,
                a.old_value,
                a.new_value,
                a.changed_at,
                u.username AS changed_by_name
            FROM case_audit_log a
            LEFT JOIN users u ON u.user_id = a.changed_by
            WHERE a.case_id = %s
            ORDER BY a.changed_at DESC, a.audit_id DESC
        """, (case_id,))
        history = cursor.fetchall()

        cursor.execute("""
            SELECT
                hearing_date,
                hearing_time,
                court_room,
                remarks
            FROM hearings
            WHERE case_id = %s
            ORDER BY hearing_date DESC, hearing_time DESC
        """, (case_id,))
        hearings = cursor.fetchall()

        return render_template(
            "case_history.html",
            case=case,
            history=history,
            hearings=hearings,
            role=account["role"]
        )

    finally:
        cursor.close()
        connection.close()

        

@app.route("/admin/add-lawyer", methods=["GET", "POST"])
def add_lawyer():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))
        account = cursor.fetchone()

        if (not account or account["role"] != "admin"
                or account["account_status"] != "active"):
            return "Access denied.", 403

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            phone = request.form.get("phone", "").strip() or None
            email = request.form.get("email", "").strip() or None
            specialization = request.form.get(
                "specialization", ""
            ).strip() or None

            if not full_name or len(full_name) > 100:
                flash("Enter a valid lawyer name.")
                return redirect(url_for("add_lawyer"))

            if phone and len(phone) > 20:
                flash("Phone number must be at most 20 characters.")
                return redirect(url_for("add_lawyer"))

            if email and len(email) > 100:
                flash("Email must be at most 100 characters.")
                return redirect(url_for("add_lawyer"))

            if specialization and len(specialization) > 100:
                flash("Specialization must be at most 100 characters.")
                return redirect(url_for("add_lawyer"))

            cursor.execute("""
                INSERT INTO lawyers
                    (full_name, phone, email, specialization)
                VALUES (%s, %s, %s, %s)
            """, (full_name, phone, email, specialization))

            connection.commit()
            flash("Lawyer added successfully!")
            return redirect(url_for("add_lawyer"))

        cursor.execute("""
            SELECT lawyer_id, full_name, phone, email, specialization
            FROM lawyers
            ORDER BY lawyer_id DESC
        """)
        lawyers = cursor.fetchall()

        return render_template("add_lawyer.html", lawyers=lawyers)

    except Exception:
        connection.rollback()
        app.logger.exception("Add lawyer failed")
        flash("Unable to save lawyer. Check the Flask terminal.")
        return redirect(url_for("add_lawyer"))

    finally:
        cursor.close()
        connection.close()


@app.route("/admin/add-judge", methods=["GET", "POST"])
def add_judge():
    if "user_id" not in session:
        return redirect(url_for("login"))

    connection = get_db_connection()
    cursor = connection.cursor(dictionary=True)

    try:
        cursor.execute("""
            SELECT role, account_status
            FROM users
            WHERE user_id = %s
        """, (session["user_id"],))
        account = cursor.fetchone()

        if (not account or account["role"] != "admin"
                or account["account_status"] != "active"):
            return "Access denied.", 403

        if request.method == "POST":
            full_name = request.form.get("full_name", "").strip()
            court_name = request.form.get("court_name", "").strip()
            designation = request.form.get(
                "designation", ""
            ).strip() or None

            if not full_name or len(full_name) > 100:
                flash("Enter a valid judge name.")
                return redirect(url_for("add_judge"))

            if not court_name or len(court_name) > 150:
                flash("Enter a valid court name.")
                return redirect(url_for("add_judge"))

            if designation and len(designation) > 100:
                flash("Designation must be at most 100 characters.")
                return redirect(url_for("add_judge"))

            cursor.execute("""
                INSERT INTO judges
                    (full_name, court_name, designation)
                VALUES (%s, %s, %s)
            """, (full_name, court_name, designation))

            connection.commit()
            flash("Judge added successfully!")
            return redirect(url_for("add_judge"))

        cursor.execute("""
            SELECT judge_id, full_name, court_name, designation
            FROM judges
            ORDER BY judge_id DESC
        """)
        judges = cursor.fetchall()

        return render_template("add_judge.html", judges=judges)

    except Exception:
        connection.rollback()
        app.logger.exception("Add judge failed")
        flash("Unable to save judge. Check the Flask terminal.")
        return redirect(url_for("add_judge"))

    finally:
        cursor.close()
        connection.close()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)