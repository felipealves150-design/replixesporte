import os
from flask import Flask
from models import db, Arena, Quadra, Video

# =========================
# CONFIGURAÇÃO FLASK/SQLALCHEMY
# =========================
app = Flask(__name__)

BASE_DIR = r"C:/Users/Kivianne Hipolito/Desktop/Felipe/Replix/replixesporte/instance"
DB_PATH = os.path.join(BASE_DIR, "database.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)

# =========================
# FUNÇÃO DE CONSULTA
# =========================
def consultar_videos(arena_nome=None, quadra_nome=None, salvar_local=False):
    with app.app_context():
        query = Video.query

        # Filtrar por arena se informado
        if arena_nome:
            arena = Arena.query.filter_by(nome=arena_nome).first()
            if arena:
                query = query.filter_by(arena_id=arena.id)
            else:
                print(f"Arena '{arena_nome}' não encontrada.")
                return

        # Filtrar por quadra se informado
        if quadra_nome:
            if not arena_nome:
                print("Para filtrar por quadra, informe a arena.")
                return
            quadra = Quadra.query.filter_by(nome=quadra_nome, arena_id=arena.id).first()
            if quadra:
                query = query.filter_by(quadra_id=quadra.id)
            else:
                print(f"Quadra '{quadra_nome}' não encontrada na arena '{arena_nome}'.")
                return

        videos = query.order_by(Video.id.desc()).all()

        if not videos:
            print("Nenhum vídeo encontrado.")
            return

        # Pasta para salvar vídeos localmente
        if salvar_local:
            pasta_download = "videos_baixados"
            os.makedirs(pasta_download, exist_ok=True)

        for v in videos:
            print(f"ID: {v.id}")
            print(f"Nome: {v.nome_arquivo}")
            print(f"Arena ID: {v.arena_id}")
            print(f"Quadra ID: {v.quadra_id}")
            
            # Verifica se o vídeo tem o campo correto
            arquivo_data = getattr(v, "arquivo", None)
            if arquivo_data:
                print(f"Tamanho: {len(arquivo_data)} bytes")
                if salvar_local:
                    caminho = os.path.join(pasta_download, v.nome_arquivo)
                    with open(caminho, "wb") as f:
                        f.write(arquivo_data)
                    print(f"Vídeo salvo em: {caminho}")
            else:
                print("Nenhum arquivo de vídeo disponível para este registro.")
            
            print("-" * 30)

# =========================
# EXEMPLO DE USO
# =========================
if __name__ == "__main__":
    consultar_videos()