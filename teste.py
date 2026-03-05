from flask import Flask, render_template, redirect, url_for, request, flash
from models import db, User
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, login_user, login_required, logout_user, current_user

app = Flask(__name__)
app.config['SECRET_KEY'] = 'segredo_super_forte'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///database.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


# ===============================
# USER LOADER
# ===============================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))
    



# ===============================
# SITE PÚBLICO (INDEX)
# ===============================

@app.route("/")
def home():
    return render_template("index.html")


# ===============================
# REGISTRO
# ===============================

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        telefone = request.form["telefone"]
        password = generate_password_hash(request.form["password"])

        if User.query.filter_by(username=username).first():
            flash("Usuário já existe!")
            return redirect(url_for("register"))

        new_user = User(username=username, email=email, telefone=telefone, password=password)
        db.session.add(new_user)
        db.session.commit()

        flash("Conta criada com sucesso!")
        return redirect(url_for("login"))

    return render_template("register.html")


# ===============================
# LOGIN
# ===============================

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username")
        email = request.form.get("email")
        telefone = request.form.get("telefone")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user:
            if check_password_hash(user.password, password):
                login_user(user)
                return redirect(url_for("dashboard"))
            else:
                flash("Senha incorreta!")
        else:
            flash("Usuário não encontrado!")

    return render_template("login.html")

# ===============================
# DASHBOARD PROTEGIDO
# ===============================

@app.route("/dashboard")
@login_required
def dashboard():
    return render_template(
        "dashboard.html",
        username=current_user.username,
        email=current_user.email,
        telefone=current_user.telefone
    )


# ===============================
# LOGOUT
# ===============================

@app.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("home"))


# ===============================
# RUN
# ===============================

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)