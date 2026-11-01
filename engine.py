import os
import subprocess
import tempfile
import yt_dlp
from pathlib import Path
from database import DatabaseManager

class MediaEngine:
    def __init__(self, db_manager: DatabaseManager, handbrake_path: str = "HandBrakeCLI", preset_path: str = "CARRO PAI.json"):
        """
        Inicializa o motor multimédia. Espera que o binário do HandBrakeCLI e o ficheiro
        CARRO PAI.json estejam na diretoria do projeto ou no PATH.
        """
        self.db = db_manager
        self.handbrake_path = handbrake_path
        self.preset_path = preset_path
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
        Invoca o HandBrakeCLI como subprocesso, importando estritamente o preset JSON.
        """
        cmd = [
            self.handbrake_path,
            "--preset-import-file", self.preset_path,
            "-Z", "CARRO PAI",
            "-i", input_path,
            "-o", output_path
        ]
        # Executa o comando suprimindo o output do terminal (ou pode redirecionar para um logger)
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