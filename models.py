from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime, timedelta

db = SQLAlchemy()

# =========================
# USUÁRIOS
# =========================
class User(UserMixin, db.Model):
    __tablename__ = "user"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(150), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    telefone = db.Column(db.String(150), nullable=False)
    password = db.Column(db.String(200), nullable=False)

    def __repr__(self):
        return f"<User {self.username}>"

# =========================
# ARENAS
# =========================
class Arena(db.Model):
    __tablename__ = "arena"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)

    quadras = db.relationship("Quadra", backref="arena", lazy=True, cascade="all, delete")
    videos = db.relationship("Video", backref="arena", lazy=True, cascade="all, delete")

    def __repr__(self):
        return f"<Arena {self.nome}>"

# =========================
# QUADRAS
# =========================
class Quadra(db.Model):
    __tablename__ = "quadra"

    id = db.Column(db.Integer, primary_key=True)
    nome = db.Column(db.String(150), nullable=False)

    arena_id = db.Column(db.Integer, db.ForeignKey("arena.id"), nullable=False)

    videos = db.relationship("Video", backref="quadra", lazy=True, cascade="all, delete")

    def __repr__(self):
        return f"<Quadra {self.nome}>"

# =========================
# VÍDEOS
# =========================
class Video(db.Model):
    __tablename__ = "video"

    id = db.Column(db.Integer, primary_key=True)
    nome_arquivo = db.Column(db.String(255), nullable=False)
    arquivo = db.Column(db.LargeBinary, nullable=False)  # novo campo para o vídeo
    data_upload = db.Column(db.DateTime, default=datetime.utcnow)
    data_expiracao = db.Column(db.DateTime, nullable=False)

    arena_id = db.Column(db.Integer, db.ForeignKey("arena.id"), nullable=False)
    quadra_id = db.Column(db.Integer, db.ForeignKey("quadra.id"), nullable=False)

    def __init__(self, nome_arquivo, arquivo_bytes, arena_id, quadra_id):
        self.nome_arquivo = nome_arquivo
        self.arquivo = arquivo_bytes
        self.arena_id = arena_id
        self.quadra_id = quadra_id
        self.data_upload = datetime.now()
        self.data_expiracao = self.data_upload + timedelta(days=3)