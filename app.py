from flask import Flask, render_template, request, redirect, session, url_for
import os, re, requests, psycopg2
from dotenv import load_dotenv
from datetime import date, datetime
from functools import wraps

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-dev-secret-key")

# ---------- DB helpers ----------
def db_conn():
    return psycopg2.connect(DATABASE_URL)

def get_people_dict():
    """Return {name: iban} for all users (used by your form)."""
    with db_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT name, COALESCE(iban,'') FROM users ORDER BY lower(name)")
            rows = c.fetchall()
    return {name: iban for (name, iban) in rows}

def get_user_by_name(name):
    with db_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT id, name, password, role, iban FROM users WHERE lower(name)=lower(%s)", (name,))
            return c.fetchone()  # tuple or None

def is_developer():
    return session.get("user_role") == "developer"

def dev_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not is_developer():
            return render_template("index.html", error="Oh Pepa!!\nNo la líes", people=get_people_dict())
        return view(*args, **kwargs)
    return wrapper

def iban_group(value: str) -> str:
    """
    Insert a zero-width space every 4 characters
    so browsers can wrap IBANs neatly.
    """
    if not value:
        return ""
    return "&#8203;".join(value[i:i+4] for i in range(0, len(value), 4))

app.jinja_env.filters["iban_group"] = iban_group

def save_term_dates(term1, term2, term3, year):
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()

    # Avoid duplicates
    c.execute("DELETE FROM term_dates WHERE year = %s", (year,))
    c.execute("""
        INSERT INTO term_dates (year, term1, term2, term3)
        VALUES (%s, %s, %s, %s)
    """, (year, term1, term2, term3))

    conn.commit()
    conn.close()


def load_term_dates():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    current_year = date.today().year
    c.execute("""
        SELECT term1, term2, term3 FROM term_dates
        WHERE year = %s
    """, (current_year,))
    result = c.fetchone()
    conn.close()

    if result:
        term1, term2, term3 = result
        return {
            "term1": term1,
            "term2": term2,
            "term3": term3,
        }
    else:
        raise Exception("Terms not set for the current year.")


def upload_image_to_imgur(image_file):
    IMGUR_CLIENT_ID = os.environ.get("IMGUR_CLIENT_ID")
    headers = {"Authorization": f"Client-ID {IMGUR_CLIENT_ID}"}

    files = {"image": (image_file.filename, image_file.read())}

    response = requests.post("https://api.imgur.com/3/image", headers=headers, files=files)
    response_data = response.json()

    if response.status_code == 200 and response_data["success"]:
        return response_data["data"]["link"]
    else:
        raise Exception("Imgur upload failed: " + response_data.get("data", {}).get("error", "Unknown error"))


@app.route("/")
def home():
    print(f"Connected to: {DATABASE_URL}")
    return render_template("index.html", people=get_people_dict())

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":            # After submitting the login
        username = request.form["username"] # Check username and password agree
        password = request.form["password"]

        row = get_user_by_name(username)
        if row:
            _id, name, stored_pw, role, _iban = row
            if password == stored_pw:
                session["user"] = name      # Store username in `session` and redirect
                session["user_role"] = role
                return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Oh Pepa!!\nCredenciales incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
    session.pop("user_role", None)
    return redirect("/login")

@app.before_request
def require_login():
    allowed_routes = ["login", "static"]
    if "user" not in session and request.endpoint not in allowed_routes:
        return redirect(url_for("login"))

@app.route("/submit", methods=["POST"])
def submit():
    name = request.form["name"]
    account = request.form["account"]
    description = request.form["description"]
    amount = float(request.form["amount"])
    category = request.form["category"]
    whatfor = request.form["whatfor"]
    date = request.form["date"]

    # Handle image
    image = request.files.get("image")
    image_url = None
    if image and image.filename:
        image_url = upload_image_to_imgur(image)

    # Save to PostgreSQL
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("""
        INSERT INTO expenses (name, account, description, amount, category, whatfor, date, image_filename)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    """, (name, account, description, amount, category, whatfor, date, image_url))
    conn.commit()
    conn.close()

    return render_template("index.html", message="Submission saved succesfully!", people=get_people_dict())

@app.route("/dates", methods=["GET", "POST"])
def dates():
    if session["user_role"] == "developer":
        if request.method == "POST":    # If "POST", return to the homepage and update the terms
            term1 = request.form["term1"]
            term2 = request.form["term2"]
            term3 = request.form["term3"]

            save_term_dates(term1, term2, term3, datetime.strptime(term1, "%Y-%m-%d").date().year)

            return render_template("index.html", people=get_people_dict())
        else:   # If "GET", show `dates.html`
            return render_template("dates.html")
    else:
        return render_template("index.html", error="Oh Pepa!!\nNo la líes", people=get_people_dict())



