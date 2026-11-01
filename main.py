import customtkinter as ctk
import threading
from tkinter import messagebox
# Importação dos módulos anteriores (comente/ajuste conforme necessário para testar a UI primeiro)
# from database import DatabaseManager
# from youtube_parser import InputParser, YTDLPConfigurator
# from engine import MediaEngine
# from sync_engine import SyncEngine

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
        # self.db = DatabaseManager()
        # self.media_engine = MediaEngine(self.db)
        # self.sync_engine = SyncEngine(self.db)

        self._build_ui()

    def _build_ui(self):
        # ================= PAINEL ESQUERDO: CONTROLOS =================
        self.frame_esq = ctk.CTkFrame(self)
        self.frame_esq.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_esq, text="Configuração da Coleção", font=("Roboto", 16, "bold")).pack(pady=(10, 5))
        
        self.nome_colecao = ctk.CTkEntry(self.frame_esq, placeholder_text="Nome da Coleção (ex: PenDrive_Carro)", width=300)
        self.nome_colecao.pack(pady=5)

        # Modos de Sincronia e Ordem (Segmented Buttons para UI limpa)
        self.modo_sincronia = ctk.CTkSegmentedButton(self.frame_esq, values=["Incremental", "Estrito"])
        self.modo_sincronia.set("Incremental")
        self.modo_sincronia.pack(pady=10)

        self.modo_ordem = ctk.CTkSegmentedButton(self.frame_esq, values=["Aleatório", "Ordenado"])
        self.modo_ordem.set("Aleatório")
        self.modo_ordem.pack(pady=10)

        ctk.CTkLabel(self.frame_esq, text="Links (Vídeos ou Playlists)", font=("Roboto", 14)).pack(pady=(15, 0))
        
        # Caixa de texto multilinha para colar links misturados
        self.textbox_links = ctk.CTkTextbox(self.frame_esq, height=150, width=300)
        self.textbox_links.pack(pady=5)

        # Regra de Negócio: UX/Input à prova de falhas
        self.check_ignorar_playlist = ctk.CTkCheckBox(self.frame_esq, text="Ignorar Playlists (Apenas Vídeo)")
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

        if not colecao or not links_brutos:
            messagebox.showwarning("Aviso", "Preencha o nome da coleção e insira pelo menos um link.")
            return

        self.btn_iniciar.configure(state="disabled", text="A processar...")
        
        # Inicia a thread de trabalho
        thread = threading.Thread(target=self.fluxo_principal, args=(colecao, links_brutos), daemon=True)
        thread.start()

    def fluxo_principal(self, colecao: str, links_brutos: str):
        """Método executado em background que orquestra todos os módulos."""
        try:
            self.log(f"[*] A iniciar coleção '{colecao}'...")
            
            ignorar_pl = self.check_ignorar_playlist.get() == 1
            sincronia = self.modo_sincronia.get().lower()
            ordem = self.modo_ordem.get().lower().replace("aleatório", "aleatorio")

            # Aqui entrará a integração real:
            # 1. db.inserir_ou_atualizar_colecao(colecao, ordem, sincronia)
            # 2. links_parseados = InputParser.extrair_e_categorizar_links(links_brutos, ignorar_pl)
            # 3. opts = YTDLPConfigurator.get_base_options()
            # 4. iterar sobre os links, invocar self.media_engine.process_video()
            # 5. self.sync_engine.executar_sincronia_colecao()
            
            self.log("[+] Parse de links concluído.")
            self.log("[+] Processamento finalizado (Simulação).")
            
        except Exception as e:
            self.log(f"[!] ERRO: {str(e)}")
        finally:
            # Restaura o botão na main thread
            self.after(0, lambda: self.btn_iniciar.configure(state="normal", text="Iniciar Sincronização"))

if __name__ == "__main__":
    app = YTCarSyncApp()
    app.mainloop()