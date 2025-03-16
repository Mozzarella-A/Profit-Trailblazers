import bcrypt
from db import get_db_cursor

class User:
    @staticmethod
    def create_user(username, email, password, role, class_code=None):
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        connection, cursor = get_db_cursor()
        try:
            sql = """
                INSERT INTO users (username, email, password_hash, role, class_code, created_at)
                VALUES (%s, %s, %s, %s, %s, NOW())
            """
            cursor.execute(sql, (username, email, hashed_pw, role, class_code))
            connection.commit()
            return True
        except Exception as e:
            connection.rollback()
            raise e
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def find_by_email(email):
        connection, cursor = get_db_cursor()
        try:
            sql = "SELECT * FROM users WHERE email = %s"
            cursor.execute(sql, (email,))
            return cursor.fetchone()
        finally:
            cursor.close()
            connection.close()

    @staticmethod
    def verify_user(email, password):
        user = User.find_by_email(email)
        if user and bcrypt.checkpw(password.encode('utf-8'), user[3].encode('utf-8')):  # user[3] is password_hash
            return user
        return None