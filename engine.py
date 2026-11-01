import os
import subprocess
import tempfile
import yt_dlp
from pathlib import Path
from database import DatabaseManager

class MediaEngine:
    def __init__(self, db_manager: DatabaseManager, ffmpeg_path: str = "ffmpeg"):
        self.db = db_manager
        self.ffmpeg_path = ffmpeg_path
        self.temp_dir = tempfile.gettempdir()

    def process_video(self, video_data: dict, ytdlp_opts: dict, destino_final_dir: str):
        """
        Executa o fluxo de download para o %TEMP%, conversão e movimento para a pen drive.
        Atualiza o estado na base de dados a cada passo.
        """
        youtube_id = video_data['youtube_id']
        url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        # Configurar yt-dlp para gravar ficheiro bruto no %TEMP%
        raw_output_template = os.path.join(self.temp_dir, f"{youtube_id}_raw.%(ext)s")
        opts = ytdlp_opts.copy()
        opts['outtmpl'] = raw_output_template

        # 1. Download Bruto
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # Obter o caminho real gerado pelo yt-dlp (com a extensão correta)
                raw_filepath = ydl.prepare_filename(info)
                
            self._atualizar_status_db(youtube_id, "descarregado")
            
        except yt_dlp.utils.DownloadError:
            self._atualizar_status_db(youtube_id, "erro")
            return

        # 2. Conversão (HandBrakeCLI)
        Path(destino_final_dir).mkdir(parents=True, exist_ok=True)
        final_filename = f"{info.get('title', youtube_id)}.mp4".replace('/', '_').replace('\\', '_')
        final_filepath = os.path.join(destino_final_dir, final_filename)

        try:
            self._converter_video(raw_filepath, final_filepath)
            
            # Limpeza do ficheiro bruto no %TEMP%
            if os.path.exists(raw_filepath):
                os.remove(raw_filepath)
                
            self._atualizar_status_db(youtube_id, "convertido", final_filepath)
            
        except subprocess.CalledProcessError:
            self._atualizar_status_db(youtube_id, "erro")

    def _converter_video(self, input_path: str, output_path: str):
        """
        Invoca o FFmpeg estático para forçar o output a 320x240 (4:3) H.264/AAC,
        replicando com exatidão o preset "CARRO PAI".
        """
        cmd = [
            self.ffmpeg_path,
            "-y", # Sobrescrever ficheiro se existir
            "-i", input_path,
            "-c:v", "libx264",
            "-profile:v", "baseline", # Máxima compatibilidade com centrais auto antigas
            "-level", "3.0",
            "-vf", "scale=320:240,setdar=16/9", # Força a resolução e diz ao player para esticar
            "-r", "30", # Framerate a 30fps
            "-c:a", "aac",
            "-b:a", "160k",
            "-ac", "2", # Stereo
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