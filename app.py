from flask import Flask, render_template, request
import os
import requests
import psycopg2

DATABASE_URL = os.environ.get("DATABASE_URL")
app = Flask(__name__)


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
    return render_template("index.html", people=people)

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

    return render_template("index.html", message="Submission saved succesfully!")


@app.route("/view")
def view_entries():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()
    c.execute("SELECT name, description, amount, category, whatfor, date, image_filename FROM expenses ORDER BY date DESC")
    entries = c.fetchall()
    print(entries)
    conn.close()
    return render_template("view.html", entries=entries)


@app.route("/tesoreria")
def tesoreria():
    conn = psycopg2.connect(DATABASE_URL)
    c = conn.cursor()



if __name__ == "__main__":
    app.run(debug=True)
