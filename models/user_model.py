import bcrypt
from db import get_db_cursor
import uuid
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os
import random
import string

# Load encryption key from environment or generate a new one (only for future use if we add encryption elsewhere)
key = os.getenv("ENCRYPTION_KEY") or Fernet.generate_key()
cipher = Fernet(key)

class User:
    @staticmethod
    def create_user(username, email, password, role="teacher", class_code=None):
        """Create a new user with hashed password and plain text unique access code for students"""
        print(f"Attempting to create user: {username}, {email}, role: {role}, class_code: {class_code}")
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
        # No encryption for email
        unique_code = None
        if role == "student":
            unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
            while User.find_by_access_code(unique_code):  # Ensure uniqueness
                unique_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))
        connection, cursor = get_db_cursor()
        try:
            sql = """
                INSERT INTO users (username, email, password_hash, role, class_code, unique_access_code, is_verified, theme, avatar_url, created_at, is_superuser)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s)
            """
            values = (username, email, hashed_pw, role, class_code, unique_code, 0, 'default', None, 0)
            print("Executing user insertion...")
            cursor.execute(sql, values)
            connection.commit()
            print("User inserted successfully.")
            
            cursor.execute("SELECT LAST_INSERT_ID()")
            user_id = cursor.fetchone()[0]
            print(f"New user ID: {user_id}")
            
            token = str(uuid.uuid4())
            expires_at = datetime.now() + timedelta(hours=24)
            print("Inserting verification token...")
            cursor.execute("""
                INSERT INTO verification_tokens (user_id, token, purpose, expires_at)
                VALUES (%s, %s, %s, %s)
            """, (user_id, token, 'registration', expires_at))
            connection.commit()
            print("Verification token inserted successfully.")
            
            return token
        except Exception as e:
            print("Error:", e)
            connection.rollback()
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def find_by_email(email):
        """Find a user by email (plain text)"""
        print(f"Looking up user by email: {email}")
        connection, cursor = get_db_cursor()
        try:
            sql = "SELECT * FROM users WHERE email = %s"
            cursor.execute(sql, (email,))
            user = cursor.fetchone()
            if user:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, user))
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def verify_user(email, password):
        """Verify user credentials with plain text email"""
        user = User.find_by_email(email)
        if user and bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            return user
        return None

    @staticmethod
    def verify_token(token, purpose):
        """Verify a token and return the associated user"""
        print(f"Verifying token: {token} for purpose: {purpose}")
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("""
                SELECT user_id FROM verification_tokens 
                WHERE token = %s AND purpose = %s AND expires_at > NOW()
            """, (token, purpose))
            result = cursor.fetchone()
            if result:
                user_id = result[0]
                cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
                user = cursor.fetchone()
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, user))
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def find_by_access_code(unique_access_code):
        """Find a user by unique access code (plain text)"""
        print(f"Looking up user by access code: {unique_access_code}")
        connection, cursor = get_db_cursor()
        try:
            sql = "SELECT * FROM users WHERE unique_access_code = %s"
            cursor.execute(sql, (unique_access_code,))
            user = cursor.fetchone()
            if user:
                columns = [column[0] for column in cursor.description]
                return dict(zip(columns, user))
            return None
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def mark_as_verified(user_id):
        """Mark a user as verified"""
        print(f"Marking user {user_id} as verified")
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("UPDATE users SET is_verified = 1 WHERE id = %s", (user_id,))
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            print(f"Error marking user as verified: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def update_theme(user_id, theme):
        """Update the user's theme"""
        print(f"Updating theme for user {user_id} to {theme}")
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("UPDATE users SET theme = %s WHERE id = %s", (theme, user_id))
            connection.commit()
            print(f"Theme updated successfully for user {user_id} to {theme}")
            return True
        except Exception as e:
            connection.rollback()
            print(f"Error updating theme: {e}")
            return False
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def update_avatar(user_id, avatar_url):
        """Update the user's avatar URL"""
        print(f"Updating avatar for user {user_id} to {avatar_url}")
        connection, cursor = get_db_cursor()
        try:
            cursor.execute("UPDATE users SET avatar_url = %s WHERE id = %s", (avatar_url, user_id))
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            print(f"Error updating avatar: {e}")
            return False
        finally:
            cursor.close()
            connection.close()