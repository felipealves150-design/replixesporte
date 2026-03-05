import os
import time
from collections import deque
from datetime import datetime, timedelta
from io import BytesIO
import subprocess
import cv2

from flask import Flask, render_template, redirect, url_for, request, flash, send_file, jsonify, abort
from flask_login import LoginManager, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func

from models import db, User, Arena, Quadra, Video

# ===============================
# CONFIGURAÇÃO FLASK/SQLALCHEMY
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
# PASTA DE UPLOAD TEMPORÁRIO
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
# DASHBOARD COM FILTROS
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
        datas_disponiveis = [row[0] for row in db.session.query(func.date(Video.data_upload))
                             .filter(Video.quadra_id == quadra_id)
                             .distinct()
                             .order_by(func.date(Video.data_upload).desc())
                             .all()]

    horas_disponiveis = []
    if quadra_id and data_selecionada:
        horas_disponiveis = [row[0] for row in db.session.query(func.strftime("%H:00", Video.data_upload))
                             .filter(Video.quadra_id == quadra_id,
                                     func.date(Video.data_upload) == data_selecionada)
                             .distinct()
                             .order_by(func.strftime("%H:00", Video.data_upload))
                             .all()]

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
# CADASTRAR ARENA
# ===============================
@app.route("/arena/nova", methods=["GET", "POST"])
@login_required
def nova_arena():
    if request.method == "POST":
        nome = request.form["nome"]
        arena = Arena(nome=nome)
        db.session.add(arena)
        db.session.commit()
        flash("Arena cadastrada com sucesso!")
        return redirect(url_for("listar_arenas"))
    return render_template("nova_arena.html")

@app.route("/arenas")
@login_required
def listar_arenas():
    arenas = Arena.query.order_by(Arena.nome).all()
    return render_template("arenas.html", arenas=arenas)

# ===============================
# UPLOAD DE VÍDEO MANUAL
# ===============================
@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_video():
    arenas = Arena.query.order_by(Arena.nome).all()
    quadras = Quadra.query.order_by(Quadra.nome).all()

    if request.method == "POST":
        file = request.files["video"]
        arena_id = request.form.get("arena")
        quadra_id = request.form.get("quadra")

        if not file or not arena_id or not quadra_id:
            flash("Selecione arena, quadra e vídeo!")
            return redirect(url_for("upload_video"))

        nome_arquivo = file.filename
        caminho = os.path.join(UPLOAD_FOLDER, nome_arquivo)
        file.save(caminho)

        with open(caminho, "rb") as f:
            arquivo_bytes = f.read()

        novo_video = Video(
            nome_arquivo=nome_arquivo,
            arquivo_bytes=arquivo_bytes,
            arena_id=arena_id,
            quadra_id=quadra_id
        )
        db.session.add(novo_video)
        db.session.commit()
        flash("Vídeo enviado com sucesso!")
        return redirect(url_for("dashboard"))

    return render_template("upload.html", arenas=arenas, quadras=quadras)

# ===============================
# SERVIR VÍDEOS DO BANCO
# ===============================
@app.route("/video/<int:video_id>")
@login_required
def servir_video_html(video_id):
    video = Video.query.get(video_id)
    if not video or not video.arquivo:
        abort(404)
    return send_file(BytesIO(video.arquivo), mimetype="video/mp4", download_name=video.nome_arquivo)

# ===============================
# AJAX: QUADRAS, DATAS E HORAS
# ===============================
@app.route("/quadras_por_arena/<int:arena_id>")
@login_required
def quadras_por_arena(arena_id):
    quadras = Quadra.query.filter_by(arena_id=arena_id).order_by(Quadra.nome).all()
    return jsonify([{"id": q.id, "nome": q.nome} for q in quadras])

