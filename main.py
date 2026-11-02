import os
import sys
import tempfile
import yt_dlp
import platform
import customtkinter as ctk
import threading
from tkinter import messagebox
import shutil
from tkinter import filedialog
# Importação dos módulos anteriores (comente/ajuste conforme necessário para testar a UI primeiro)
from database import DatabaseManager
from youtube_parser import InputParser, YTDLPConfigurator
from engine import MediaEngine
from sync_engine import SyncEngine

def get_resource_path(relative_path):
    """Obtém o caminho absoluto para recursos, compatível com o PyInstaller."""
    try:
        # PyInstaller cria uma pasta temporária em _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class YTCarSyncApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("YT Car Sync - Toyota Corolla 2020")
        self.geometry("900x600")
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # Configuração (Bases de Dados e Motores instanciados aqui)
        self.db = DatabaseManager()
        # self.media_engine = MediaEngine(self.db)
        # self.sync_engine = SyncEngine(self.db)

        self._build_ui()

    def _carregar_colecoes(self):
        """Busca os nomes das coleções já existentes no banco de dados."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT nome FROM colecoes ORDER BY nome ASC")
            return [row['nome'] for row in cursor.fetchall()]

    def _ao_selecionar_colecao(self, nome_selecionado):
        """Auto-preenche os modos de sincronia e ordem quando uma coleção existente é selecionada."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT modo_ordem, modo_sincronia FROM colecoes WHERE nome = ?", (nome_selecionado,))
            col = cursor.fetchone()
            if col:
                # Ajusta a formatação para bater com os valores exatos dos Segmented Buttons
                ordem = "Aleatório" if col['modo_ordem'] == "aleatorio" else "Ordenado"
                sincronia = col['modo_sincronia'].capitalize()
                
                self.modo_ordem.set(ordem)
                self.modo_sincronia.set(sincronia)

    def _remover_dica(self):
        """Remove o rótulo de dica da interface de forma segura."""
        if hasattr(self, 'lbl_dica') and self.lbl_dica:
            try:
                self.lbl_dica.pack_forget()
                self.lbl_dica.destroy()
                self.lbl_dica = None
            except Exception:
                pass

    def _ao_focar_combobox(self, event):
        """Limpa o texto do combobox automaticamente se contiver o placeholder ao focar."""
        valor_atual = self.nome_colecao.get()
        if valor_atual == getattr(self, 'placeholder_colecao', ""):
            self.nome_colecao.set("")
        self._remover_dica()

    def _selecionar_media(self):
        """Abre o seletor, define o destino e inicializa a base de dados (Master/Slave)."""
        diretorio = filedialog.askdirectory(title="Selecione a raiz do Pendrive")
        if not diretorio:
            return
            
        self.caminho_pendrive = diretorio
        self.lbl_caminho.configure(text=self.caminho_pendrive, text_color="white")
        
        # Cria a pasta oculta de sistema no pendrive para o DB
        db_folder_usb = os.path.join(self.caminho_pendrive, ".yt-car-sync")
        os.makedirs(db_folder_usb, exist_ok=True)
        
        self.db_master_path = os.path.join(db_folder_usb, "database.db")
        db_slave_path = os.path.join(tempfile.gettempdir(), "yt_car_sync_temp.db")
        
        # Se o pendrive já tiver um DB (Master), copia para o local (Slave)
        if os.path.exists(self.db_master_path):
            shutil.copy2(self.db_master_path, db_slave_path)
            
        # Instancia o gestor apontando para a cópia ultra-rápida no SSD local
        self.db = DatabaseManager(db_path=db_slave_path)
        
        self._atualizar_ui_apos_media()

    def _atualizar_ui_apos_media(self):
        """Desbloqueia os controlos da coleção após o DB do pendrive ser carregado."""
        self.placeholder_colecao = "Digite o nome de uma nova coleção..."
        colecoes = self._carregar_colecoes()
        valores = colecoes if colecoes else [self.placeholder_colecao]
        
        self.nome_colecao.configure(state="normal", values=valores)
        
        if colecoes:
            self.nome_colecao.set(colecoes[0])
            self._ao_selecionar_colecao(colecoes[0])
        else:
            self.nome_colecao.set(self.placeholder_colecao)

    def _build_ui(self):
        # ================= PAINEL ESQUERDO: CONTROLOS =================
        self.frame_esq = ctk.CTkFrame(self)
        self.frame_esq.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # --- NOVO: SELEÇÃO DE MÍDIA / PENDRIVE ---
        self.frame_media = ctk.CTkFrame(self.frame_esq, fg_color="transparent")
        self.frame_media.pack(pady=(0, 10), fill="x")
        
        ctk.CTkLabel(self.frame_media, text="Mídia de Destino (Pendrive)", font=("Roboto", 16, "bold")).pack(pady=(5, 2))
        
        self.caminho_pendrive = None
        self.lbl_caminho = ctk.CTkLabel(self.frame_media, text="Nenhuma mídia selecionada", text_color="orange")
        self.lbl_caminho.pack(pady=2)
        
        self.btn_selecionar_media = ctk.CTkButton(self.frame_media, text="Procurar Pendrive...", command=self._selecionar_media)
        self.btn_selecionar_media.pack(pady=5)
        
        ctk.CTkFrame(self.frame_esq, height=2, fg_color="gray30").pack(fill="x", pady=5) # Linha divisória
        # ----------------------------------------
        
        ctk.CTkLabel(self.frame_esq, text="Configuração da Coleção", font=("Roboto", 16, "bold")).pack(pady=(10, 5))
        
        # A caixa de coleções inicia bloqueada e vazia até o DB do pendrive ser lido
        self.placeholder_colecao = "Selecione a mídia primeiro..."
        self.nome_colecao = ctk.CTkComboBox(
            self.frame_esq, 
            values=[self.placeholder_colecao], 
            width=300,
            command=self._ao_selecionar_colecao,
            state="disabled" 
        )
        self.nome_colecao.set(self.placeholder_colecao)
        self.nome_colecao.pack(pady=5)

        # --- DICA TEMPORÁRIA ABAIXO DA CAIXA ---
        self.lbl_dica = ctk.CTkLabel(
            self.frame_esq, 
            text="💡 Dica: Selecione uma coleção ou escreva para criar nova.", 
            font=("Roboto", 11), 
            text_color="gray"
        )
        self.lbl_dica.pack(pady=(0, 5))
        
        # 1. CRIAR PRIMEIRO OS BOTÕES (Para que existam na memória)
        self.modo_sincronia = ctk.CTkSegmentedButton(self.frame_esq, values=["Incremental", "Estrito"])
        self.modo_sincronia.pack(pady=10)

        self.modo_ordem = ctk.CTkSegmentedButton(self.frame_esq, values=["Aleatório", "Ordenado"])
        self.modo_ordem.pack(pady=10)

        # 2. DEFINIR OS VALORES PADRÃO 
        # (Não tentamos ler as coleções aqui porque o utilizador ainda não escolheu o pendrive)
        self.modo_sincronia.set("Incremental") 
        self.modo_ordem.set("Aleatório")


        try:
            self.nome_colecao._entry.bind("<FocusIn>", self._ao_focar_combobox)
        except AttributeError:
            pass

        self.timer_dica = self.after(6000, self._remover_dica)
        # ----------------------------------------

        ctk.CTkLabel(self.frame_esq, text="Links (Vídeos ou Playlists)", font=("Roboto", 14)).pack(pady=(15, 0))
        
        # Caixa de texto multilinha para colar links misturados
        self.textbox_links = ctk.CTkTextbox(self.frame_esq, height=150, width=300)
        self.textbox_links.pack(pady=5)

        # Regra de Negócio: UX/Input à prova de falhas
        self.check_ignorar_playlist = ctk.CTkCheckBox(self.frame_esq, text="Ignorar Playlists (Apenas Vídeo)")
        self.check_ignorar_playlist.set(True)
        self.check_ignorar_playlist.pack(pady=10)

        self.btn_iniciar = ctk.CTkButton(self.frame_esq, text="Iniciar Sincronização", command=self.iniciar_processo_thread, fg_color="green", hover_color="darkgreen")
        self.btn_iniciar.pack(pady=20)

        # ================= PAINEL DIREITO: LOGS E STATUS =================
        self.frame_dir = ctk.CTkFrame(self)
        self.frame_dir.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_dir, text="Console de Processamento", font=("Roboto", 16, "bold")).pack(pady=(10, 5))
        
        self.console_log = ctk.CTkTextbox(self.frame_dir, state="disabled")
        self.console_log.pack(expand=True, fill="both", padx=10, pady=10)

    def log(self, mensagem: str):
        """Injeta mensagens no console da interface de forma thread-safe."""
        self.console_log.configure(state="normal")
        self.console_log.insert("end", mensagem + "\n")
        self.console_log.see("end")
        self.console_log.configure(state="disabled")

    def iniciar_processo_thread(self):
        """Inicia a sincronização numa thread paralela para não bloquear a GUI."""
        colecao = self.nome_colecao.get().strip()
        links_brutos = self.textbox_links.get("1.0", "end").strip()

        # Impede que o placeholder seja usado como nome de coleção válido
        if not colecao or colecao == getattr(self, 'placeholder_colecao', "") or not links_brutos:
            messagebox.showwarning("Aviso", "Preencha o nome da coleção e insira pelo menos um link.")
            return

        if not self.caminho_pendrive:
            messagebox.showwarning("Aviso", "Selecione o Pendrive de destino primeiro.")
            return

        self.btn_iniciar.configure(state="disabled", text="A processar...")
        
        # Inicia a thread de trabalho
        thread = threading.Thread(target=self.fluxo_principal, args=(colecao, links_brutos), daemon=True)
        thread.start()

    def fluxo_principal(self, colecao: str, links_brutos: str):
        """Método executado em background que orquestra todos os módulos."""
        try:
            self.log(f"[*] A iniciar a coleção '{colecao}'...")
            
            ignorar_pl = self.check_ignorar_playlist.get() == 1
            sincronia = self.modo_sincronia.get().lower()
            ordem = self.modo_ordem.get().lower().replace("aleatório", "aleatorio")

            # Instanciar os motores (com caminho resolvido dinamicamente para o binário)
            db = DatabaseManager()
            
            # Deteta automaticamente se é Windows (.exe) ou Linux
            nome_binario = "ffmpeg.exe" if platform.system() == "Windows" else "ffmpeg"
            ffmpeg_path = get_resource_path(os.path.join("bin", nome_binario)) 
            
            media_engine = MediaEngine(db, ffmpeg_path=ffmpeg_path)
            sync_engine = SyncEngine(db)

            # 1. Base de Dados: Registar ou Atualizar Coleção
            with db.get_connection() as conn:
                cursor = conn.cursor()
                # Insere ou atualiza as regras caso a coleção já exista
                cursor.execute("""
                    INSERT INTO colecoes (nome, modo_ordem, modo_sincronia) 
                    VALUES (?, ?, ?) 
                    ON CONFLICT(nome) DO UPDATE SET 
                    modo_ordem=excluded.modo_ordem, modo_sincronia=excluded.modo_sincronia
                """, (colecao, ordem, sincronia))
                cursor.execute("SELECT id FROM colecoes WHERE nome = ?", (colecao,))
                colecao_id = cursor.fetchone()['id']
                conn.commit()

            # 2. Parse dos Links
            links_parseados = InputParser.extrair_e_categorizar_links(links_brutos, ignorar_pl)
            self.log(f"[+] {len(links_parseados)} link(s) base identificado(s). A extrair metadados web...")

            # 3. Resolução de Playlists e Inserção de Vídeos Pendentes
            for item in links_parseados:
                url = item['url']
                with db.get_connection() as conn:
                    cursor = conn.cursor()
                    cursor.execute("INSERT OR IGNORE INTO playlists (colecao_id, url) VALUES (?, ?)", (colecao_id, url))
                    cursor.execute("SELECT id FROM playlists WHERE url = ?", (url,))
                    playlist_id = cursor.fetchone()['id']
                    conn.commit()

                # Extrair metadados sem descarregar os ficheiros físicos (modo flat)
                ext_opts = {
                    'extract_flat': True, 
                    'quiet': True, 
                    'no_warnings': True, 
                    'ignoreerrors': True,
                    'noplaylist': item['noplaylist']  # Correção: Injeção dinâmica da flag
                }
                
                with yt_dlp.YoutubeDL(ext_opts) as ydl:
                    info = ydl.extract_info(url, download=False)
                    if not info:
                        continue
                    
                    entradas = info.get('entries', [info]) if 'entries' in info else [info]
                    
                    with db.get_connection() as conn:
                        for entry in entradas:
                            if not entry or not entry.get('id'):
                                continue
                            video_id = entry['id']
                            titulo = entry.get('title', video_id)
                            # Regista como pendente. O status evita redownloads automáticos futuramente.
                            conn.execute("""
                                INSERT OR IGNORE INTO videos (playlist_id, youtube_id, titulo, status)
                                VALUES (?, ?, ?, 'pendente')
                            """, (playlist_id, video_id, titulo))
                        conn.commit()

            # 4. Processamento dos Ficheiros Físicos
            archive_path = os.path.join(tempfile.gettempdir(), f"archive_{colecao_id}.txt")
            db.exportar_download_archive(archive_path)
            opts = YTDLPConfigurator.get_base_options(archive_path)

            with db.get_connection() as conn:
                cursor = conn.cursor()
                # Tenta processar pendentes ou que falharam em sessões anteriores
                cursor.execute("""
                    SELECT v.* FROM videos v
                    JOIN playlists p ON v.playlist_id = p.id
                    WHERE p.colecao_id = ? AND (v.status = 'pendente' OR v.status = 'erro')
                """, (colecao_id,))
                pendentes = cursor.fetchall()

            # Antes: pasta_destino = os.path.abspath(f"./{colecao}")
            # Agora: Aponta diretamente para o Pendrive
            pasta_destino = os.path.join(self.caminho_pendrive, colecao)

            if pendentes:
                self.log(f"[*] A processar {len(pendentes)} vídeo(s)...")
                for idx, video in enumerate(pendentes):
                    self.log(f" -> [{idx+1}/{len(pendentes)}] A descarregar e converter: {video['youtube_id']}")
                    media_engine.process_video(video, opts, pasta_destino)
            else:
                self.log("[+] Não há novos vídeos para processar.")

            # 5. Motor de Sincronia (Aleatoriedade, Limpeza e os.utime)
            self.log("[*] A aplicar regras de ordem cronológica e sincronia física...")
            sync_engine.executar_sincronia_colecao(colecao_id, pasta_destino)

            self.log("[+] Operação concluída com sucesso! Os ficheiros estão na pasta local.")
            
        except Exception as e:
            self.log(f"[!] ERRO CRÍTICO: {str(e)}")
        finally:
            # 1. Grava as alterações do SSD (Slave) de volta para o Pendrive (Master)
            try:
                if hasattr(self, 'db_master_path') and self.db_master_path:
                    shutil.copy2(self.db.db_path, self.db_master_path)
                    self.log("[+] Base de dados sincronizada com o pendrive com sucesso.")
            except Exception as e:
                self.log(f"[!] Erro ao guardar base de dados no pendrive: {str(e)}")
                
            # 2. Desbloqueia a interface apenas após concluir a cópia
            self.after(0, lambda: self.btn_iniciar.configure(state="normal", text="Iniciar Sincronização"))
if __name__ == "__main__":
    app = YTCarSyncApp()
    app.mainloop()