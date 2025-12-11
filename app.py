"""
Video Editor - Sistema de edição de vídeo com Python e Flask
Combina áudio de narração, imagens/vídeos, legendas SRT e áudio de background
"""
import os
import uuid
import json
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
from werkzeug.utils import secure_filename
from utils.video_processor import VideoProcessor

# Configuração do Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'video-editor-secret-key-2024')
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500MB max

# Diretórios
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"

# Cria diretórios se não existirem
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Extensões permitidas
ALLOWED_AUDIO = {'mp3', 'wav', 'aac', 'm4a', 'ogg', 'flac'}
ALLOWED_VIDEO = {'mp4', 'avi', 'mov', 'mkv', 'webm', 'flv', 'wmv'}
ALLOWED_IMAGE = {'jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tiff'}
ALLOWED_SUBTITLE = {'srt'}

# Inicializa o processador
processor = VideoProcessor(str(UPLOAD_DIR), str(OUTPUT_DIR))

# Estado do processamento (em produção, usar Redis/Database)
processing_status = {}


def allowed_file(filename: str, allowed_extensions: set) -> bool:
    """Verifica se a extensão do arquivo é permitida"""
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed_extensions


def save_uploaded_file(file, prefix: str = "") -> str:
    """Salva um arquivo enviado e retorna o caminho"""
    if file and file.filename:
        # Gera nome único
        ext = Path(file.filename).suffix
        unique_name = f"{prefix}_{uuid.uuid4().hex}{ext}"
        file_path = UPLOAD_DIR / unique_name
        file.save(str(file_path))
        return str(file_path)
    return ""


@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')


@app.route('/api/upload', methods=['POST'])
def upload_files():
    """Endpoint para upload de arquivos"""
    try:
        session_id = request.form.get('session_id', uuid.uuid4().hex)
        file_type = request.form.get('type', '')

        if 'file' not in request.files:
            return jsonify({'error': 'Nenhum arquivo enviado'}), 400

        file = request.files['file']

        if file.filename == '':
            return jsonify({'error': 'Arquivo sem nome'}), 400

        # Valida tipo de arquivo
        if file_type == 'narration':
            if not allowed_file(file.filename, ALLOWED_AUDIO):
                return jsonify({'error': 'Formato de áudio não suportado'}), 400
        elif file_type == 'media':
            if not allowed_file(file.filename, ALLOWED_VIDEO | ALLOWED_IMAGE):
                return jsonify({'error': 'Formato de mídia não suportado'}), 400
        elif file_type == 'subtitle':
            if not allowed_file(file.filename, ALLOWED_SUBTITLE):
                return jsonify({'error': 'Formato de legenda não suportado (use .srt)'}), 400
        elif file_type == 'background':
            if not allowed_file(file.filename, ALLOWED_AUDIO):
                return jsonify({'error': 'Formato de áudio não suportado'}), 400

        # Salva o arquivo
        saved_path = save_uploaded_file(file, f"{session_id}_{file_type}")

        return jsonify({
            'success': True,
            'path': saved_path,
            'filename': file.filename,
            'type': file_type
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/process', methods=['POST'])
def process_video():
    """Endpoint para processar o vídeo"""
    try:
        data = request.get_json()

        if not data:
            return jsonify({'error': 'Dados não fornecidos'}), 400

        # Obtém parâmetros
        narration_path = data.get('narration_path')
        media_files = data.get('media_files', [])
        subtitle_path = data.get('subtitle_path')
        background_path = data.get('background_path')
        background_volume_db = float(data.get('background_volume_db', -15))

        # Validações
        if not narration_path or not os.path.exists(narration_path):
            return jsonify({'error': 'Áudio de narração não encontrado'}), 400

        if not media_files:
            return jsonify({'error': 'Nenhuma mídia (imagem/vídeo) fornecida'}), 400

        # Verifica se todos os arquivos de mídia existem
        for media_path in media_files:
            if not os.path.exists(media_path):
                return jsonify({'error': f'Arquivo de mídia não encontrado: {media_path}'}), 400

        # Processa o vídeo
        output_path, output_filename = processor.process(
            narration_path=narration_path,
            media_files=media_files,
            subtitle_path=subtitle_path,
            background_path=background_path,
            background_volume_db=background_volume_db
        )

        # Limpa arquivos de upload
        files_to_clean = [narration_path] + media_files
        if subtitle_path:
            files_to_clean.append(subtitle_path)
        if background_path:
            files_to_clean.append(background_path)
        processor.cleanup_uploads(files_to_clean)

        return jsonify({
            'success': True,
            'output_path': output_path,
            'output_filename': output_filename,
            'download_url': f'/api/download/{output_filename}'
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/api/download/<filename>')
def download_file(filename):
    """Endpoint para download do vídeo processado"""
    try:
        file_path = OUTPUT_DIR / secure_filename(filename)
        if not file_path.exists():
            return jsonify({'error': 'Arquivo não encontrado'}), 404

        return send_file(
            str(file_path),
            mimetype='video/mp4',
            as_attachment=True,
            download_name=filename
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/preview/<filename>')
def preview_file(filename):
    """Endpoint para preview do vídeo"""
    try:
        file_path = OUTPUT_DIR / secure_filename(filename)
        if not file_path.exists():
            return jsonify({'error': 'Arquivo não encontrado'}), 404

        return send_file(
            str(file_path),
            mimetype='video/mp4'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/status')
def get_status():
    """Retorna o status do processamento"""
    return jsonify(processing_status)


@app.errorhandler(413)
def request_entity_too_large(error):
    """Handler para arquivos muito grandes"""
    return jsonify({'error': 'Arquivo muito grande. Máximo: 500MB'}), 413


if __name__ == '__main__':
    print("=" * 50)
    print("VIDEO EDITOR - Sistema de Edição de Vídeo")
    print("=" * 50)
    print(f"Upload dir: {UPLOAD_DIR}")
    print(f"Output dir: {OUTPUT_DIR}")
    print("Iniciando servidor em http://localhost:5000")
    print("=" * 50)

    app.run(debug=True, host='0.0.0.0', port=5000)
