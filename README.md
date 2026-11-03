# 🚗 YT Car Sync - Toyota Corolla 2020 Edition

Um gestor e sincronizador avançado de mídias do YouTube para Pendrives, desenhado com uma arquitetura cirúrgica para contornar as limitações de leitura de hardware do sistema de infoentretenimento do Toyota Corolla 2020.

🤖 **Nota de Desenvolvimento:** Este software foi arquitetado, escrito e refinado com o auxílio avançado de Inteligência Artificial (LLM), combinando as melhores práticas de Engenharia de Software com prompt engineering para resolver problemas físicos de hardware automóvel.

## 💡 O Problema

O sistema multimédia do Toyota Corolla (2020) não respeita a ordenação alfabética padrão nem as metatags das pastas num pendrive FAT32. Ele reproduz as mídias com base na **ordem estrita de gravação física no disco** (tabela FAT) e nos *timestamps* dos ficheiros. Ao atualizar um pendrive com músicas novas, a ordem cronológica quebrava, misturando músicas velhas com novas.

## 🎯 A Solução (Características Principais)

* **Manipulação de Timestamp (`os.utime`):** O motor de sincronia injeta datas de modificação/acesso retroativas e milimetricamente espaçadas nos ficheiros físicos, forçando a central multimédia a ler os vídeos na ordem exata definida pelo utilizador.
* **Arquitetura Master/Slave:** O Pendrive atua como "Master" (guardando uma base de dados SQLite invisível). O SSD do computador atua como "Slave" local ultra-rápido. Isso permite portabilidade total (qualquer computador lê as regras do pendrive) e previne desgaste precoce da memória Flash.
* **Gestão Inteligente de Fontes (UI):** O programa armazena as URLs das playlists. Com um clique, ele varre o YouTube atrás de vídeos novos, ignorando os que já estão no pendrive (Bulk Insert otimizado).
* **Limpeza FAT32 (Regex):** Sanitização automática de emojis e caracteres especiais asiáticos que corrompem a leitura do rádio do carro.
* **Resiliência a Falhas:** Sistema *Graceful Shutdown* para cancelar downloads sem corromper a base de dados, além de um sistema de "Retry Limit" que ignora vídeos apagados/privados após 3 tentativas.

---

## 🛠️ Configuração de Ambiente e Instalação

Recomendamos vivamente a utilização de um Ambiente Virtual (`venv`) para isolar as dependências do projeto. **Python 3.8 ou superior** é estritamente necessário.

### 🐧 Ambiente Linux

**1. Preparação do Ambiente e Dependências Python:**
Abra o seu terminal na raiz do projeto e execute:
```bash
# Cria o ambiente virtual
python3 -m venv .venv

# Ativa o ambiente virtual
source .venv/bin/activate

# Instala os pacotes necessários
pip install customtkinter yt-dlp pyinstaller
```

**2. Preparação do Motor FFmpeg (Linux):**
Crie uma pasta chamada `bin` na raiz do seu projeto. Descarregue a versão estática (*static build*) do `ffmpeg` para Linux e coloque o binário executável dentro da pasta `bin/`. O ficheiro **não deve ter extensão**, devendo ficar exatamente como: `bin/ffmpeg`. Certifique-se de que lhe dá permissões de execução (`chmod +x bin/ffmpeg`).

### 🪟 Ambiente Windows

**1. Preparação do Ambiente e Dependências Python:**
Abra o PowerShell ou o Terminal (CMD) na raiz do projeto e execute:
```cmd
:: Cria o ambiente virtual
python -m venv .venv

:: Ativa o ambiente virtual
.venv\Scripts\activate

:: Instala os pacotes necessários
pip install customtkinter yt-dlp pyinstaller
```

**2. Preparação do Motor FFmpeg (Windows):**
Crie uma pasta chamada `bin` na raiz do seu projeto. Descarregue a versão *essentials* do FFmpeg para Windows (um ficheiro `.exe`) e coloque-o dentro da pasta. O caminho completo deve ser exatamente: `bin/ffmpeg.exe`.

---

## 📦 Como Compilar o Projeto (Executável Standalone)

Transformar este projeto em código Python num executável portátil requer o uso do **PyInstaller**. 

> ⚠️ **ATENÇÃO (Cross-Compilation):** O PyInstaller compila sempre para o sistema operativo em que está a ser executado. Compilar no Linux gerará um executável de Linux. Para gerar um ficheiro `.exe` para o Windows, **terá obrigatoriamente** de clonar o projeto e executar o comando de compilação dentro de um sistema Windows (físico ou Máquina Virtual).

O comando de compilação difere subtilmente na sintaxe do parâmetro `--add-binary` devido à forma como cada sistema operativo processa caminhos.

### Compilar para Windows (.exe)
Dentro do ambiente Windows (com o `venv` ativado), utilize o separador de caminho **ponto-e-vírgula** (`;`) e especifique o ficheiro `.exe`:

```cmd
pyinstaller --noconfirm --onedir --windowed --name "YT_Car_Sync" --add-binary "bin/ffmpeg.exe;bin" --collect-all customtkinter main.py
```

### Compilar para Linux (Binário ELF)
Dentro do ambiente Linux (com o `venv` ativado), utilize o separador de caminho **dois-pontos** (`:`) e especifique o binário sem extensão:

```bash
pyinstaller --noconfirm --onedir --windowed --name "YT_Car_Sync" --add-binary "bin/ffmpeg:bin" --collect-all customtkinter main.py
```

**Explicação dos parâmetros utilizados:**
* `--onedir`: Cria uma pasta com o executável e as suas dependências (recomendado por ter inicialização instantânea). Se preferir um ficheiro único, utilize `--onefile` (irá adicionar 5-10 segundos de atraso no arranque).
* `--windowed`: Oculta a janela de consola do terminal para que apenas a Interface Gráfica seja exibida.
* `--add-binary`: Embuta o FFmpeg no pacote final, para que o utilizador não necessite de instalações externas de codecs.
* `--collect-all`: Garante a inclusão dos temas e ficheiros de configuração base do `CustomTkinter`.

O seu programa final compilado estará na pasta `dist/YT_Car_Sync/`.

---

## 📖 Como Utilizar

1. **Selecionar Mídia:** Clique em "Procurar Pendrive" e selecione a raiz da sua pen drive USB (FAT32). O sistema criará a base de dados invisível imediatamente.
2. **Criar Coleção:** Na caixa de seleção combinada (combobox), digite o nome de uma pasta (ex: "Viagem 2026") e pressione ENTER, ou selecione uma coleção existente.
3. **Gerir Links:** Cole URLs do YouTube (vídeos avulsos ou playlists) na caixa de texto.
4. **Sincronizar:** Clique em "Iniciar Sincronização". O programa tratará do download, da conversão inteligente (320x240, proporção 16:9, codec h264 otimizado para o Corolla), aplicará a manipulação de hardware (timestamp) e enviará tudo perfeitamente ordenado para a pen drive.
5. **Gerenciador Avançado:** Clique em "Gerenciar Coleções" para abrir a interface detalhada. Aqui poderá visualizar a hierarquia da pen drive através de uma estrutura de árvore, mover ficheiros de forma segura entre coleções, remover vídeos específicos, aplicar novamente a ordem, ou clicar em "Verificar Novas Mídias" para atualizar playlists remotamente com 1 clique.