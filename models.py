import bcrypt
from db import db

class User:
    @staticmethod
    def create_user(email, password, role, avatar_url):
        hashed_pw = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())
        sql = "INSERT INTO users (email, password_hash, role, avatar_url) VALUES (%s, %s, %s, %s)"
        db.cursor().execute(sql, (email, hashed_pw, role, avatar_url))
        db.commit()

    @staticmethod
    def find_by_email(email):
        sql = "SELECT * FROM users WHERE email = %s"
        cursor = db.cursor()
        cursor.execute(sql, (email,))
        return cursor.fetchone()
