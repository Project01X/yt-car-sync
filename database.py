import sqlite3
import os
from pathlib import Path

class DatabaseManager:
    def __init__(self, db_path: str = "database.db"):
        """
        Inicializa o gestor da base de dados. O db_path pode ser alterado dinamicamente
        para operar numa cópia local (em %TEMP%) antes de ser movido para a pen drive.
        """
        self.db_path = db_path
        self._init_schema()

    def get_connection(self):
        """Retorna uma conexão configurada com Foreign Keys ativadas."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = 1;")
        # Retorna dicionários em vez de tuplos para facilitar a integração com a GUI
        conn.row_factory = sqlite3.Row 
        return conn

    def _init_schema(self):
        """Cria as tabelas principais caso não existam."""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            
            # Coleções: Representam as pastas físicas na pen drive e as suas regras
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS colecoes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    nome TEXT NOT NULL UNIQUE,
                    modo_ordem TEXT NOT NULL CHECK(modo_ordem IN ('aleatorio', 'ordenado')) DEFAULT 'aleatorio',
                    modo_sincronia TEXT NOT NULL CHECK(modo_sincronia IN ('estrito', 'incremental')) DEFAULT 'incremental'
                )
            """)

            # Playlists: Fontes web associadas a uma coleção
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS playlists (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    colecao_id INTEGER NOT NULL,
                    url TEXT NOT NULL UNIQUE,
                    nome TEXT,
                    FOREIGN KEY (colecao_id) REFERENCES colecoes (id) ON DELETE CASCADE
                )
            """)

            # Vídeos: Metadados do YouTube e rastreio do ficheiro local
            # Tabela atualizada com a coluna 'tentativas'
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS videos (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    playlist_id INTEGER NOT NULL,
                    youtube_id TEXT NOT NULL UNIQUE,
                    titulo TEXT NOT NULL,
                    caminho_ficheiro TEXT,
                    data_modificacao REAL, 
                    status TEXT CHECK(status IN ('pendente', 'descarregado', 'convertido', 'erro')) DEFAULT 'pendente',
                    tentativas INTEGER DEFAULT 0,
                    FOREIGN KEY (playlist_id) REFERENCES playlists (id) ON DELETE CASCADE
                )
            """)
            
            # Migração automática para bancos de dados já existentes
            try:
                cursor.execute("ALTER TABLE videos ADD COLUMN tentativas INTEGER DEFAULT 0")
            except sqlite3.OperationalError:
                pass # A coluna já existe, ignorar
                
            conn.commit()

    def exportar_download_archive(self, caminho_txt: str):
        """
        Gera um ficheiro .txt no formato aceite pelo --download-archive do yt-dlp.
        Extrai todos os youtube_id que já tenham o status 'convertido'.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT youtube_id FROM videos WHERE status = 'convertido'")
            videos_processados = cursor.fetchall()
            
            with open(caminho_txt, 'w', encoding='utf-8') as f:
                for video in videos_processados:
                    f.write(f"youtube {video['youtube_id']}\n")