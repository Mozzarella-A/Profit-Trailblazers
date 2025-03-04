from flask import Flask, render_template, request, redirect, url_for

app = Flask(__name__, static_folder="static", template_folder="templates")

@app.route("/", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        return redirect(url_for("browse"))
    return render_template("login.html")

@app.route("/register")
def register():
    return render_template("register.html")

@app.route("/browse")
def browse():
    return render_template("browse.html")

@app.route("/write")
def write_article():
    return render_template("write.html")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=True)
