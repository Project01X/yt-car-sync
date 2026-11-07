import customtkinter as ctk
from tkinter import messagebox, ttk
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

        # Configuração do tema da Árvore (Treeview)
        style = ttk.Style(self)
        style.theme_use("default")
        style.configure("Treeview", 
                        background="#2b2b2b", 
                        foreground="white", 
                        rowheight=28, 
                        fieldbackground="#2b2b2b", 
                        borderwidth=0)
        style.map('Treeview', background=[('selected', '#1f538d')])

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

        # ================= PAINEL ESQUERDO =================
        self.frame_lista = ctk.CTkFrame(self)
        self.frame_lista.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        ctk.CTkLabel(self.frame_lista, text="Suas Coleções", font=("Roboto", 16, "bold")).pack(pady=10)
        self.scroll_colecoes = ctk.CTkScrollableFrame(self.frame_lista, fg_color="transparent")
        self.scroll_colecoes.pack(expand=True, fill="both", padx=5, pady=5)

        # ================= PAINEL DIREITO =================
        self.frame_detalhes = ctk.CTkFrame(self)
        self.frame_detalhes.grid(row=0, column=1, padx=(0, 10), pady=10, sticky="nsew")
        
        self.lbl_nome_colecao = ctk.CTkLabel(self.frame_detalhes, text="Selecione uma coleção", font=("Roboto", 20, "bold"))
        self.lbl_nome_colecao.pack(pady=15)

        # NOVO: Sistema de Abas
        self.tabs = ctk.CTkTabview(self.frame_detalhes, fg_color="transparent")
        
        self.tab_regras = self.tabs.add("Regras & Ações")
        self.tab_fontes = self.tabs.add("Fontes (Playlists/Links)")

        # --- ABA 1: Regras e Ações ---
        ctk.CTkLabel(self.tab_regras, text="Modo de Ordem no Corolla:", font=("Roboto", 13)).pack(pady=(10, 2))
        self.modo_ordem = ctk.CTkSegmentedButton(self.tab_regras, values=["Aleatório", "Ordenado"])
        self.modo_ordem.pack(pady=5)

        ctk.CTkLabel(self.tab_regras, text="Modo de Sincronia:", font=("Roboto", 13)).pack(pady=(15, 2))
        self.modo_sincronia = ctk.CTkSegmentedButton(self.tab_regras, values=["Incremental", "Estrito"])
        self.modo_sincronia.pack(pady=5)

        self.lbl_stats = ctk.CTkLabel(self.tab_regras, text="Vídeos baixados: 0", text_color="gray")
        self.lbl_stats.pack(pady=15)

        self.btn_salvar = ctk.CTkButton(self.tab_regras, text="Salvar Preferências", command=self._salvar_preferencias)
        self.btn_salvar.pack(pady=5, fill="x", padx=40)

        self.btn_reset_erros = ctk.CTkButton(self.tab_regras, text="Tentar Novamente Vídeos com Erro", command=self._resetar_erros, fg_color="#D97706", hover_color="#B45309")
        self.btn_reset_erros.pack(pady=5, fill="x", padx=40)

        self.btn_reaplicar = ctk.CTkButton(self.tab_regras, text="Reaplicar Ordem no Pendrive", command=self._forcar_reordenacao, fg_color="#3B82F6", hover_color="#2563EB")
        self.btn_reaplicar.pack(pady=5, fill="x", padx=40)

        self.btn_excluir = ctk.CTkButton(self.tab_regras, text="Excluir Coleção", command=self._excluir_colecao, fg_color="#EF4444", hover_color="#DC2626")
        self.btn_excluir.pack(pady=(20, 10), fill="x", padx=40)

        # --- ABA 2: Fontes Web (Gestão Avançada) ---
        self.frame_tree = ctk.CTkFrame(self.tab_fontes, fg_color="transparent")
        self.frame_tree.pack(expand=True, fill="both", padx=5, pady=5)
        
        # Scrollbar e Treeview nativo do Tkinter
        self.tree_scroll = ctk.CTkScrollbar(self.frame_tree)
        self.tree_scroll.pack(side="right", fill="y")
        
        # Colunas ocultas para armazenar metadados: tipo, id_principal, id_secundario
        self.tree = ttk.Treeview(self.frame_tree, selectmode="browse", yscrollcommand=self.tree_scroll.set, show="tree")
        self.tree.pack(side="left", expand=True, fill="both")
        self.tree_scroll.configure(command=self.tree.yview)
        
        self.tree.bind("<<TreeviewSelect>>", self._on_tree_select)

        # Botões de Ação da Árvore
        self.frame_acoes_tree = ctk.CTkFrame(self.tab_fontes, fg_color="transparent")
        self.frame_acoes_tree.pack(fill="x", pady=5)

        self.btn_mover = ctk.CTkButton(
            self.frame_acoes_tree, text="Mover Selecionado", 
            command=self._mover_selecionado, state="disabled", 
            fg_color="#3B82F6", hover_color="#2563EB"
        )
        self.btn_mover.pack(side="left", expand=True, padx=5)

        self.btn_excluir_tree = ctk.CTkButton(
            self.frame_acoes_tree, text="Excluir Selecionado", 
            command=self._excluir_selecionado, state="disabled", 
            fg_color="#EF4444", hover_color="#DC2626"
        )
        self.btn_excluir_tree.pack(side="left", expand=True, padx=5)

        self.btn_atualizar_remoto = ctk.CTkButton(
            self.tab_fontes, 
            text="Verificar Novas Mídias no YouTube", 
            command=self._iniciar_atualizacao_remota,
            fg_color="#059669", hover_color="#047857"
        )
        self.btn_atualizar_remoto.pack(pady=10, fill="x", padx=5)

    def _carregar_fontes(self):
        """Lista todas as playlists e vídeos da coleção atual com hierarquia visual."""
        for item in self.tree.get_children():
            self.tree.delete(item)
            
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, url FROM playlists WHERE colecao_id = ?", (self.colecao_atual_id,))
            playlists = cursor.fetchall()
            
            cursor.execute("""
                SELECT v.id, v.titulo, v.playlist_id, v.status
                FROM videos v
                JOIN playlists p ON v.playlist_id = p.id
                WHERE p.colecao_id = ?
            """, (self.colecao_atual_id,))
            todos_videos = cursor.fetchall()
            
        # Nó Pai para vídeos isolados
        node_sem_categoria = self.tree.insert("", "end", text="📁 Sem Categoria (Vídeos Avulsos)", values=("grupo", None, None))
        
        for p in playlists:
            p_id = p['id']
            url = p['url']
            videos_desta_pl = [v for v in todos_videos if v['playlist_id'] == p_id]
            
            if "list=" in url:
                # É uma playlist estruturada
                node_pl = self.tree.insert("", "end", text=f"🗂️ Playlist: {url}", values=("playlist", p_id, None))
                for v in videos_desta_pl:
                    icone = "✅" if v['status'] == 'convertido' else ("❌" if v['status'] == 'erro' else "⏳")
                    # Bloqueamos a movimentação via atributo "video_playlist"
                    self.tree.insert(node_pl, "end", text=f"  {icone} {v['titulo']}", values=("video_playlist", v['id'], p_id))
            else:
                # É um vídeo avulso (URL direta). Adicionamos sob a pasta "Sem Categoria"
                for v in videos_desta_pl:
                    icone = "✅" if v['status'] == 'convertido' else ("❌" if v['status'] == 'erro' else "⏳")
                    # Salvamos o p_id na aba 3 (id_secundario) para mover o ficheiro independente
                    self.tree.insert(node_sem_categoria, "end", text=f"  {icone} {v['titulo']}", values=("video_independente", v['id'], p_id))
                    
        self.tree.item(node_sem_categoria, open=True)

    def _on_tree_select(self, event):
        """Regras de Negócio: Bloqueia a movimentação de vídeos de playlist."""
        selecionado = self.tree.selection()
        if not selecionado: return
        
        item = self.tree.item(selecionado[0])
        tipo = item['values'][0]
        
        if tipo == "grupo": # O título "Sem Categoria" em si
            self.btn_mover.configure(state="disabled")
            self.btn_excluir_tree.configure(state="disabled")
        elif tipo == "video_playlist":
            self.btn_mover.configure(state="disabled") # PROTEÇÃO: Impede mover itens da playlist
            self.btn_excluir_tree.configure(state="normal") # Mas permite apagá-los
        else:
            self.btn_mover.configure(state="normal")
            self.btn_excluir_tree.configure(state="normal")

    def _mover_selecionado(self):
        """Abre uma janela Modal para selecionar a Coleção de Destino."""
        selecionado = self.tree.selection()
        if not selecionado: return
        
        item = self.tree.item(selecionado[0])
        tipo = item['values'][0]
        id_principal = item['values'][1]
        id_secundario = item['values'][2]
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id, nome FROM colecoes WHERE id != ?", (self.colecao_atual_id,))
            outras_colecoes = cursor.fetchall()
            
        if not outras_colecoes:
            messagebox.showinfo("Aviso", "Não existem outras coleções para onde mover.")
            return
            
        dialog = ctk.CTkToplevel(self)
        dialog.title("Mover Item")
        dialog.geometry("300x150")
        dialog.transient(self)
        dialog.grab_set()
        
        ctk.CTkLabel(dialog, text="Selecione a coleção de destino:").pack(pady=10)
        combo_destino = ctk.CTkComboBox(dialog, values=[c['nome'] for c in outras_colecoes])
        combo_destino.pack(pady=5)
        
        def confirmar():
            nome_alvo = combo_destino.get()
            dest_id = next((c['id'] for c in outras_colecoes if c['nome'] == nome_alvo), None)
            if dest_id:
                self._executar_movimentacao(tipo, id_principal, id_secundario, dest_id, nome_alvo)
            dialog.destroy()
            
        ctk.CTkButton(dialog, text="Confirmar Transferência", command=confirmar).pack(pady=10)

    def _executar_movimentacao(self, tipo, id_principal, p_id, dest_id, dest_nome):
        """Move os ficheiros físicos no pendrive e atualiza o BD em simultâneo."""
        pasta_destino = os.path.join(self.caminho_pendrive, dest_nome)
        os.makedirs(pasta_destino, exist_ok=True)
        
        playlist_id_alvo = id_principal if tipo == "playlist" else p_id
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Encontra todos os arquivos .mp4 que precisam ser movidos
            cursor.execute("SELECT id, caminho_ficheiro FROM videos WHERE playlist_id = ?", (playlist_id_alvo,))
            videos = cursor.fetchall()
            
            for v in videos:
                caminho_antigo = v['caminho_ficheiro']
                if caminho_antigo and os.path.exists(caminho_antigo):
                    nome_arq = os.path.basename(caminho_antigo)
                    novo_caminho = os.path.join(pasta_destino, nome_arq)
                    shutil.move(caminho_antigo, novo_caminho) # Ficheiro movido fisicamente
                    cursor.execute("UPDATE videos SET caminho_ficheiro = ? WHERE id = ?", (novo_caminho, v['id']))
            
            # Reposiciona a fonte na base de dados
            cursor.execute("UPDATE playlists SET colecao_id = ? WHERE id = ?", (dest_id, playlist_id_alvo))
            conn.commit()
            
        self._sincronizar_pendrive()
        self._carregar_detalhes(self.colecao_atual_id, self.colecao_atual_nome) # Recarrega a UI
        messagebox.showinfo("Sucesso", "Transferência física e estrutural concluída!")

    def _excluir_selecionado(self):
        """Exclui o item do BD e remove o arquivo físico correspondente."""
        selecionado = self.tree.selection()
        if not selecionado: return
        
        item = self.tree.item(selecionado[0])
        tipo = item['values'][0]
        
        if not messagebox.askyesno("Excluir", "Deseja excluir este item?\nOs arquivos físicos também serão deletados."): return
            
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            if tipo == "playlist": # Deleta a pasta lógica inteira
                playlist_id = item['values'][1]
                cursor.execute("SELECT caminho_ficheiro FROM videos WHERE playlist_id = ?", (playlist_id,))
                for v in cursor.fetchall():
                    if v['caminho_ficheiro'] and os.path.exists(v['caminho_ficheiro']):
                        os.remove(v['caminho_ficheiro'])
                
                conn.execute("PRAGMA foreign_keys = ON") # Força cascata no SQLite
                cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
                
            elif tipo in ("video_independente", "video_playlist"): # Deleta 1 único arquivo
                video_id = item['values'][1]
                playlist_id = item['values'][2]
                
                cursor.execute("SELECT caminho_ficheiro FROM videos WHERE id = ?", (video_id,))
                v = cursor.fetchone()
                if v and v['caminho_ficheiro'] and os.path.exists(v['caminho_ficheiro']):
                    os.remove(v['caminho_ficheiro'])
                    
                # A MÁGICA DO SOFT DELETE: Em vez de apagar da base, criamos um "Blacklist" permanente
                if tipo == "video_playlist":
                    # Usa tentativas = 999 para indicar que o utilizador baniu esta música da playlist
                    cursor.execute("UPDATE videos SET status = 'erro', tentativas = 999, caminho_ficheiro = NULL WHERE id = ?", (video_id,))
                else:
                    # Se for independente, a playlist é fictícia, logo podemos apagar tudo sem criar fantasmas
                    cursor.execute("DELETE FROM videos WHERE id = ?", (video_id,))
                    cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))
                    
            conn.commit()
            
        self._sincronizar_pendrive()
        self._carregar_detalhes(self.colecao_atual_id, self.colecao_atual_nome)
        
    def _iniciar_atualizacao_remota(self):
        """Envia os links salvos de volta para a UI principal para buscar novos vídeos no YouTube."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT url FROM playlists WHERE colecao_id = ?", (self.colecao_atual_id,))
            fontes = cursor.fetchall()
            
        if not fontes:
            messagebox.showwarning("Aviso", "Não há fontes para atualizar.")
            return
            
        urls = [f['url'] for f in fontes]
        
        self.master.nome_colecao.set(self.colecao_atual_nome)
        self.master._ao_selecionar_colecao(self.colecao_atual_nome)
        self.master.textbox_links.delete("1.0", "end")
        self.master.textbox_links.insert("end", "\n".join(urls))
        
        self.destroy()
        self.master.iniciar_processo_thread()

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
        self._carregar_fontes()
        
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
        self.tabs.pack(expand=True, fill="both", padx=10, pady=10)

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
        self.tabs.pack_forget()
        self.lbl_nome_colecao.configure(text="Coleção Excluída")
        self._carregar_lista_colecoes()
        messagebox.showinfo("Sucesso", "Coleção e vídeos excluídos com sucesso.")

    def _resetar_erros(self):
        """Zera o contador de tentativas (ignorando os banidos com 999)."""
        if self.colecao_atual_id is None:
            return
        
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # O filtro "tentativas < 999" impede que as músicas "apagadas" voltem
            cursor.execute("""
                UPDATE videos 
                SET status = 'pendente', tentativas = 0
                WHERE status = 'erro' AND tentativas < 999 AND playlist_id IN (
                    SELECT id FROM playlists WHERE colecao_id = ?
                )
            """, (self.colecao_atual_id,))
            linhas_afetadas = cursor.rowcount
            conn.commit()
        
        self._sincronizar_pendrive()

        if linhas_afetadas > 0:
            messagebox.showinfo("Sucesso", f"{linhas_afetadas} vídeo(s) redefinido(s) para a fila.")
            self._carregar_detalhes(self.colecao_atual_id, self.colecao_atual_nome)
        else:
            messagebox.showinfo("Aviso", "Não há vídeos com falha nesta coleção (músicas excluídas manualmente não contam como erro).")