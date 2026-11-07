import os
import subprocess
import tempfile
import shutil
import yt_dlp
import re
import platform
from pathlib import Path
from database import DatabaseManager

class MediaEngine:
    def __init__(self, db_manager: DatabaseManager, ffmpeg_path: str = "ffmpeg"):
        self.db = db_manager
        self.ffmpeg_path = ffmpeg_path
        self.temp_dir = tempfile.gettempdir()

    def process_video(self, video_data: dict, ytdlp_opts: dict, destino_final_dir: str, forcar_corte_cego: bool = False):
        youtube_id = video_data['youtube_id']
        playlist_id = video_data['playlist_id']
        url = f"https://www.youtube.com/watch?v={youtube_id}"
        
        raw_output_template = os.path.join(self.temp_dir, f"{youtube_id}_raw.%(ext)s")
        opts = ytdlp_opts.copy()
        opts['outtmpl'] = raw_output_template

        # 1. Download Bruto e Leitura de Capítulos (1x no SSD)
        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=True)
                if info is None:
                    raise Exception("O yt-dlp retornou metadados vazios (None).")
                raw_filepath = ydl.prepare_filename(info)
                capitulos = info.get('chapters', []) # Puxa a lista de timestamps se existir
                
            self._atualizar_status_db(youtube_id, "descarregado")
            
        except Exception as e:
            print(f"[Engine] Falha ao extrair/descarregar {youtube_id}: {str(e)}")
            self._incrementar_erro(youtube_id)
            return

        # 2. Conversão e Fatiamento
        Path(destino_final_dir).mkdir(parents=True, exist_ok=True)

        try:
            # === NOVA LÓGICA DE INTERCEPTAÇÃO (IA ACÚSTICA) ===
            # Se não houver capítulos oficiais e o botão na interface estiver ativado, processa o áudio!
            if not capitulos and forcar_corte_cego:
                print("[Engine] Sem Capítulos oficiais. A iniciar Análise Acústica de Silêncio...")
                titulo_original = info.get('title', youtube_id)
                canal_original = info.get('uploader', 'Canal Desconhecido') # NOVO: Puxa o canal
                
                # Passa os 4 dados para a inteligência
                capitulos = self._gerar_capitulos_por_silencio(raw_filepath, info.get('duration', 0), titulo_original, canal_original, youtube_id)

            if capitulos:
                # === MODO ÁLBUM (MÚLTIPLAS FAIXAS / CAPÍTULOS) ===
                print(f"[Engine] {len(capitulos)} capítulos detetados! A iniciar fatiamento automático...")
                for idx, cap in enumerate(capitulos, 1):
                    titulo_cap = cap.get('title', f"Track {idx}")
                    start_t = cap.get('start_time')
                    end_t = cap.get('end_time')
                    
                    titulo_seguro = re.sub(r'[^\w\-_\. ]', '_', titulo_cap)
                    titulo_seguro = re.sub(r'_+', '_', titulo_seguro).strip('_ ')
                    
                    # Nomeia as faixas em ordem numérica (01 - Musica, 02 - Musica)
                    final_filename = f"{idx:02d} - {titulo_seguro}.mp4"
                    temp_conv = os.path.join(self.temp_dir, f"{youtube_id}_c{idx}_conv.mp4")
                    final_filepath = os.path.join(destino_final_dir, final_filename)
                    
                    # Fatiamento Cirúrgico e Conversão Simultânea
                    self._converter_video(raw_filepath, temp_conv, start_t, end_t)
                    shutil.move(temp_conv, final_filepath)
                    
                    if idx == 1:
                        # O 1º capítulo usa o registo original no Banco de Dados
                        self._atualizar_status_db(youtube_id, "convertido", final_filepath)
                        self._atualizar_titulo_db(youtube_id, titulo_cap) # Muda o título genérico para o nome da música
                    else:
                        # Os restantes ganham novos IDs únicos na base de dados para serem geríveis na Interface
                        fake_id = f"{youtube_id}_c{idx}"
                        self._inserir_capitulo_db(playlist_id, fake_id, titulo_cap, final_filepath)
                        
            else:
                # === MODO NORMAL (VÍDEO ÚNICO CONTÍNUO) ===
                titulo_bruto = info.get('title', youtube_id)
                titulo_seguro = re.sub(r'[^\w\-_\. ]', '_', titulo_bruto)
                titulo_seguro = re.sub(r'_+', '_', titulo_seguro).strip('_ ')
                
                final_filename = f"{titulo_seguro}.mp4"
                temp_conv = os.path.join(self.temp_dir, f"{youtube_id}_conv.mp4")
                final_filepath = os.path.join(destino_final_dir, final_filename)
                
                self._converter_video(raw_filepath, temp_conv)
                shutil.move(temp_conv, final_filepath)
                
                self._atualizar_status_db(youtube_id, "convertido", final_filepath)
                
            # Limpeza Bruta SSD após extrair tudo
            if os.path.exists(raw_filepath):
                os.remove(raw_filepath)

        except (subprocess.CalledProcessError, Exception) as e:
            print(f"[Engine] Falha ao converter {youtube_id}: {str(e)}")
            if os.path.exists(raw_filepath):
                os.remove(raw_filepath)
            self._incrementar_erro(youtube_id)

    def _converter_video(self, input_path: str, output_path: str, start_time=None, end_time=None):
        cmd = [self.ffmpeg_path, "-y", "-i", input_path]
        
        # INJEÇÃO DE CORTES: Aplicado após o input para precisão absoluta e fiabilidade nos frames
        if start_time is not None:
            cmd.extend(["-ss", str(start_time)])
        if end_time is not None:
            cmd.extend(["-to", str(end_time)])
            
        cmd.extend([
            "-c:v", "mpeg4",          
            "-b:v", "768k",           # VBR: Bitrate médio para poupar espaço
            "-maxrate", "1500k",      # VBR: Limite máximo para impedir quadrados
            "-bufsize", "1500k",      
            "-s", "320x240",          
            "-aspect", "4:3",         
            "-r", "30",               
            "-c:a", "aac",            
            "-b:a", "128k",           
            "-ac", "2",               
            output_path
        ])
        
        creationflags = 0
        if platform.system() == "Windows":
            creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000)
            
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=creationflags)

    def _atualizar_status_db(self, youtube_id: str, status: str, caminho: str = None):
        with self.db.get_connection() as conn:
            if caminho:
                conn.execute("UPDATE videos SET status = ?, caminho_ficheiro = ? WHERE youtube_id = ?", (status, caminho, youtube_id))
            else:
                conn.execute("UPDATE videos SET status = ? WHERE youtube_id = ?", (status, youtube_id))
            conn.commit()

    def _atualizar_titulo_db(self, youtube_id: str, novo_titulo: str):
        """Atualiza o título na DB (útil quando um vídeo longo vira apenas a Faixa 1)"""
        with self.db.get_connection() as conn:
            conn.execute("UPDATE videos SET titulo = ? WHERE youtube_id = ?", (novo_titulo, youtube_id))
            conn.commit()

    def _inserir_capitulo_db(self, playlist_id: int, youtube_id: str, titulo: str, caminho: str):
        """Cria registos isolados para as faixas 2, 3, 4... de forma a surgirem na Interface"""
        with self.db.get_connection() as conn:
            conn.execute("""
                INSERT INTO videos (playlist_id, youtube_id, titulo, caminho_ficheiro, status)
                VALUES (?, ?, ?, ?, 'convertido')
            """, (playlist_id, youtube_id, titulo, caminho))
            conn.commit()

    def _incrementar_erro(self, youtube_id: str):
        with self.db.get_connection() as conn:
            conn.execute("UPDATE videos SET status = 'erro', tentativas = tentativas + 1 WHERE youtube_id = ?", (youtube_id,))
            conn.commit()

    def _gerar_capitulos_por_silencio(self, filepath: str, duracao_total: float) -> list:
        """Usa o FFmpeg para mapear cortes por silêncio e devolve uma lista no formato dos capítulos do yt-dlp."""
        cmd = [
            self.ffmpeg_path, "-i", filepath,
            "-af", "silencedetect=noise=-30dB:d=2", # O padrão exato de 2.0 segundos que pediu!
            "-f", "null", "-"
        ]
        
        creationflags = getattr(subprocess, 'CREATE_NO_WINDOW', 0x08000000) if platform.system() == "Windows" else 0
        
        # O FFmpeg envia o relatório de silêncio para o stderr
        result = subprocess.run(cmd, stderr=subprocess.PIPE, text=True, creationflags=creationflags)
        
        capitulos_virtuais = []
        pontos_corte = [0.0] # Começa no segundo 0
        
        # Lê o relatório e extrai os tempos onde a música volta (silence_end)
        for linha in result.stderr.split('\n'):
            if "silence_end" in linha:
                match = re.search(r'silence_end: ([\d\.]+)', linha)
                if match:
                    tempo_corte = float(match.group(1))
                    pontos_corte.append(tempo_corte)
        
        pontos_corte.append(duracao_total) # Fim do vídeo
        
        # Constrói os capítulos filtrando pedaços com menos de 60 segundos
        for i in range(len(pontos_corte) - 1):
            start = pontos_corte[i]
            end = pontos_corte[i+1]
            duracao_faixa = end - start
            
            if duracao_faixa > 60.0:
                # Removemos o "Faixa X" daqui porque o main já coloca o "01 - " no início do ficheiro
                capitulos_virtuais.append({
                    'start_time': start,
                    'end_time': end,
                    # NOME FINAL: "Titulo do Vídeo - Canal [ID]"
                    'title': f"{titulo_original} - {canal_original} [{youtube_id}]"
                })
                
        return capitulos_virtuais