import bcrypt
from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from models.user_model import User
import uuid
from datetime import datetime, timedelta
from db import get_db_cursor, log_action
from flask_mail import Mail, Message

auth_bp = Blueprint("auth", __name__)

# Pass the mail instance when registering the blueprint (handled in app.py)
def init_auth(mail_instance):
    global mail
    mail = mail_instance  # Assign the mail instance globally within this module

    @auth_bp.route("/register", methods=["GET", "POST"])
    def register():
        if request.method == "POST":
            data = request.form
            username = data.get("username")
            email = data.get("email")
            password = data.get("password")
            confirm_password = data.get("confirm_password")
            role = data.get("account_type", "teacher")
            class_code = data.get("class_code") if role == "student" else None

            print(f"Received registration data: {data}")
            print(f"Checking if email {email} exists...")

            existing_user = User.find_by_email(email)
            print(f"Email check result: {existing_user}")
            if existing_user:
                flash("User already exists!", "error")
                return redirect(url_for("auth.register"))

            if password != confirm_password:
                flash("Passwords do not match!", "error")
                return redirect(url_for("auth.register"))

            try:
                print(f"Attempting to create user: {username}, {email}, role: {role}, class_code: {class_code}")
                token = User.create_user(username, email, password, role, class_code)
                print(f"User creation returned token: {token}")
                if token:
                    print("User creation successful, preparing verification email...")
                    verification_url = url_for('auth.verify_email', token=token, _external=True)
                    # Temporarily disable email sending due to Codio limitations
                    # msg = Message("Verify Your Komodo HUB Account", recipients=[email])
                    # msg.body = f"Please click the following link to verify your account: {verification_url}"
                    # mail.send(msg)
                    print(f"Verification link for {email}: {verification_url}")
                    flash("A verification email would have been sent! Check the terminal for the verification link.", "success")
                    print("Redirecting to login page...")
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
            identifier = data.get("email_or_code")  # Can be email or access code
            password = data.get("password")

            print(f"Login attempt: {identifier}")

            # Try to find user by email or access code
            user_by_email = User.find_by_email(identifier) if '@' in identifier else None
            print(f"User by email: {user_by_email}")  # Debug print
            user_by_code = User.find_by_access_code(identifier) if not '@' in identifier else None
            print(f"User by code: {user_by_code}")  # Debug print
            user = user_by_email or user_by_code
            print(f"Selected user: {user}")  # Debug print

            if not user:
                print("User not found")
                log_action(None, "login_failed", f"Failed login attempt for {identifier}")
                flash("Invalid email, access code, or password!", "error")
                return redirect(url_for("auth.login"))

            if not user["is_verified"]:
                flash("Please verify your account via the email link before logging in.", "error")
                return redirect(url_for("auth.login"))

            print(f"Checking password for user {user['username']}: {password}")
            if not bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
                print("Invalid credentials")
                log_action(None, "login_failed", f"Failed login attempt for {identifier}")
                flash("Invalid email, access code, or password!", "error")
                return redirect(url_for("auth.login"))

            token = str(uuid.uuid4())
            expires_at = datetime.now() + timedelta(minutes=15)
            connection, cursor = get_db_cursor()
            try:
                cursor.execute("""
                    INSERT INTO verification_tokens (user_id, token, purpose, expires_at)
                    VALUES (%s, %s, %s, %s)
                """, (user["id"], token, 'login', expires_at))
                connection.commit()
                
                verification_url = url_for('auth.verify_login', token=token, _external=True)
                # Temporarily disable email sending due to Codio limitations
                # msg = Message("Verify Your Komodo HUB Login", recipients=[user["email"]])
                # msg.body = f"Please click the following link to verify your login: {verification_url}"
                # mail.send(msg)
                print(f"Login verification link for {user['email']}: {verification_url}")
                flash("A login verification email would have been sent! Check the terminal for the verification link.", "success")
                session['pending_login_user_id'] = user["id"]
                log_action(user["id"], "login_verification_sent", f"Verification link sent for user {user['id']}")
                return redirect(url_for("auth.login"))
            except Exception as e:
                connection.rollback()
                print(f"Error sending login verification email: {e}")
                flash("An error occurred. Please try again.", "error")
                return redirect(url_for("auth.login"))
            finally:
                cursor.close()
                connection.close()

        return render_template("login.html")

    @auth_bp.route("/verify/<token>")
    def verify_email(token):
        user = User.verify_token(token, 'registration')
        if user:
            User.mark_as_verified(user['id'])
            flash("Account verified successfully! You can now log in.", "success")
            log_action(user['id'], "email_verified", f"User {user['id']} verified email")
            return redirect(url_for("auth.login"))
        else:
            flash("Invalid or expired verification link.", "error")
            return redirect(url_for("auth.register"))

    @auth_bp.route("/verify-login/<token>")
    def verify_login(token):
        user = User.verify_token(token, 'login')
        if user and 'pending_login_user_id' in session and user['id'] == session['pending_login_user_id']:
            session.pop('pending_login_user_id', None)
            session['user_id'] = user["id"]
            print("Login successful!")
            log_action(user['id'], "login_success", f"User {user['id']} logged in successfully")
            flash("Login successful!", "success")
            return redirect(url_for("write_page"))
        else:
            flash("Invalid or expired login verification link.", "error")
            return redirect(url_for("auth.login"))

    return auth_bp  # Return the blueprint instance