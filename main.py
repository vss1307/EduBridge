import os
from flask import Flask, send_file, redirect, url_for

app = Flask(__name__, static_folder="src", static_url_path="")

@app.route("/")
def index():
    return send_file('src/index.html')

@app.route("/login")
def login():
    return send_file('src/login.html')

@app.route("/signup")
def signup():
    return send_file('src/signup.html')

@app.route("/get-started")
def get_started():
    # Redirect to the signup page
    return redirect(url_for('signup'))

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(debug=True, port=port)
