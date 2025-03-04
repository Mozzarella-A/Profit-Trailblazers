from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash
from models.user_model import User

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        data = request.form
        username = data.get("username")
        email = data.get("email")
        password = data.get("password")
        confirm_password = data.get("confirm_password")
        role = data.get("account_type")
        class_code = data.get("class_code") if role == "student" else None

        print(f"Received registration data: {data}")  # Debugging

        # Check if email already exists
        if User.find_by_email(email):
            flash("User already exists!", "error")
            return redirect(url_for("auth.register"))

        # Check if passwords match
        if password != confirm_password:
            flash("Passwords do not match!", "error")
            return redirect(url_for("auth.register"))

        # Try to create the user
        try:
            created_user = User.create_user(username, email, password, role, class_code)
            if created_user:
                print("User successfully created!")
                flash("Account created! Please log in.", "success")
                return redirect(url_for("auth.login"))
            else:
                print("User creation failed in database")
                flash("Registration failed. Try again!", "error")
                return redirect(url_for("auth.register"))
        except Exception as e:
            print(f"Unexpected error in registration: {e}")
            flash("An error occurred. Try again!", "error")
            return redirect(url_for("auth.register"))

    return render_template("register.html")


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        data = request.form
        email = data.get("email")
        password = data.get("password")

        print(f"Login attempt: {email}")  # Debugging

        user = User.verify_user(email, password)
        if user:
            print("Login successful!")
            flash("Login successful!", "success")
            return redirect(url_for("write_page"))  # Redirect to write.html

        print("Invalid credentials")
        flash("Incorrect email or password!", "error")  # Flash message for incorrect login
        return redirect(url_for("auth.login"))

    return render_template("login.html")
