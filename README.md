# Video Editor

Sistema de edição de vídeo que combina narração, imagens/vídeos, legendas e áudio de background.

## Funcionalidades

- **Áudio de Narração** - MP3, WAV, AAC, M4A, OGG, FLAC
- **Imagens/Vídeos** - JPG, PNG, GIF, MP4, MOV, AVI, MKV (distribuídos em sequência)
- **Legendas** - Suporte a arquivos SRT
- **Áudio de Background** - Com controle de volume em decibéis (-40dB a 0dB)
- **Saída** - Vídeo 16:9 em 1920x1080 (Full HD)

---

## Rodar no GitHub Codespaces (Recomendado)

### Passo 1: Abrir o Codespace
1. No repositório do GitHub, clique no botão verde **"Code"**
2. Selecione a aba **"Codespaces"**
3. Clique em **"Create codespace on main"**

### Passo 2: Aguardar a configuração
O Codespace vai automaticamente:
- Instalar Python 3.11
- Instalar FFmpeg
- Instalar as dependências do projeto

### Passo 3: Executar o servidor
No terminal do Codespace, execute:
```bash
python app.py
```

### Passo 4: Acessar a aplicação
- Uma notificação aparecerá para abrir a porta 5000
- Clique em **"Open in Browser"**
- A aplicação abrirá em uma nova aba!

---

## Rodar Localmente

### Pré-requisitos
- Python 3.8+
- FFmpeg

### Instalação

```bash
# 1. Clone o repositório
git clone https://github.com/seu-usuario/VIDEO-EDIT.git
cd VIDEO-EDIT

# 2. Instale as dependências Python
pip install -r requirements.txt

# 3. Instale o FFmpeg
# Ubuntu/Debian:
sudo apt install ffmpeg

# macOS:
brew install ffmpeg

# Windows:
# Baixe em https://ffmpeg.org/download.html

# 4. Execute o servidor
python app.py
```

### Acesso
Abra no navegador: http://localhost:5000

---

## Como Usar

1. **Envie o áudio de narração** (obrigatório)
2. **Adicione imagens/vídeos** (obrigatório) - arraste para reordenar
3. **Adicione legendas SRT** (opcional)
4. **Adicione áudio de background** (opcional) - ajuste o volume
5. Clique em **"Gerar Vídeo 16:9"**
6. Aguarde o processamento e faça o download

---

## Tecnologias

- **Backend:** Python + Flask
- **Processamento:** FFmpeg
- **Frontend:** HTML5 + CSS3 + JavaScript
