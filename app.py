from flask import Flask, render_template
from controllers.auth_controller import auth_bp
import os

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "your_secret_key")

app.register_blueprint(auth_bp)

@app.route("/")
def home():
    return render_template("login.html")

@app.route("/register")
def register_page():
    return render_template("register.html")

@app.route("/login")
def login_page():
    return render_template("login.html")

@app.route("/write")
def write_page():
    return render_template("write.html")

@app.route("/browse")
def browse_page():
    return render_template("browse.html")

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=8080)