@app.route("/view")
def view_entries():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("""
        SELECT name, description, amount, category, whatfor, date, image_filename, id
        FROM expenses
        ORDER BY date DESC
    """)
    entries = c.fetchall()
    conn.close()
    return render_template("view.html", entries=entries)


@app.route("/tesoreria", methods=["GET", "POST"])
def tesoreria():
    if request.method == "POST":
        selected_name = request.form.get("name")
        term = request.form.get("term")
        ronda = request.form.get("ronda")
        match = re.search(r"Ronda (\d{2})/\d{2}", ronda)
        if match:
            year_prefix = int(match.group(1))
            year = 2000 + year_prefix
        else:
            raise ValueError("Invalid Ronda number.")

        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("""
            SELECT term1, term2, term3 FROM term_dates WHERE year = %s
        """, (year,))
        result = c.fetchone()
        conn.close()

        if not result:
            return render_template("tesoreria.html", people=get_people_dict(),
                                   term=term, selected_name=selected_name, selected_ronda=ronda,
                                   error="No term dates for that year.")

        term1, term2, term3 = result
        term_starts = {
            "term1": term1,
            "term2": term2,
            "term3": term3
        }
        term_order = ["term1", "term2", "term3"]

        try:
            start_date = term_starts[term]
            next_index = term_order.index(term) + 1
            end_date = term_starts[term_order[next_index]] if next_index < len(term_order) else date(year + 1, 9, 1)
        except Exception as e:
            return render_template("tesoreria.html", people=get_people_dict(), error=e)

        conn = psycopg2.connect(DATABASE_URL)
        c = conn.cursor()
        c.execute("""
            SELECT date, account, amount, whatfor, image_filename
            FROM expenses
            WHERE LOWER(name) = LOWER(%s)
            AND date >= %s AND date < %s
            ORDER BY date DESC
        """, (selected_name, start_date, end_date))
        entries = c.fetchall()
        conn.close()

        accounts_used = set(entry[1] for entry in entries)
        total = sum(entry[2] for entry in entries if entry[2] is not None)

        return render_template("tesoreria.html", people=get_people_dict(), entries=entries, selected_name=selected_name,
                               total=total, accounts_used=accounts_used, term=term, selected_ronda=ronda)

    return render_template("tesoreria.html", people=get_people_dict())


@app.route("/delete", methods=["POST"])
def delete_entry():
    entry_id = request.form["entry_id"]
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = %s", (entry_id,))
    conn.commit()
    conn.close()
    return redirect("/view")


@app.route("/admin/users", methods=["GET", "POST"])
@dev_required
def admin_users():
    message = None
    error = None

    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "create":
                name = request.form["name"].strip()
                password = request.form["password"].strip()
                role = request.form.get("role", "user").strip() or "user"
                iban = request.form.get("iban", "").strip()

                # Basic IBAN hygiene (very light; we can harden later)
                if iban and not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{,30}", iban.replace(" ", "").upper()):
                    raise ValueError("IBAN con formato no válido.")

                with db_conn() as conn:
                    with conn.cursor() as c:
                        c.execute("""
                            INSERT INTO users (name, password, role, iban)
                            VALUES (%s, %s, %s, %s)
                        """, (name, password, role, iban))
                message = f"Usuario «{name}» creado."

            elif action == "update":
                uid = int(request.form["id"])
                name = request.form["name"].strip()
                password = request.form.get("password", "").strip()
                role = request.form.get("role", "user").strip() or "user"
                iban = request.form.get("iban", "").strip()

                if iban and not re.fullmatch(r"[A-Z]{2}\d{2}[A-Z0-9]{,30}", iban.replace(" ", "").upper()):
                    raise ValueError("IBAN con formato no válido.")

                with db_conn() as conn:
                    with conn.cursor() as c:
                        if password:
                            c.execute("""
                                UPDATE users SET name=%s, password=%s, role=%s, iban=%s
                                WHERE id=%s
                            """, (name, password, role, iban, uid))
                        else:
                            c.execute("""
                                UPDATE users SET name=%s, role=%s, iban=%s
                                WHERE id=%s
                            """, (name, role, iban, uid))
                message = f"Usuario «{name}» actualizado."

            elif action == "delete":
                uid = int(request.form["id"])
                with db_conn() as conn:
                    with conn.cursor() as c:
                        c.execute("DELETE FROM users WHERE id=%s", (uid,))
                message = "Usuario eliminado."

        except Exception as e:
            error = str(e)

    # Load list for display
    with db_conn() as conn:
        with conn.cursor() as c:
            c.execute("SELECT id, name, role, COALESCE(iban,'') FROM users ORDER BY lower(name)")
            users = c.fetchall()

    return render_template("admin_users.html",
                           users=users, message=message, error=error, people=get_people_dict())


if __name__ == "__main__":
    app.run(debug=True)
