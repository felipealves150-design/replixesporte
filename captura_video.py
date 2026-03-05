import os
import cv2
import time
import requests
from collections import deque
from datetime import datetime
import subprocess

# =========================
# CONFIGURAÇÃO
# =========================
os.environ["OPENCV_FFMPEG_CAPTURE_OPTIONS"] = "rtsp_transport;tcp|fflags;nobuffer|flags;low_delay|max_delay;0"

BUFFER_SECONDS = 15
FPS = 30
BUFFER_SIZE = BUFFER_SECONDS * FPS
COOLDOWN = 5  # segundos

CAMERA_URL = "rtsp://admin:Ffao929310*@192.168.0.12:554/Streaming/Channels/101"

NOME_ARENA = "Salgas Beach"
NOME_QUADRA = "Quadra 1"

API_UPLOAD = "https://replixesporte-vpcw.onrender.com/api/upload_video"

# =========================
# FUNÇÃO PARA CONVERTER VIDEO PARA H264
# =========================
def converter_video_bytes(input_path):
    output_path = input_path.replace("_temp.mp4", ".mp4")
    comando = [
        r"C:\ffmpeg\bin\ffmpeg.exe",
        "-y",
        "-i", input_path,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-movflags", "+faststart",
        output_path
    ]
    resultado = subprocess.run(comando, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if resultado.returncode == 0 and os.path.exists(output_path):
        with open(output_path, "rb") as f:
            video_bytes = f.read()
        os.remove(input_path)
        os.remove(output_path)
        return video_bytes
    else:
        print("[ERRO] Conversão do vídeo falhou.")
        print(resultado.stderr.decode())
        return None

# =========================
# FUNÇÃO PARA CRIAR ARENA/QUADRA NO SERVIDOR
# =========================
def garantir_arena_quadra():
    try:
        # Tentativa de envio sem arquivo apenas para criar arena/quadra
        response = requests.post(
            API_UPLOAD,
            files={},  # Nenhum arquivo
            data={"arena": NOME_ARENA, "quadra": NOME_QUADRA},
            timeout=10
        )
        # Servidor deve retornar erro 400 porque não enviamos vídeo, mas cria arena/quadra se não existirem
        if response.status_code in [200, 400]:
            print(f"[INFO] Arena '{NOME_ARENA}' e Quadra '{NOME_QUADRA}' verificadas no servidor.")
        else:
            print(f"[ERRO] Falha ao criar/verificar arena/quadra: {response.status_code} {response.text}")
    except Exception as e:
        print("[ERRO] Não foi possível verificar arena/quadra:", e)

# =========================
# FUNÇÃO PARA ENVIAR VIDEO PARA RENDER
# =========================
def enviar_replay(bytes_video, nome_video):
    try:
        files = {"video": (nome_video, bytes_video, "video/mp4")}
        data = {"arena": NOME_ARENA, "quadra": NOME_QUADRA}
        response = requests.post(API_UPLOAD, files=files, data=data, timeout=30)

        if response.status_code == 200:
            print(f"[OK] Replay '{nome_video}' enviado para o servidor!")
        else:
            print(f"[ERRO] Código {response.status_code}: {response.text}")
    except Exception as e:
        print("[ERRO] Upload falhou:", e)

# =========================
# CONECTAR CÂMERA
# =========================
def conectar_camera():
    while True:
        print("Conectando na câmera...")
        cap = cv2.VideoCapture(CAMERA_URL, cv2.CAP_FFMPEG)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 2)
        if cap.isOpened():
            print("Câmera conectada!")
            print(f"Resolução: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")
            return cap
        print("Falha ao conectar. Tentando novamente em 5s...")
        time.sleep(5)

# =========================
# SISTEMA PRINCIPAL
# =========================
def main():
    garantir_arena_quadra()
    cap = conectar_camera()
    buffer = deque(maxlen=BUFFER_SIZE)
    ultimo_salvamento = 0

    print("Sistema iniciado. Pressione 's' = salvar replay | ESC = sair")

    while True:
        ret, frame = cap.read()
        if not ret or frame is None or frame.size == 0:
            print("Frame perdido... reconectando")
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
                nome_temp = datetime.now().strftime("replay_%H-%M-%S_temp.mp4")
                os.makedirs("temp", exist_ok=True)
                caminho_temp = os.path.join("temp", nome_temp)

                height, width, _ = frame.shape
                out = cv2.VideoWriter(caminho_temp, cv2.VideoWriter_fourcc(*'mp4v'), FPS, (width, height))
                for f in list(buffer):
                    if f is not None:
                        out.write(f)
                out.release()
                time.sleep(0.1)

                # Converter para H264
                arquivo_bytes = converter_video_bytes(caminho_temp)
                if arquivo_bytes:
                    nome_final = nome_temp.replace("_temp", "")
                    print("Enviando replay para o servidor...")
                    enviar_replay(arquivo_bytes, nome_final)
                else:
                    print("[ERRO] Não foi possível gerar bytes do vídeo.")
            else:
                print("Cooldown ativo. Aguarde...")

        # =========================
        # SAIR
        # =========================
        if key == 27:
            break

    cap.release()
    cv2.destroyAllWindows()
    print("Sistema encerrado.")

if __name__ == "__main__":
    main()