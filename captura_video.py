import os
import cv2
import time
from collections import deque
from datetime import datetime
import subprocess

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from models import db, Arena, Quadra, Video


# =========================
# OTIMIZAÇÃO RTSP
# =========================
#os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|buffer_size;1024000|max_delay;500000"
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0"


# =========================
# CONFIGURAÇÃO FLASK
# =========================
app = Flask(__name__)

BASE_DIR = r"C:/Users/Kivianne Hipolito/Desktop/Felipe/Replix/replixesporte/instance"
os.makedirs(BASE_DIR, exist_ok=True)

DB_PATH = os.path.join(BASE_DIR, "database.db")

app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db.init_app(app)


# =========================
# CONFIGURAÇÃO CAPTURA
# =========================
BUFFER_SECONDS = 15
FPS = 30
BUFFER_SIZE = BUFFER_SECONDS * FPS

COOLDOWN = 5

CAMERA_URL = "rtsp://admin:Ffao929310*@192.168.0.12:554/Streaming/Channels/101"

NOME_ARENA = "Cactoos"
NOME_QUADRA = "Quadra 1"


# =========================
# FUNÇÃO CONVERTER VIDEO
# =========================
def converter_video_bytes(input_path):

    output_path = input_path.replace("_temp.mp4", ".mp4")

    comando = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        "-loglevel", "quiet",
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        output_path
    ]

    resultado = subprocess.run(comando)

    if resultado.returncode == 0 and os.path.exists(output_path):

        with open(output_path, "rb") as f:
            video_bytes = f.read()

        os.remove(input_path)
        os.remove(output_path)

        return video_bytes

    else:
        print("Erro na conversão.")
        return None


# =========================
# FUNÇÃO CONECTAR CAMERA
# =========================
def conectar_camera():

    while True:

        print("Conectando na câmera...")

        cap = cv2.VideoCapture(CAMERA_URL, cv2.CAP_FFMPEG)

        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)

        if cap.isOpened():

            print("Câmera conectada!")

            largura = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            altura = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)

            print(f"Resolução da câmera: {int(largura)}x{int(altura)}")

            return cap

        print("Falha ao conectar. Tentando novamente em 5s...")
        time.sleep(5)


# =========================
# SISTEMA PRINCIPAL
# =========================
with app.app_context():

    arena = Arena.query.filter_by(nome=NOME_ARENA).first()

    if not arena:
        arena = Arena(nome=NOME_ARENA)
        db.session.add(arena)
        db.session.commit()

    quadra = Quadra.query.filter_by(nome=NOME_QUADRA, arena_id=arena.id).first()

    if not quadra:
        quadra = Quadra(nome=NOME_QUADRA, arena_id=arena.id)
        db.session.add(quadra)
        db.session.commit()

    cap = conectar_camera()

    buffer = deque(maxlen=BUFFER_SIZE)

    ultimo_salvamento = 0

    print("Sistema iniciado.")
    print("Pressione 's' para salvar replay.")
    print("ESC para sair.")

    while True:

        ret, frame = cap.read()

        # =========================
        # TRATAMENTO FRAME
        # =========================
        if not ret or frame is None or frame.size == 0:

            print("Frame perdido... reconectando câmera")

            cap.release()
            time.sleep(1)
            cap = conectar_camera()

            continue

        buffer.append(frame)

        cv2.imshow("Replay System", frame)

        key = cv2.waitKey(1) & 0xFF


        # =========================
        # SALVAR REPLAY
        # =========================
        if key == ord('s'):

            agora = time.time()

            if agora - ultimo_salvamento > COOLDOWN:

                ultimo_salvamento = agora

                frames_para_salvar = list(buffer)

                nome_temp = datetime.now().strftime("replay_%H-%M-%S_temp.mp4")

                os.makedirs("temp", exist_ok=True)

                caminho_temp = os.path.join("temp", nome_temp)

                height, width, _ = frame.shape

                out = cv2.VideoWriter(
                    caminho_temp,
                    cv2.VideoWriter_fourcc(*'MJPG'),
                    FPS,
                    (width, height)
                )

                for f in frames_para_salvar:

                    if f is not None:
                        out.write(f)

                out.release()

                time.sleep(0.1)

                arquivo_bytes = converter_video_bytes(caminho_temp)

                if arquivo_bytes:

                    novo_video = Video(
                        nome_arquivo=nome_temp.replace("_temp", ""),
                        arquivo_bytes=arquivo_bytes,
                        arena_id=arena.id,
                        quadra_id=quadra.id
                    )

                    db.session.add(novo_video)
                    db.session.commit()

                    print(f"[OK] Replay salvo: {novo_video.nome_arquivo}")

                else:

                    print("Falha ao gerar bytes do vídeo.")

            else:

                print("Cooldown ativo... Aguarde.")


        # =========================
        # SAIR
        # =========================
        if key == 27:
            break


    cap.release()
    cv2.destroyAllWindows()

    print("Sistema encerrado.")