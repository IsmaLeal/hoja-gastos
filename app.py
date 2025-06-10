from flask import Flask, render_template, request, redirect, session, url_for
import os
import re
import requests
import psycopg2
from dotenv import load_dotenv
from datetime import date, datetime

load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "fallback-dev-secret-key")

# Predefined allowed users
USERS = {
        "ivan gonzalez": "ivangsngonzalez669",
        "gonzalo pousa": "gonzalogsnpousa669",
        "ismael leal": "ismaelgsnleal669",
        "maria bravo": "mariagsnbravo669",
        "nuria gomez": "nuriagsngomez669",
        "lola damgaard": "lolagsndamgaard669",
        "cyntia fritz": "cyntiagsnfritz669",
        "sebastian gonzalez": "sebastiangsngonzalez669",
        "sara jimenez": "saragsnjimenez669",
        "irune de miguel": "irunegsndemiguel669",
        "pablo cabarcos": "pablogsncabarcos669",
        "eva gomez": "evagsngomez669",
        "miguel ruiz": "miguelgsnruiz669",
        "ruben garcia": "rubengsngarcia669",
        "ivan martin": "ivangsnmartin669",
        "laura diaz": "lauragsndiaz669",
        "alem": "alemgsn669",
        "luna miralles": "lunagsnmiralles669",
        "lucia alarcon": "luciagsnalarcon669",
        "gonzalo lara": "gonzalogsnlara669",
        "nora manzano": "noragsnmanzano669",
        "developer": "developer669"
    }

people = {
        "ivan gonzalez": "ES7114650100982050375582",
        "gonzalo pousa": "ES0921002904030262057029",
        "ismael leal": "ES6101821294110204237477",
        "maria bravo": "ES9630580990292762776683",
        "nuria gomez": "ES5621003414171300376682",
        "lola damgaard": "ES6701822566150201590657",
        "cyntia fritz": "ES0721001176131300462209",
        "sebastian gonzalez": "ES2721003322621300316258",
        "sara jimenez": "",
        "irune de miguel": "ES5221004587130200293195",
        "pablo cabarcos": "",
        "eva gomez": "ES4521002339310200362644",
        "miguel ruiz": "ES9630580990292762776683",
        "ruben garcia": "ES6700814197310001646570",
        "ivan martin": "ES7314650170191752597751",
        "laura diaz": "ES0514650170141761503626",
        "alem": "",
        "luna miralles": "ES1715632626393265677051",
        "lucia alarcon": "ES3901824030810201646259",
        "gonzalo lara": "ES2200730100520742787943",
        "nora manzano": "",
    }


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
    return render_template("index.html", people=people)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":            # After submitting the login
        username = request.form["username"] # Check username and password agree
        password = request.form["password"]
        if username in USERS and USERS[username] == password:
            session["user"] = username      # Store username in `session` and redirect
            return redirect(url_for("home"))
        else:
            return render_template("login.html", error="Oh Pepa!!\nCredenciales incorrectos")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.pop("user", None)
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

    return render_template("index.html", message="Submission saved succesfully!", people=people)

@app.route("/dates", methods=["GET", "POST"])
def dates():
    if session["user"] == "developer":
        if request.method == "POST":    # If "POST", return to the homepage and update the terms
            term1 = request.form["term1"]
            term2 = request.form["term2"]
            term3 = request.form["term3"]

            save_term_dates(term1, term2, term3, datetime.strptime(term1, "%Y-%m-%d").date().year)

            return render_template("index.html", people=people)
        else:   # If "GET", show `dates.html`
            return render_template("dates.html")
    else:
        return render_template("index.html", error="Oh Pepa!!\nNo la líes")



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
    entries = []
    total = 0
    selected_name = None
    term = None
    year = None

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
            return render_template("tesoreria.html", people=people, term=term, selected_name=selected_name, error="No term dates for that year.")

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
            return render_template("tesoreria.html", people=people, error=e)

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

        return render_template("tesoreria.html", people=people, entries=entries, selected_name=selected_name,
                               total=total, accounts_used=accounts_used, term=term)

    return render_template("tesoreria.html", people=people)


@app.route("/delete", methods=["POST"])
def delete_entry():
    entry_id = request.form["entry_id"]
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("DELETE FROM expenses WHERE id = %s", (entry_id,))
    conn.commit()
    conn.close()
    return redirect("/view")


if __name__ == "__main__":
    app.run(debug=True)
