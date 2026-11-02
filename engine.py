import os
import subprocess
import tempfile
import shutil
import yt_dlp
import re
from pathlib import Path
from database import DatabaseManager

class MediaEngine:
    def __init__(self, db_manager: DatabaseManager, ffmpeg_path: str = "ffmpeg"):
        self.db = db_manager
        self.ffmpeg_path = ffmpeg_path
        self.temp_dir = tempfile.gettempdir()

    def process_video(self, video_data: dict, ytdlp_opts: dict, destino_final_dir: str):
        youtube_id = video_data['youtube_id']
        url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        # Caminho bruto no %TEMP% (SSD)
        raw_output_template = os.path.join(self.temp_dir, f"{youtube_id}_raw.%(ext)s")
        opts = ytdlp_opts.copy()
        opts['outtmpl'] = raw_output_template

        # 1. Download Bruto (Ocorre no SSD)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                raw_filepath = ydl.prepare_filename(info)
                
            self._atualizar_status_db(youtube_id, "descarregado")
            
        except yt_dlp.utils.DownloadError:
            self._incrementar_erro(youtube_id)
            return

        # 2. Conversão e Nomeação
        Path(destino_final_dir).mkdir(parents=True, exist_ok=True)
        
        titulo_bruto = info.get('title', youtube_id)
        titulo_seguro = re.sub(r'[^\w\-_\. ]', '_', titulo_bruto)
        titulo_seguro = re.sub(r'_+', '_', titulo_seguro).strip('_ ')
        
        final_filename = f"{titulo_seguro}.mp4"
        
        # Caminho temporário de conversão (Também no SSD)
        temp_converted_filepath = os.path.join(self.temp_dir, f"{youtube_id}_conv.mp4")
        # Caminho de destino final no Pendrive
        final_filepath = os.path.join(destino_final_dir, final_filename)

        try:
            # Transcodifica 100% no SSD local para máxima performance
            self._converter_video(raw_filepath, temp_converted_filepath)
            
            # Transferência atômica: Move o vídeo finalizado de uma vez para o pendrive
            shutil.move(temp_converted_filepath, final_filepath)
            
            # Limpeza do vídeo bruto residual no SSD
            if os.path.exists(raw_filepath):
                os.remove(raw_filepath)
                
            self._atualizar_status_db(youtube_id, "convertido", final_filepath)
            
        except (subprocess.CalledProcessError, Exception):
            # Limpeza de arquivos temporários em caso de falha
            if os.path.exists(temp_converted_filepath):
                os.remove(temp_converted_filepath)
            if os.path.exists(raw_filepath):
                os.remove(raw_filepath)
            self._incrementar_erro(youtube_id)

    def _converter_video(self, input_path: str, output_path: str):
        """
        Invoca o FFmpeg estático forçando 320x240 (4:3) H.264 e áudio AAC de alta fidelidade (192k / 44.1kHz).
        """
        cmd = [
            self.ffmpeg_path,
            "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-profile:v", "baseline",
            "-level", "3.0",
            "-vf", "scale=320:240,setdar=16/9",
            "-r", "30",
            "-c:a", "aac",
            "-b:a", "192k",    # Aumentado de 160k para 192k para mitigar a perda por re-encoding
            "-ar", "44100",   # Taxa de amostragem de 44.1 kHz para evitar resampling degradante
            "-ac", "2",       # Stereo
            output_path
        ]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _atualizar_status_db(self, youtube_id: str, status: str, caminho: str = None):
        """Atualiza a máquina de estados do ficheiro na base de dados."""
        with self.db.get_connection() as conn:
            if caminho:
                conn.execute(
                    "UPDATE videos SET status = ?, caminho_ficheiro = ? WHERE youtube_id = ?",
                    (status, caminho, youtube_id)
                )
            else:
                conn.execute(
                    "UPDATE videos SET status = ? WHERE youtube_id = ?",
                    (status, youtube_id)
                )
            conn.commit()

    def _incrementar_erro(self, youtube_id: str):
        """Regista a falha e incrementa o contador de tentativas."""
        with self.db.get_connection() as conn:
            conn.execute("""
                UPDATE videos 
                SET status = 'erro', tentativas = tentativas + 1 
                WHERE youtube_id = ?
            """, (youtube_id,))
            conn.commit()