@app.route("/datas_por_quadra/<int:quadra_id>")
@login_required
def datas_por_quadra(quadra_id):
    datas = db.session.query(func.date(Video.data_upload))\
                      .filter(Video.quadra_id == quadra_id)\
                      .distinct()\
                      .order_by(func.date(Video.data_upload).desc())\
                      .all()
    return jsonify([d[0] for d in datas])

@app.route("/horas_por_quadra_data/<int:quadra_id>/<data>")
@login_required
def horas_por_quadra_data(quadra_id, data):
    horas = db.session.query(func.strftime("%H:00", Video.data_upload))\
                      .filter(Video.quadra_id == quadra_id,
                              func.date(Video.data_upload) == data)\
                      .distinct()\
                      .order_by(func.strftime("%H:00", Video.data_upload))\
                      .all()
    return jsonify([h[0] for h in horas])

# ===============================
# CAPTURA DE CÂMERA (REPLAY AUTOMÁTICO)
# ===============================
def captura_camera_replay(arena_nome="Minha Arena", quadra_nome="Quadra 1"):
    with app.app_context():
        BUFFER_SECONDS = 20
        FPS = 30
        BUFFER_SIZE = BUFFER_SECONDS * FPS
        COOLDOWN = 5

        arena = Arena.query.filter_by(nome=arena_nome).first()
        if not arena:
            arena = Arena(nome=arena_nome)
            db.session.add(arena)
            db.session.commit()

        quadra = Quadra.query.filter_by(nome=quadra_nome, arena_id=arena.id).first()
        if not quadra:
            quadra = Quadra(nome=quadra_nome, arena_id=arena.id)
            db.session.add(quadra)
            db.session.commit()

        cap = cv2.VideoCapture("rtsp://admin:Ffao929310*@192.168.0.12:554/Streaming/Channels/101")
        if not cap.isOpened():
            print("Erro ao abrir a câmera")
            return

        buffer = deque(maxlen=BUFFER_SIZE)
        ultimo_salvamento = 0

        print("Sistema iniciado. Pressione 's' para salvar replay. ESC para sair.")
        while True:
            ret, frame = cap.read()
            if not ret:
                break
            frame = cv2.resize(frame, (720, 500))
            buffer.append(frame)
            cv2.imshow("Replay System", frame)
            key = cv2.waitKey(1) & 0xFF

            if key == ord('s'):
                agora = time.time()
                if agora - ultimo_salvamento > COOLDOWN:
                    ultimo_salvamento = agora
                    nome_temp = datetime.now().strftime("replay_%H-%M-%S_temp.mp4")
                    os.makedirs("temp", exist_ok=True)
                    caminho_temp = os.path.join("temp", nome_temp)

                    height, width, _ = frame.shape
                    out = cv2.VideoWriter(caminho_temp, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (width, height))
                    for f in buffer:
                        if f is not None:
                            out.write(f)
                    out.release()
                    time.sleep(1)

                    # Converter
                    output_path = caminho_temp.replace("_temp.mp4", ".mp4")
                    comando = ["C:\\ffmpeg\\bin\\ffmpeg.exe", "-y", "-i", caminho_temp,
                               "-c:v", "libx264", "-preset", "fast", "-crf", "23",
                               "-c:a", "aac", "-movflags", "+faststart", output_path]
                    subprocess.run(comando)

                    if os.path.exists(output_path):
                        with open(output_path, "rb") as f:
                            arquivo_bytes = f.read()
                        os.remove(caminho_temp)
                        os.remove(output_path)
                        video = Video(nome_arquivo=nome_temp.replace("_temp", ""), arquivo_bytes=arquivo_bytes,
                                      arena_id=arena.id, quadra_id=quadra.id)
                        db.session.add(video)
                        db.session.commit()
                        print(f"[OK] Replay salvo: {video.nome_arquivo}")

            if key == 27:
                break

        cap.release()
        cv2.destroyAllWindows()
        print("Sistema encerrado.")

# ===============================
# EXECUTAR
# ===============================
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)