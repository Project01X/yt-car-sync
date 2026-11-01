import re
from urllib.parse import urlparse, parse_qs
from typing import List, Dict

class InputParser:
    @staticmethod
    def extrair_e_categorizar_links(raw_text: str, ignorar_playlists: bool = False) -> List[Dict]:
        """
        Processa texto sujo contendo múltiplos links (separados por vírgulas ou quebras de linha).
        Retorna uma lista de dicionários categorizando se o link deve ser tratado como vídeo único ou playlist.
        """
        # Divide o texto por quebras de linha ou vírgulas
        raw_links = re.split(r'[\n,]+', raw_text)
        links_processados = []
        urls_vistas = set()

        for link in raw_links:
            link = link.strip()
            if not link:
                continue

            # Validação Regex básica para domínios do YouTube
            if not re.search(r'(?:https?:\/\/)?(?:www\.)?(?:youtube\.com|youtu\.be)\/(?:watch\?v=|playlist\?list=|embed\/|shorts\/)?([a-zA-Z0-9_-]+)', link):
                continue

            if link in urls_vistas:
                continue
            urls_vistas.add(link)

            parsed_url = urlparse(link)
            query_params = parse_qs(parsed_url.query)

            tem_v = 'v' in query_params
            tem_list = 'list' in query_params
            is_short = 'shorts/' in parsed_url.path
            is_youtu_be = 'youtu.be' in parsed_url.netloc

            is_playlist = False
            noplaylist = True

            # Lógica de decisão: Playlist pura vs Vídeo dentro de Playlist
            if tem_list:
                if (tem_v or is_youtu_be) and ignorar_playlists:
                    # Link tem vídeo e playlist, mas o utilizador forçou extração apenas do vídeo
                    is_playlist = False
                    noplaylist = True
                else:
                    # Tratar como playlist (mesmo que tenha um 'v' embutido)
                    is_playlist = True
                    noplaylist = False
            
            links_processados.append({
                'url': link,
                'is_playlist': is_playlist,
                'noplaylist': noplaylist,
                'is_short': is_short
            })

        return links_processados

class YTDLPConfigurator:
    @staticmethod
    def get_base_options(download_archive_path: str = None) -> dict:
        """
        Gera o dicionário de opções para o yt-dlp injetando as regras de fallback
        obrigatórias para contornar falhas de resolução e otimizar banda.
        """
        opts = {
            # Regra de Negócio: Garantir resolução máxima de 360p (para downscale perfeito para 240p)
            # Fallback 1: worstvideo+bestaudio (caso não haja 360p exato)
            # Fallback 2: best (caso o vídeo não tenha faixas separadas)
            'format': 'bestvideo[height<=360]+bestaudio/worstvideo+bestaudio/best',
            'merge_output_format': 'mp4',
            'quiet': True,
            'no_warnings': True,
            'ignoreerrors': True, # Impede que um vídeo bloqueado interrompa toda a fila
            'extract_flat': False, # Definido dinamicamente no motor de download
        }
        
        if download_archive_path:
            opts['download_archive'] = download_archive_path
            
        return opts