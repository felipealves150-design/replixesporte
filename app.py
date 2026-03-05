import os
import time
from collections import deque
from datetime import datetime
from io import BytesIO
import subprocess
import cv2

from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify, abort
from flask_login import LoginManager, login_user, login_required, logout_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

from models import db, User, Arena, Quadra, Video

# ===============================
# CONFIGURAÇÃO FLASK
# ===============================
app = Flask(__name__)
app.config['SECRET_KEY'] = 'segredo_super_forte'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

basedir = os.path.abspath(os.path.dirname(__file__))
db_path = os.path.join(basedir, 'instance', 'database.db')

os.makedirs(os.path.join(basedir, 'instance'), exist_ok=True)

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'

print("BANCO USADO:", db_path)

db.init_app(app)

# ===============================
# LOGIN MANAGER
# ===============================
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = None


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ===============================
# PASTA TEMPORÁRIA
# ===============================
UPLOAD_FOLDER = os.path.join(basedir, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)


# ===============================
# SITE PÚBLICO
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

        if User.query.filter_by(email=email).first():

            flash("Email já cadastrado!")
            return redirect(url_for("register"))

        new_user = User(
            username=username,
            email=email,
            telefone=telefone,
            password=password
        )

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

        email = request.form.get("email")
        password = request.form.get("password")

        user = User.query.filter_by(email=email).first()

        if user and check_password_hash(user.password, password):

            login_user(user)
            return redirect(url_for("dashboard"))

        flash("Credenciais inválidas!")

    return render_template("login.html")


# ===============================
# LOGOUT
# ===============================
@app.route("/logout")
@login_required
def logout():

    logout_user()
    return redirect(url_for("home"))


# ===============================
# DASHBOARD
# ===============================
@app.route("/dashboard")
@login_required
def dashboard():

    arena_id = request.args.get("arena")
    quadra_id = request.args.get("quadra")
    data_selecionada = request.args.get("data")
    hora_selecionada = request.args.get("hora")

    arenas = Arena.query.order_by(Arena.nome).all()

    videos = []
    pesquisou = False

    if arena_id and quadra_id and data_selecionada and hora_selecionada:

        pesquisou = True

        videos = Video.query.filter(
            Video.arena_id == arena_id,
            Video.quadra_id == quadra_id,
            func.date(Video.data_upload) == data_selecionada,
            func.strftime("%H:00", Video.data_upload) == hora_selecionada
        ).order_by(Video.data_upload.desc()).all()

    datas_disponiveis = []

    if quadra_id:

        datas_disponiveis = [
            row[0] for row in db.session.query(func.date(Video.data_upload))
            .filter(Video.quadra_id == quadra_id)
            .distinct()
            .order_by(func.date(Video.data_upload).desc())
            .all()
        ]

    horas_disponiveis = []

    if quadra_id and data_selecionada:

        horas_disponiveis = [
            row[0] for row in db.session.query(func.strftime("%H:00", Video.data_upload))
            .filter(
                Video.quadra_id == quadra_id,
                func.date(Video.data_upload) == data_selecionada
            )
            .distinct()
            .order_by(func.strftime("%H:00", Video.data_upload))
            .all()
        ]

    return render_template(
        "dashboard.html",
        arenas=arenas,
        videos=videos,
        arena_selecionada=arena_id,
        quadra_selecionada=quadra_id,
        data_selecionada=data_selecionada,
        hora_selecionada=hora_selecionada,
        datas_disponiveis=datas_disponiveis,
        horas_disponiveis=horas_disponiveis,
        pesquisou=pesquisou
    )


# ===============================
# API RECEBER REPLAY DO PC
# ===============================
@app.route("/api/upload", methods=["POST"])
def api_upload():

    video = request.files.get("video")
    arena_nome = request.form.get("arena")
    quadra_nome = request.form.get("quadra")

    if not video or not arena_nome or not quadra_nome:

        return jsonify({"erro": "dados incompletos"}), 400

    arquivo_bytes = video.read()

    arena = Arena.query.filter_by(nome=arena_nome).first()

    if not arena:

        arena = Arena(nome=arena_nome)
        db.session.add(arena)
        db.session.commit()

    quadra = Quadra.query.filter_by(
        nome=quadra_nome,
        arena_id=arena.id
    ).first()

    if not quadra:

        quadra = Quadra(
            nome=quadra_nome,
            arena_id=arena.id
        )

        db.session.add(quadra)
        db.session.commit()

    novo_video = Video(
        nome_arquivo=video.filename,
        arquivo_bytes=arquivo_bytes,
        arena_id=arena.id,
        quadra_id=quadra.id
    )

    db.session.add(novo_video)
    db.session.commit()

    print("Replay recebido:", video.filename)

    return jsonify({"status": "ok"})


# ===============================
# SERVIR VIDEO
# ===============================
@app.route("/video/<int:video_id>")
@login_required
def servir_video_html(video_id):

    video = Video.query.get(video_id)

    if not video or not video.arquivo_bytes:

        abort(404)

    return send_file(
        BytesIO(video.arquivo_bytes),
        mimetype="video/mp4",
        download_name=video.nome_arquivo
    )


# ===============================
# AJAX QUADRAS
# ===============================
@app.route("/quadras_por_arena/<int:arena_id>")
@login_required
def quadras_por_arena(arena_id):

    quadras = Quadra.query.filter_by(arena_id=arena_id).order_by(Quadra.nome).all()

    return jsonify([
        {"id": q.id, "nome": q.nome}
        for q in quadras
    ])


# ===============================
# EXECUTAR
# ===============================
if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)
