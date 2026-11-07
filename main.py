import os
import sys
import tempfile
import platform
import threading
import shutil
import urllib.request
import json
from tkinter import filedialog, messagebox

# --- SISTEMA DE AUTO-UPDATE DINÂMICO DO YT-DLP ---
# Cria uma pasta oculta no diretório do utilizador (C:\Users\Nome\.yt-car-sync)
USER_DATA_DIR = os.path.join(os.path.expanduser("~"), ".yt-car-sync")
os.makedirs(USER_DATA_DIR, exist_ok=True)
YTDLP_ZIP_PATH = os.path.join(USER_DATA_DIR, "yt-dlp.zip")

# Se a atualização já tiver sido baixada, força o programa a ler o ficheiro novo PRIMEIRO
if os.path.exists(YTDLP_ZIP_PATH):
    sys.path.insert(0, YTDLP_ZIP_PATH)

# Agora, o import puxará a versão do ZIP se existir, ou o fallback do .exe original
import yt_dlp
import customtkinter as ctk

# Importação dos módulos anteriores (comente/ajuste conforme necessário para testar a UI primeiro)
from database import DatabaseManager
from youtube_parser import InputParser, YTDLPConfigurator
from engine import MediaEngine
from sync_engine import SyncEngine
from manager_ui import GerenciadorColecoesUI
from sync_engine import SyncEngine # Certifique-se de que está importado

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
        self.geometry("900x700")

        self.cancelar_flag = False
        # Grid Principal: Colunas divididas igualmente, Linha 0 expande, Linha 1 fixa
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)  # <-- Nova linha fixa para o rodapé

        self.db = None
        self._build_ui()
        self._verificar_atualizacao_pendente()

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

    def _abrir_gerenciador(self):
        """Abre a janela de gestão de coleções e passa as instâncias necessárias."""
        if not self.caminho_pendrive or not hasattr(self, 'db'):
            return
            
        sync_eng = SyncEngine(self.db)
        
        # Inicia a janela
        janela = GerenciadorColecoesUI(self, self.db, sync_eng, self.caminho_pendrive)
        
        # NOVO GATILHO: Pausa a janela principal até o Gestor ser fechado, depois recarrega a UI
        self.wait_window(janela)
        self._atualizar_ui_apos_media()

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
        
        # --- CORREÇÃO DA CONTAMINAÇÃO CRUZADA ---
        if os.path.exists(self.db_master_path):
            # Se o pendrive já tem um DB (Master), sobrepõe o Slave local
            shutil.copy2(self.db_master_path, db_slave_path)
        else:
            # Se o pendrive é virgem, OBRIGATORIAMENTE apagamos o Slave local antigo
            if os.path.exists(db_slave_path):
                try:
                    os.remove(db_slave_path)
                except OSError:
                    pass
        # ----------------------------------------
            
        # Instancia o gestor apontando para o SSD local
        # Se os.remove foi chamado, ele criará um ficheiro em branco automaticamente
        self.db = DatabaseManager(db_path=db_slave_path)
        
        self._atualizar_ui_apos_media()

    def _atualizar_ui_apos_media(self):
        """Desbloqueia os controlos da coleção após o DB do pendrive ser carregado."""
        self.placeholder_colecao = "Digite o nome de uma nova coleção..."
        colecoes = self._carregar_colecoes()
        valores = colecoes if colecoes else [self.placeholder_colecao]
        
        self.nome_colecao.configure(state="normal", values=valores)
        self.btn_gerenciar.configure(state="normal") # Desbloqueia o gerenciador
        
        if colecoes:
            self.nome_colecao.set(colecoes[0])
            self._ao_selecionar_colecao(colecoes[0])
        else:
            self.nome_colecao.set(self.placeholder_colecao)

    def _selecionar_tudo_links(self, event=None):
        """Seleciona todo o texto na caixa de entrada de links usando Ctrl+A."""
        self.textbox_links.tag_add("sel", "1.0", "end")
        return "break"

    def _build_ui(self):
        # ================= PAINEL ESQUERDO: CONTROLOS =================
        self.frame_esq = ctk.CTkFrame(self)
        self.frame_esq.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # --- SELEÇÃO DE MÍDIA / PENDRIVE ---
        self.frame_media = ctk.CTkFrame(self.frame_esq, fg_color="transparent")
        self.frame_media.pack(pady=(0, 10), fill="x")
        
        ctk.CTkLabel(self.frame_media, text="Mídia de Destino (Pendrive)", font=("Roboto", 16, "bold")).pack(pady=(5, 2))
        
        self.caminho_pendrive = None
        self.lbl_caminho = ctk.CTkLabel(self.frame_media, text="Nenhuma mídia selecionada", text_color="orange")
        self.lbl_caminho.pack(pady=2)
        
        self.btn_selecionar_media = ctk.CTkButton(self.frame_media, text="Procurar Pendrive...", command=self._selecionar_media)
        self.btn_selecionar_media.pack(pady=5)
        
        ctk.CTkFrame(self.frame_esq, height=2, fg_color="gray30").pack(fill="x", pady=5) # Linha divisória

        # Botão para abrir o gerenciador (Inicia desativado até o pendrive ser selecionado)
        self.btn_gerenciar = ctk.CTkButton(
            self.frame_esq, 
            text="Gerenciar Coleções...", 
            fg_color="#4B5563", hover_color="#374151", # Cinza
            command=self._abrir_gerenciador,
            state="disabled"
        )
        self.btn_gerenciar.pack(pady=(5, 15), fill="x", padx=20)
        
        # --- CONFIGURAÇÃO DA COLEÇÃO ---
        ctk.CTkLabel(self.frame_esq, text="Configuração da Coleção", font=("Roboto", 16, "bold")).pack(pady=(10, 5))
        
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

        self.lbl_dica = ctk.CTkLabel(
            self.frame_esq, 
            text="💡 Dica: Selecione uma coleção ou escreva para criar nova.", 
            font=("Roboto", 11), 
            text_color="gray"
        )
        self.lbl_dica.pack(pady=(0, 5))

        self.modo_sincronia = ctk.CTkSegmentedButton(self.frame_esq, values=["Incremental", "Estrito"])
        self.modo_sincronia.pack(pady=10)
        self.modo_ordem = ctk.CTkSegmentedButton(self.frame_esq, values=["Aleatório", "Ordenado"])
        self.modo_ordem.pack(pady=10)

        self.modo_sincronia.set("Incremental") 
        self.modo_ordem.set("Aleatório")

        try:
            self.nome_colecao._entry.bind("<FocusIn>", self._ao_focar_combobox)
        except AttributeError:
            pass

        self.timer_dica = self.after(6000, self._remover_dica)

        # --- LINKS E REGRAS ---
        # Cria um mini-container para alinhar o título e o botão lado a lado
        self.frame_links_header = ctk.CTkFrame(self.frame_esq, fg_color="transparent")
        self.frame_links_header.pack(pady=(15, 0), fill="x", padx=20)

        ctk.CTkLabel(self.frame_links_header, text="Links (Vídeos ou Playlists)", font=("Roboto", 14)).pack(side="left")

        self.btn_limpar_links = ctk.CTkButton(
            self.frame_links_header, 
            text="Limpar", 
            width=60, 
            height=24,
            fg_color="#4B5563", hover_color="#374151", 
            command=lambda: self.textbox_links.delete("1.0", "end")
        )
        self.btn_limpar_links.pack(side="right")
        
        # Altura reduzida de 150 para 110 para evitar empurrar a checkbox para fora da janela
        self.textbox_links = ctk.CTkTextbox(self.frame_esq, height=110, width=300)
        self.textbox_links.pack(pady=5)

        # Habilita o Ctrl+A (tanto em minúsculo quanto maiúsculo/Caps Lock)
        self.textbox_links.bind("<Control-a>", self._selecionar_tudo_links)
        self.textbox_links.bind("<Control-A>", self._selecionar_tudo_links)

        self.check_ignorar_playlist = ctk.CTkCheckBox(self.frame_esq, text="Ignorar Playlists (Apenas Vídeo)")
        self.check_ignorar_playlist.set(True)
        self.check_ignorar_playlist.pack(pady=5) # Reduzido o espaçamento (pady) para poupar espaço vertical

        # --- NOVO BOTÃO DE IA DE SILÊNCIO COM SELETOR ---
        self.frame_ia = ctk.CTkFrame(self.frame_esq, fg_color="transparent")
        self.frame_ia.pack(pady=5, fill="x", padx=20)
        
        self.check_corte_cego = ctk.CTkCheckBox(self.frame_ia, text="✂️ Corte Cego (Sem Capítulos)")
        self.check_corte_cego.set(False)
        self.check_corte_cego.pack(side="left")
        
        self.combo_silencio = ctk.CTkComboBox(
            self.frame_ia, 
            values=["1s (Agressivo)", "2s (Padrão)", "3s (Seguro)"], 
            width=110
        )
        self.combo_silencio.set("2s (Padrão)")
        self.combo_silencio.pack(side="right")

        # ================= PAINEL DIREITO: LOGS E STATUS =================
        self.frame_dir = ctk.CTkFrame(self)
        self.frame_dir.grid(row=0, column=1, padx=10, pady=10, sticky="nsew")
        
        # Mini-container para o Título e o Botão de Update
        self.frame_dir_header = ctk.CTkFrame(self.frame_dir, fg_color="transparent")
        self.frame_dir_header.pack(fill="x", padx=10, pady=(10, 5))
        
        ctk.CTkLabel(self.frame_dir_header, text="Console de Processamento", font=("Roboto", 16, "bold")).pack(side="left")
        
        self.btn_update_motor = ctk.CTkButton(
            self.frame_dir_header, 
            text="Atualizar yt-dlp", 
            width=100, height=24,
            fg_color="#059669", hover_color="#047857", # Verde
            command=self._baixar_atualizacao_motor
        )
        self.btn_update_motor.pack(side="right")
        
        self.console_log = ctk.CTkTextbox(self.frame_dir, state="disabled")
        self.console_log.pack(expand=True, fill="both", padx=10, pady=10)

        # ================= RODAPÉ FIXO (LINHA 1): BARRA + BOTÃO =================
        self.frame_rodape = ctk.CTkFrame(self, fg_color="transparent")
        self.frame_rodape.grid(row=1, column=0, columnspan=2, padx=10, pady=(0, 10), sticky="ew")
        
        self.frame_rodape.grid_columnconfigure(0, weight=1)
        self.frame_rodape.grid_columnconfigure(1, weight=0)

        # Barra de Progresso mais grossa (height=28 acompanha o botão)
        self.progress_bar = ctk.CTkProgressBar(self.frame_rodape, height=28)
        self.progress_bar.grid(row=0, column=0, padx=(0, 10), sticky="ew")
        self.progress_bar.set(0) # Usa int '0' estrito em vez de '0.0' para evitar o fragmento visual

        self.btn_iniciar = ctk.CTkButton(
            self.frame_rodape, 
            text="Iniciar Sincronização", 
            command=self.iniciar_processo_thread, 
            fg_color="green", 
            hover_color="darkgreen",
            width=180,
            height=28 # Fixado para igualar a barra
        )
        self.btn_iniciar.grid(row=0, column=1, sticky="e")

    def _baixar_atualizacao_motor(self):
        """Baixa a última versão compilada do motor do YouTube diretamente do GitHub."""
        def tarefa():
            self.btn_update_motor.configure(state="disabled", text="A transferir...")
            self.log("[*] A ligar aos servidores do GitHub para descarregar a última versão do yt-dlp...")
            try:
                # Link oficial (always points to the latest zipapp release)
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp"
                urllib.request.urlretrieve(url, YTDLP_ZIP_PATH)
                
                self.log("[+] Motor atualizado com sucesso! O novo ficheiro foi guardado no SSD.")
                messagebox.showinfo(
                    "Atualização Concluída", 
                    "O motor de extração do YouTube foi atualizado com sucesso!\n\nPor favor, feche e abra o programa novamente para que o novo motor entre em funcionamento."
                )
            except Exception as e:
                self.log(f"[!] Erro ao atualizar o motor: {str(e)}")
            finally:
                self.btn_update_motor.configure(state="normal", text="Atualizar yt-dlp")
                
        threading.Thread(target=tarefa, daemon=True).start()

    def _verificar_atualizacao_pendente(self):
        """Verifica silenciosamente na API do GitHub se o yt-dlp tem uma versão mais recente."""
        def tarefa():
            try:
                # Obtém a versão local atual carregada na memória
                versao_local = yt_dlp.version.__version__
                #versao_local = "2000.01.01"  # FORÇANDO UMA VERSÃO MUITO ANTIGA PARA TESTE
                
                # Consulta a última versão lançada no GitHub
                req = urllib.request.Request("https://api.github.com/repos/yt-dlp/yt-dlp/releases/latest")
                req.add_header("User-Agent", "YT-Car-Sync-App")
                
                with urllib.request.urlopen(req, timeout=5) as response:
                    dados = json.loads(response.read().decode())
                    versao_remota = dados.get("tag_name", "").replace("v", "")
                
                # Compara as versões (ex: "2024.04.09" < "2024.07.16")
                if versao_remota and versao_remota > versao_local:
                    # Atualiza a UI informando o utilizador (usando .after por estarmos numa thread)
                    self.after(0, lambda: self.btn_update_motor.configure(
                        text="⚠️ Update yt-dlp Disponível!", 
                        fg_color="#D97706", # Laranja de alerta
                        hover_color="#B45309"
                    ))
            except Exception:
                # Se estiver sem internet ou o GitHub bloquear temporariamente, falha em silêncio.
                # Não atrapalha a experiência do utilizador.
                pass

        threading.Thread(target=tarefa, daemon=True).start()
    
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

        if not self.caminho_pendrive:
            messagebox.showwarning("Aviso", "Selecione o Pendrive de destino primeiro.")
            return

        if not colecao or colecao == getattr(self, 'placeholder_colecao', ""):
            messagebox.showwarning("Aviso", "Preencha o nome da coleção.")
            return

        # NOVO: Busca fontes na base de dados se a caixa de links estiver vazia
        if not links_brutos:
            with self.db.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT p.url FROM playlists p
                    JOIN colecoes c ON p.colecao_id = c.id
                    WHERE c.nome = ?
                """, (colecao,))
                urls_salvas = cursor.fetchall()
                
            if urls_salvas:
                links_brutos = "\n".join([row['url'] for row in urls_salvas])
                self.textbox_links.insert("end", links_brutos) # Dá feedback visual ao utilizador
            else:
                messagebox.showwarning("Aviso", "Insira pelo menos um link ou selecione uma coleção que já tenha fontes salvas.")
                return

        self.progress_bar.set(0)
        self.cancelar_flag = False
        
        self.btn_iniciar.configure(
            text="Cancelar Operação", 
            command=self._cancelar_operacao, 
            fg_color="#EF4444", hover_color="#DC2626"
        )
        
        thread = threading.Thread(target=self.fluxo_principal, args=(colecao, links_brutos), daemon=True)
        thread.start()

    def _cancelar_operacao(self):
        """Ativa a flag de cancelamento e atualiza o estado do botão na UI."""
        self.cancelar_flag = True
        self.btn_iniciar.configure(state="disabled", text="A cancelar (Aguarde o vídeo atual)...")
        self.log("[!] Pedido de cancelamento recebido. A interromper fila...")

    def fluxo_principal(self, colecao: str, links_brutos: str):
        sucesso_total = False # Flag para rastrear se houve falhas críticas
        """Método executado em background que orquestra todos os módulos."""
        try:
            self.log(f"[*] A iniciar a coleção '{colecao}'...")
            
            # Lógica para capturar as preferências da UI
            ignorar_pl = self.check_ignorar_playlist.get() == 1
            sincronia = self.modo_sincronia.get().lower()
            ordem = self.modo_ordem.get().lower().replace("aleatório", "aleatorio")

            forcar_corte_cego = self.check_corte_cego.get() == 1
            
            # NOVO: Extrai apenas o número (1, 2 ou 3) da string selecionada
            segundos_silencio = int(self.combo_silencio.get().split("s")[0])

            # CORREÇÃO: Usar a base de dados ativa carregada na memória (SSD Slave)
            db = self.db
            
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
                if self.cancelar_flag: break
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
                    try: # NOVO: Bloco try para proteger contra metadados corrompidos (ex: VEVO)
                        info = ydl.extract_info(url, download=False)
                        if not info: continue
                        entradas = info.get('entries', [info]) if 'entries' in info else [info]
                        
                        with db.get_connection() as conn:
                            videos_lote = []
                            for entry in entradas:
                                if self.cancelar_flag: break
                                if not entry or not entry.get('id'): continue
                                
                                video_id = entry['id']
                                titulo = entry.get('title', video_id)
                                videos_lote.append((playlist_id, video_id, titulo, 'pendente'))
                                
                            if videos_lote:
                                conn.executemany("""
                                    INSERT OR IGNORE INTO videos (playlist_id, youtube_id, titulo, status)
                                    VALUES (?, ?, ?, ?)
                                """, videos_lote)
                            conn.commit()
                            
                    except Exception as e:
                        # Se o YouTube atirar um NoneType aqui, ignoramos o link e continuamos a construir a lista!
                        self.log(f"   [!] Aviso: Não foi possível ler os metadados de '{url}'. A ignorar fonte...")
                        continue

            # 4. Processamento dos Ficheiros Físicos
            archive_path = os.path.join(tempfile.gettempdir(), f"archive_{colecao_id}.txt")
            db.exportar_download_archive(archive_path)
            opts = YTDLPConfigurator.get_base_options(archive_path)

            with db.get_connection() as conn:
                cursor = conn.cursor()
                # NOVO: Conta quantos foram ignorados definitivamente
                cursor.execute("""
                    SELECT COUNT(*) as ignorados FROM videos v
                    JOIN playlists p ON v.playlist_id = p.id
                    WHERE p.colecao_id = ? AND v.status = 'erro' AND v.tentativas >= 3
                """, (colecao_id,))
                ignorados_definitivos = cursor.fetchone()['ignorados']
                
                if ignorados_definitivos > 0:
                    self.log(f"[*] {ignorados_definitivos} vídeo(s) com falha crítica omitido(s) da fila (Limite de 3 tentativas).")

                # NOVO: Filtra pendentes ou erros com menos de 3 tentativas
                cursor.execute("""
                    SELECT v.* FROM videos v
                    JOIN playlists p ON v.playlist_id = p.id
                    WHERE p.colecao_id = ? AND (v.status = 'pendente' OR (v.status = 'erro' AND v.tentativas < 3))
                """, (colecao_id,))
                pendentes = cursor.fetchall()

            pasta_destino = os.path.join(self.caminho_pendrive, colecao)

            if pendentes:
                total_videos = len(pendentes)
                self.log(f"[*] A processar {total_videos} vídeo(s)...")
                for idx, video in enumerate(pendentes):
                    if self.cancelar_flag: # <-- Verificação 3: Quebra da fila de conversão
                        self.log("[-] Operação abortada pelo utilizador. Os vídeos restantes ficarão pendentes.")
                        break
                    
                    self.log(f" -> [{idx+1}/{total_videos}] A descarregar e converter: {video['youtube_id']}")
                    media_engine.process_video(video, opts, pasta_destino, forcar_corte_cego, segundos_silencio)
                    
                    progresso = (idx + 1) / total_videos
                    self.after(0, lambda p=progresso: self.progress_bar.set(p))
            else:
                self.log("[+] Não há novos vídeos para processar.")
                self.after(0, lambda: self.progress_bar.set(1.0)) # Enche a barra a 100%

            # 5. Motor de Sincronia
            self.log("[*] A aplicar regras de ordem cronológica e sincronia física...")
            sync_engine.executar_sincronia_colecao(colecao_id, pasta_destino)

            self.log("[+] Operação concluída com sucesso!")
            sucesso_total = True # Marca como sucesso
            
        except Exception as e:
            self.log(f"[!] ERRO CRÍTICO: {str(e)}")
        finally:
            # 1. Grava as alterações de volta para o Pendrive
            try:
                if hasattr(self, 'db_master_path') and self.db_master_path:
                    import shutil
                    shutil.copy2(db.db_path, self.db_master_path)
                    self.log("[+] DB sincronizado com pendrive.")
            except Exception as e:
                self.log(f"[!] Erro ao guardar DB: {str(e)}")
                
            # 2. Desbloqueia a interface e exibe o status de conclusão
            def restaurar_ui():
                self.btn_iniciar.configure(state="normal", command=self.iniciar_processo_thread)
                
                if self.cancelar_flag:
                    self.btn_iniciar.configure(text="Operação Cancelada", fg_color="#D97706") # Laranja
                elif sucesso_total:
                    self.btn_iniciar.configure(text="Concluído! ✔️", fg_color="darkgreen")
                    self.progress_bar.set(1.0)
                    self.textbox_links.delete("1.0", "end") # UX: Limpa os links
                    
                    # --- NOVO: RELATÓRIO FINAL POP-UP ---
                    with db.get_connection() as conn:
                        sucessos = conn.execute("SELECT COUNT(*) FROM videos v JOIN playlists p ON v.playlist_id = p.id WHERE p.colecao_id = ? AND v.status = 'convertido'", (colecao_id,)).fetchone()[0]
                        erros = conn.execute("SELECT COUNT(*) FROM videos v JOIN playlists p ON v.playlist_id = p.id WHERE p.colecao_id = ? AND v.status = 'erro'", (colecao_id,)).fetchone()[0]
                    messagebox.showinfo("Sincronização Finalizada!", f"✔️ {sucessos} músicas/vídeos prontos no Pendrive.\n❌ {erros} falhas (Verifique o log).")
                    # ------------------------------------
                else:
                    self.btn_iniciar.configure(text="Erro. Tentar Novamente", fg_color="#8B0000")
                
                # --- CORREÇÃO AQUI: REFRESH GARANTIDO ---
                # 1. Força a UI a reprocessar as listas a partir da BD
                self._atualizar_ui_apos_media()
                
                # 2. Volta a selecionar a coleção que estava a ser editada
                colecoes_atualizadas = self._carregar_colecoes()
                if colecao in colecoes_atualizadas:
                    self.nome_colecao.set(colecao)
                    self._ao_selecionar_colecao(colecao)
                
                self.after(4000, lambda: self.btn_iniciar.configure(text="Iniciar Sincronização", fg_color="green"))
                
            self.after(0, restaurar_ui)
if __name__ == "__main__":
    app = YTCarSyncApp()
    app.mainloop()