import bcrypt
from db import db, cursor

class User:
    @staticmethod
    def create_user(username, email, password, role, class_code=None):
        """Create a new user with hashed password"""
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        sql = "INSERT INTO users (username, email, password_hash, account_type, class_code) VALUES (%s, %s, %s, %s, %s)"
        values = (username, email, hashed_pw, role, class_code)

        try:
            cursor.execute(sql, values)
            db.commit()
            return True
        except Exception as e:
            print("Error:", e)
            return False

    @staticmethod
    def find_by_email(email):
        """Find a user by email and return a dictionary"""
        sql = "SELECT * FROM users WHERE email = %s"
        cursor.execute(sql, (email,))
        user = cursor.fetchone()

        if user:
            columns = [column[0] for column in cursor.description]  # Get column names
            return dict(zip(columns, user))  # Convert tuple to dictionary

        return None

    @staticmethod
    def verify_user(email, password):
        """Verify user credentials"""
        user = User.find_by_email(email)
        if user and bcrypt.checkpw(password.encode('utf-8'), user["password_hash"].encode('utf-8')):
            return user
        return None
