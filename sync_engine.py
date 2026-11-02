import os
import time
import random
from pathlib import Path
from database import DatabaseManager

class SyncEngine:
    def __init__(self, db_manager: DatabaseManager):
        self.db = db_manager

    def aplicar_ordenacao_e_utime(self, colecao_id: int):
        """
        Aplica a ordenação (aleatória ou ordenada) e altera o timestamp de modificação
        dos ficheiros físicos usando os.utime() com espaçamento incremental.
        Isto força a central do Toyota Corolla a reproduzir os vídeos na ordem desejada.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            
            # Obter modo de ordem da coleção
            cursor.execute("SELECT modo_ordem FROM colecoes WHERE id = ?", (colecao_id,))
            col = cursor.fetchone()
            if not col:
                return
            modo_ordem = col['modo_ordem']

            # Obter vídeos convertidos desta coleção
            cursor.execute("""
                SELECT v.id, v.caminho_ficheiro FROM videos v
                JOIN playlists p ON v.playlist_id = p.id
                WHERE p.colecao_id = ? AND v.status = 'convertido' AND v.caminho_ficheiro IS NOT NULL
            """, (colecao_id,))
            videos = cursor.fetchall()

        if not videos:
            return

        ficheiros = [v['caminho_ficheiro'] for v in videos if os.path.exists(v['caminho_ficheiro'])]

        # Regra de Negócio: Aleatório vs Ordenado
        if modo_ordem == 'aleatorio':
            random.shuffle(ficheiros)
        else:
            # NOVO: Ordena estritamente pelo nome do arquivo final (ignorando caminhos de pastas e maiúsculas/minúsculas)
            ficheiros.sort(key=lambda x: os.path.basename(x).lower())

        # Define um ponto base no passado recente
        tempo_atual = time.time() - (len(ficheiros) * 5)

        for caminho in ficheiros:
            # NOVO: Acumulador garantido (soma sempre de 3 a 5 segundos a partir do ÚLTIMO valor)
            tempo_atual += random.randint(3, 5)
            
            # Aplica o timestamp de acesso e modificação (atime, mtime)
            os.utime(caminho, (tempo_atual, tempo_atual))
            
            # Atualiza o registo na base de dados
            with self.db.get_connection() as conn:
                conn.execute(
                    "UPDATE videos SET data_modificacao = ? WHERE caminho_ficheiro = ?",
                    (tempo_atual, caminho)
                )
                conn.commit()

    def executar_sincronia_colecao(self, colecao_id: int, pasta_destino: str):
        """
        Executa a sincronização aplicando o modo 'estrito' ou 'incremental'.
        No modo 'estrito', remove ficheiros locais huérfanos que desapareceram da web.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT modo_sincronia FROM colecoes WHERE id = ?", (colecao_id,))
            col = cursor.fetchone()
            if not col:
                return
            modo_sincronia = col['modo_sincronia']

            # Obter caminhos válidos associados na base de dados
            cursor.execute("""
                SELECT v.caminho_ficheiro FROM videos v
                JOIN playlists p ON v.playlist_id = p.id
                WHERE p.colecao_id = ? AND v.caminho_ficheiro IS NOT NULL
            """, (colecao_id,))
            registos = cursor.fetchall()
            caminhos_validos = {os.path.abspath(r['caminho_ficheiro']) for r in registos}

        # Modo Estrito: Limpa ficheiros locais que já não constam nas playlists ativas
        if modo_sincronia == 'estrito' and os.path.exists(pasta_destino):
            for root, _, files in os.walk(pasta_destino):
                for file in files:
                    filepath = os.path.abspath(os.path.join(root, file))
                    if filepath not in caminhos_validos and file.endswith('.mp4'):
                        try:
                            os.remove(filepath)
                        except OSError:
                            pass

        # Aplica a ordenação temporal no final da sincronização
        self.aplicar_ordenacao_e_utime(colecao_id)