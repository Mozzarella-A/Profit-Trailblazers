from flask import Flask, request, jsonify
from flask_jwt_extended import JWTManager, create_access_token
from models import User
from config import Config

app = Flask(__name__)
app.config.from_object(Config)
jwt = JWTManager(app)

@app.route("/register", methods=["POST"])
def register():
    data = request.json
    if User.find_by_email(data["email"]):
        return jsonify({"message": "User already exists"}), 400
    
    User.create_user(data["email"], data["password"], data["role"], data["avatar_url"])
    return jsonify({"message": "User registered successfully"}), 201

@app.route("/login", methods=["POST"])
def login():
    data = request.json
    user = User.find_by_email(data["email"])

    if not user or not bcrypt.checkpw(data["password"].encode('utf-8'), user[2].encode('utf-8')):
        return jsonify({"message": "Invalid credentials"}), 401
    
    access_token = create_access_token(identity=user[0])
    return jsonify({"token": access_token}), 200

if __name__ == "__main__":
    app.run(debug=True)
