import customtkinter as ctk
from tkinter import messagebox
import os
import shutil

class GerenciadorColecoesUI(ctk.CTkToplevel):
    def __init__(self, master, db_manager, sync_engine, caminho_pendrive):
        super().__init__(master)
        self.title("Gerenciador de Coleções - YT Car Sync")
        self.geometry("850x550")
        self.minsize(800, 500)
        
        # Garante que a janela fique no topo da principal
        self.transient(master)
        self.grab_set()

        self.db = db_manager
        self.sync_engine = sync_engine
        self.caminho_pendrive = caminho_pendrive
        
        self.colecao_atual_id = None
        self.colecao_atual_nome = None

        self._build_ui()
        self._carregar_lista_colecoes()

    def _sincronizar_pendrive(self):
        """Grava as alterações do SSD de volta para o banco de dados mestre no Pendrive."""
        try:
            # Acede ao caminho original guardado na janela principal (master)
            if hasattr(self.master, 'db_master_path') and self.master.db_master_path:
                shutil.copy2(self.db.db_path, self.master.db_master_path)
        except Exception as e:
            print(f"Erro ao sincronizar BD com o pendrive: {e}")

    def _build_ui(self):
        self.grid_columnconfigure(0, weight=1) # Lista lateral (1/3)
        self.grid_columnconfigure(1, weight=2) # Painel de detalhes (2/3)
        self.grid_rowconfigure(0, weight=1)

        # ================= PAINEL ESQUERDO: LISTA DE COLEÇÕES =================
        self.frame_lista = ctk.CTkFrame(self)
        self.frame_lista.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        ctk.CTkLabel(self.frame_lista, text="Suas Coleções", font=("Roboto", 16, "bold")).pack(pady=10)
        
        self.scroll_colecoes = ctk.CTkScrollableFrame(self.frame_lista, fg_color="transparent")
        self.scroll_colecoes.pack(expand=True, fill="both", padx=5, pady=5)

        # ================= PAINEL DIREITO: DETALHES E AÇÕES =================
        self.frame_detalhes = ctk.CTkFrame(self)
        self.frame_detalhes.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        
        # Placeholder inicial
        self.lbl_nome_colecao = ctk.CTkLabel(self.frame_detalhes, text="Selecione uma coleção", font=("Roboto", 20, "bold"))
        self.lbl_nome_colecao.pack(pady=20)

        # Container de Controles (Inicia oculto/vazio até selecionar algo)
        self.frame_controles = ctk.CTkFrame(self.frame_detalhes, fg_color="transparent")
        
        ctk.CTkLabel(self.frame_controles, text="Modo de Ordem no Corolla:", font=("Roboto", 13)).pack(pady=(10, 2))
        self.modo_ordem = ctk.CTkSegmentedButton(self.frame_controles, values=["Aleatório", "Ordenado"])
        self.modo_ordem.pack(pady=5)

        ctk.CTkLabel(self.frame_controles, text="Modo de Sincronia:", font=("Roboto", 13)).pack(pady=(15, 2))
        self.modo_sincronia = ctk.CTkSegmentedButton(self.frame_controles, values=["Incremental", "Estrito"])
        self.modo_sincronia.pack(pady=5)

        # Estatísticas da coleção
        self.lbl_stats = ctk.CTkLabel(self.frame_controles, text="Vídeos baixados: 0", text_color="gray")
        self.lbl_stats.pack(pady=15)

        # Botões de Ação
        self.btn_salvar = ctk.CTkButton(self.frame_controles, text="Salvar Preferências", command=self._salvar_preferencias)
        self.btn_salvar.pack(pady=10, fill="x", padx=40)

        # NOVO: Botão para zerar falhas
        self.btn_reset_erros = ctk.CTkButton(
            self.frame_controles, 
            text="Tentar Novamente Vídeos com Erro", 
            command=self._resetar_erros,
            fg_color="#D97706", hover_color="#B45309" # Laranja
        )
        self.btn_reset_erros.pack(pady=10, fill="x", padx=40)

        self.btn_reaplicar = ctk.CTkButton(
            self.frame_controles, 
            text="Reaplicar Ordem no Pendrive", 
            command=self._forcar_reordenacao,
            fg_color="#3B82F6", hover_color="#2563EB" # Azul
        )
        self.btn_reaplicar.pack(pady=10, fill="x", padx=40)

        self.btn_excluir = ctk.CTkButton(
            self.frame_controles, 
            text="Excluir Coleção", 
            command=self._excluir_colecao,
            fg_color="#EF4444", hover_color="#DC2626" # Vermelho
        )
        self.btn_excluir.pack(pady=(30, 10), fill="x", padx=40)

    def _limpar_lista(self):
        for widget in self.scroll_colecoes.winfo_children():
            widget.destroy()

    def _carregar_lista_colecoes(self):
        self._limpar_lista()
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome FROM colecoes ORDER BY nome ASC")
            colecoes = cursor.fetchall()

        if not colecoes:
            ctk.CTkLabel(self.scroll_colecoes, text="Nenhuma coleção\nno pendrive.", text_color="gray").pack(pady=20)
            self.frame_controles.pack_forget()
            self.lbl_nome_colecao.configure(text="Nenhuma coleção encontrada")
            return

        for col in colecoes:
            btn = ctk.CTkButton(
                self.scroll_colecoes, 
                text=col['nome'], 
                fg_color="transparent", 
                border_width=1,
                text_color=("gray10", "gray90"),
                hover_color=("gray70", "gray30"),
                command=lambda id=col['id'], nome=col['nome']: self._carregar_detalhes(id, nome)
            )
            btn.pack(pady=2, fill="x")

    def _carregar_detalhes(self, colecao_id, nome):
        self.colecao_atual_id = colecao_id
        self.colecao_atual_nome = nome
        self.lbl_nome_colecao.configure(text=nome)
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Puxa regras
            cursor.execute("SELECT modo_ordem, modo_sincronia FROM colecoes WHERE id = ?", (colecao_id,))
            regras = cursor.fetchone()
            
            # Conta vídeos finalizados
            cursor.execute("""
                SELECT COUNT(v.id) as total FROM videos v
                JOIN playlists p ON v.playlist_id = p.id
                WHERE p.colecao_id = ? AND v.status = 'convertido'
            """, (colecao_id,))
            stats = cursor.fetchone()

        if regras:
            ordem = "Aleatório" if regras['modo_ordem'] == "aleatorio" else "Ordenado"
            self.modo_ordem.set(ordem)
            self.modo_sincronia.set(regras['modo_sincronia'].capitalize())
            
        if stats:
            self.lbl_stats.configure(text=f"Vídeos finalizados na coleção: {stats['total']}")

        # Exibe os controles agora que algo foi selecionado
        self.frame_controles.pack(expand=True, fill="both")

    def _salvar_preferencias(self):
        if not self.colecao_atual_id: return
        
        ordem = "aleatorio" if self.modo_ordem.get() == "Aleatório" else "ordenado"
        sincronia = self.modo_sincronia.get().lower()

        with self.db.get_connection() as conn:
            conn.execute(
                "UPDATE colecoes SET modo_ordem = ?, modo_sincronia = ? WHERE id = ?", 
                (ordem, sincronia, self.colecao_atual_id)
            )
            conn.commit()
            
        self._sincronizar_pendrive()
        messagebox.showinfo("Sucesso", "Regras atualizadas no banco de dados!")

    def _forcar_reordenacao(self):
        """Reaplica a lógica do os.utime para contornar o hardware do Corolla sem baixar nada."""
        if not self.colecao_atual_id: return
        
        self._salvar_preferencias() # Garante que está a usar a regra mais recente
        self.btn_reaplicar.configure(state="disabled", text="A processar...")
        
        try:
            # Chama o motor de sincronia para refazer os timestamps (Módulo 4)
            self.sync_engine.aplicar_ordenacao_e_utime(self.colecao_atual_id)
            messagebox.showinfo("Sucesso", "Nova ordem cronológica aplicada fisicamente aos arquivos do pendrive!")
        except Exception as e:
            messagebox.showerror("Erro", f"Falha ao reordenar: {str(e)}")
        finally:
            self.btn_reaplicar.configure(state="normal", text="Reaplicar Ordem no Pendrive")

    def _excluir_colecao(self):
        if self.colecao_atual_id is None:
            return
        
        confirm = messagebox.askyesno(
            "Excluir Coleção", 
            f"Tem a certeza que deseja excluir '{self.colecao_atual_nome}'?\n\nIsso apagará a pasta do pendrive e todos os vídeos contidos nela."
        )
        if not confirm: return

        # 1. Deleta do Banco de Dados com PRAGMA forçado para limpar vídeos e playlists (CASCADE)
        with self.db.get_connection() as conn:
            conn.execute("PRAGMA foreign_keys = ON") # <-- CRUCIAL PARA APAGAR OS VÍDEOS
            conn.execute("DELETE FROM colecoes WHERE id = ?", (self.colecao_atual_id,))
            conn.commit()

        # 2. Deleta a pasta física no Pendrive
        pasta_fisica = os.path.join(self.caminho_pendrive, self.colecao_atual_nome)
        if os.path.exists(pasta_fisica):
            try:
                shutil.rmtree(pasta_fisica)
            except Exception as e:
                messagebox.showwarning("Aviso", f"A coleção foi removida do banco, mas houve um erro ao apagar a pasta:\n{str(e)}")

        # 3. Sincroniza a exclusão imediatamente com o pendrive
        self._sincronizar_pendrive()

        self.colecao_atual_id = None
        self.frame_controles.pack_forget()
        self.lbl_nome_colecao.configure(text="Coleção Excluída")
        self._carregar_lista_colecoes()
        messagebox.showinfo("Sucesso", "Coleção e vídeos excluídos com sucesso.")

    def _resetar_erros(self):
        """Zera o contador de tentativas e devolve os vídeos quebrados para o status pendente."""
        if self.colecao_atual_id is None:
            return
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Atualiza apenas os vídeos que pertencem às playlists desta coleção específica
            cursor.execute("""
                UPDATE videos 
                SET status = 'pendente', tentativas = 0
                WHERE status = 'erro' AND playlist_id IN (
                    SELECT id FROM playlists WHERE colecao_id = ?
                )
            """, (self.colecao_atual_id,))
            linhas_afetadas = cursor.rowcount
            conn.commit()
        
        self._sincronizar_pendrive()

        if linhas_afetadas > 0:
            messagebox.showinfo(
                "Sucesso", 
                f"{linhas_afetadas} vídeo(s) redefinido(s) para a fila.\nEles serão baixados na próxima sincronização."
            )
            # Recarrega os detalhes para atualizar as estatísticas visuais, se houver
            self._carregar_detalhes(self.colecao_atual_id, self.colecao_atual_nome)
        else:
            messagebox.showinfo("Aviso", "Não há vídeos com falha nesta coleção.")