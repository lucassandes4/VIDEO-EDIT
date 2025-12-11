"""
Video AI Tool v2 - Editor de Vídeo com Imagens Personalizadas
VERSÃO COMPLETA - Com Efeitos Visuais e Overlays
"""
from flask import Flask, render_template, request, jsonify, send_file, send_from_directory
import os
import json
import whisper
import subprocess
from pathlib import Path
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
import shutil
import base64

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=2)

# Diretórios
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "output"
TEMP_DIR = BASE_DIR / "temp"
OVERLAYS_DIR = BASE_DIR / "overlays"

for d in [UPLOAD_DIR, OUTPUT_DIR, TEMP_DIR, OVERLAYS_DIR]:
    d.mkdir(exist_ok=True)

# Estado global
project_state = {
    "audio_path": None,
    "segments": [],
    "images": [],
    "subtitle_config": {
        "font": "Arial",
        "size": 48,
        "color": "#FFFFFF",
        "bg_color": "none",
        "position": "bottom",
        "animation": "none"
    },
    "status": "idle",
    "project_dir": None
}

# Modelo Whisper
whisper_model = None

def get_whisper_model():
    global whisper_model
    if whisper_model is None:
        print("🔄 Carregando modelo Whisper...")
        whisper_model = whisper.load_model("base")
        print("✅ Modelo carregado!")
    return whisper_model


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/uploads/<filename>')
def serve_upload(filename):
    return send_from_directory(UPLOAD_DIR, filename)


@app.route('/output/<path:filename>')
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route('/status')
def status():
    return jsonify(project_state)


# ==================== OVERLAYS ====================

@app.route('/list_overlays')
def list_overlays():
    """Lista overlays disponíveis"""
    overlays = []
    for f in OVERLAYS_DIR.iterdir():
        if f.suffix.lower() in ['.mp4', '.mov', '.webm', '.gif', '.png', '.jpg']:
            overlays.append({
                "name": f.stem,
                "filename": f.name,
                "type": "video" if f.suffix.lower() in ['.mp4', '.mov', '.webm', '.gif'] else "image"
            })
    return jsonify({"overlays": overlays})


@app.route('/upload_overlay', methods=['POST'])
def upload_overlay():
    """Upload de overlay personalizado"""
    if 'overlay' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    
    file = request.files['overlay']
    if file.filename == '':
        return jsonify({"error": "Arquivo vazio"}), 400
    
    # Salvar overlay
    overlay_path = OVERLAYS_DIR / file.filename
    file.save(str(overlay_path))
    
    return jsonify({
        "success": True,
        "filename": file.filename
    })


# ==================== ÁUDIO E TRANSCRIÇÃO ====================

@app.route('/upload_audio', methods=['POST'])
def upload_audio():
    if 'audio' not in request.files:
        return jsonify({"error": "Nenhum arquivo enviado"}), 400
    
    file = request.files['audio']
    if file.filename == '':
        return jsonify({"error": "Arquivo vazio"}), 400
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    project_dir = OUTPUT_DIR / f"projeto_{timestamp}"
    project_dir.mkdir(exist_ok=True)
    (project_dir / "images").mkdir(exist_ok=True)
    
    audio_path = project_dir / file.filename
    file.save(str(audio_path))
    
    project_state["audio_path"] = str(audio_path)
    project_state["project_dir"] = str(project_dir)
    project_state["status"] = "audio_uploaded"
    project_state["images"] = []
    
    return jsonify({
        "success": True,
        "audio_path": str(audio_path),
        "project_dir": str(project_dir)
    })


@app.route('/transcribe', methods=['POST'])
def transcribe():
    if not project_state["audio_path"]:
        return jsonify({"error": "Nenhum áudio carregado"}), 400
    
    project_state["status"] = "transcribing"
    
    try:
        model = get_whisper_model()
        result = model.transcribe(
            project_state["audio_path"],
            language="pt",
            verbose=False
        )
        
        segments = []
        for seg in result["segments"]:
            segments.append({
                "id": seg["id"],
                "start": round(seg["start"], 2),
                "end": round(seg["end"], 2),
                "text": seg["text"].strip(),
                "edited": False
            })
        
        project_state["segments"] = segments
        project_state["status"] = "transcribed"
        
        return jsonify({
            "success": True,
            "segments": segments,
            "full_text": result["text"]
        })
    except Exception as e:
        project_state["status"] = "error"
        return jsonify({"error": str(e)}), 500


@app.route('/update_segments', methods=['POST'])
def update_segments():
    data = request.json
    project_state["segments"] = data["segments"]
    return jsonify({"success": True})


@app.route('/update_subtitle_config', methods=['POST'])
def update_subtitle_config():
    data = request.json
    project_state["subtitle_config"].update(data)
    return jsonify({"success": True})


# ==================== IMAGENS ====================

@app.route('/upload_image', methods=['POST'])
def upload_image():
    if 'image' not in request.files:
        return jsonify({"error": "Nenhuma imagem enviada"}), 400
    
    if not project_state["project_dir"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = OUTPUT_DIR / f"projeto_{timestamp}"
        project_dir.mkdir(exist_ok=True)
        (project_dir / "images").mkdir(exist_ok=True)
        project_state["project_dir"] = str(project_dir)
    
    file = request.files['image']
    project_dir = Path(project_state["project_dir"])
    
    img_index = len(project_state["images"]) + 1
    ext = Path(file.filename).suffix or ".png"
    img_filename = f"img_{img_index:03d}{ext}"
    img_path = project_dir / "images" / img_filename
    file.save(str(img_path))
    
    image_config = create_default_image_config(img_index, img_filename, str(img_path))
    project_state["images"].append(image_config)
    
    return jsonify({
        "success": True,
        "image": image_config
    })


@app.route('/upload_images_batch', methods=['POST'])
def upload_images_batch():
    if 'images' not in request.files:
        return jsonify({"error": "Nenhuma imagem enviada"}), 400
    
    if not project_state["project_dir"]:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        project_dir = OUTPUT_DIR / f"projeto_{timestamp}"
        project_dir.mkdir(exist_ok=True)
        (project_dir / "images").mkdir(exist_ok=True)
        project_state["project_dir"] = str(project_dir)
    
    files = request.files.getlist('images')
    project_dir = Path(project_state["project_dir"])
    uploaded = []
    
    for file in files:
        img_index = len(project_state["images"]) + 1
        ext = Path(file.filename).suffix or ".png"
        img_filename = f"img_{img_index:03d}{ext}"
        img_path = project_dir / "images" / img_filename
        file.save(str(img_path))
        
        image_config = create_default_image_config(img_index, img_filename, str(img_path))
        project_state["images"].append(image_config)
        uploaded.append(image_config)
    
    return jsonify({
        "success": True,
        "images": uploaded
    })


def create_default_image_config(img_index, filename, path):
    """Cria configuração padrão para uma imagem com todos os efeitos disponíveis"""
    return {
        "id": img_index,
        "filename": filename,
        "path": path,
        "start_time": 0.0,
        "end_time": 5.0,
        "effects": {
            # Filtros de cor
            "filter": "none",  # none, grayscale, sepia, vintage, cold, warm
            "brightness": 1.0,
            "contrast": 1.0,
            "saturation": 1.0,
            
            # Efeitos visuais FFmpeg
            "glow": 0,           # 0-100 intensidade do brilho
            "vignette": 0,       # 0-100 intensidade da vinheta
            "grain": 0,          # 0-100 intensidade do granulado
            "blur": 0,           # 0-20 desfoque
            "sharpen": 0,        # 0-100 nitidez
            "light_leak": "none", # none, warm, cool, rainbow
            
            # Movimento
            "zoom": "none",      # none, zoom_in, zoom_out
            "pan": "none"        # none, left_to_right, right_to_left, top_to_bottom, bottom_to_top
        },
        "overlay": {
            "enabled": False,
            "filename": "",      # Nome do arquivo de overlay
            "opacity": 0.5,      # 0-1 opacidade
            "blend_mode": "screen"  # screen, overlay, add, multiply
        },
        "transition_in": {
            "type": "none",      # none, fade, slide_left, slide_right, zoom, blur
            "duration": 0.5
        },
        "transition_out": {
            "type": "none",
            "duration": 0.5
        }
    }


@app.route('/update_image/<int:image_id>', methods=['POST'])
def update_image(image_id):
    data = request.json
    
    for img in project_state["images"]:
        if img["id"] == image_id:
            if "start_time" in data:
                img["start_time"] = data["start_time"]
            if "end_time" in data:
                img["end_time"] = data["end_time"]
            if "effects" in data:
                img["effects"].update(data["effects"])
            if "overlay" in data:
                img["overlay"].update(data["overlay"])
            if "transition_in" in data:
                img["transition_in"].update(data["transition_in"])
            if "transition_out" in data:
                img["transition_out"].update(data["transition_out"])
            return jsonify({"success": True, "image": img})
    
    return jsonify({"error": "Imagem não encontrada"}), 404


@app.route('/remove_image/<int:image_id>', methods=['DELETE'])
def remove_image(image_id):
    for i, img in enumerate(project_state["images"]):
        if img["id"] == image_id:
            try:
                os.remove(img["path"])
            except:
                pass
            project_state["images"].pop(i)
            return jsonify({"success": True})
    
    return jsonify({"error": "Imagem não encontrada"}), 404


@app.route('/get_image/<int:image_id>')
def get_image(image_id):
    for img in project_state["images"]:
        if img["id"] == image_id:
            return send_file(img["path"])
    return jsonify({"error": "Imagem não encontrada"}), 404


# ==================== MONTAGEM DO VÍDEO ====================

def build_visual_effects_filter(effects):
    """Constrói filtros visuais FFmpeg"""
    filters = []
    
    # Filtro de cor
    if effects["filter"] == "grayscale":
        filters.append("colorchannelmixer=.3:.4:.3:0:.3:.4:.3:0:.3:.4:.3")
    elif effects["filter"] == "sepia":
        filters.append("colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131")
    elif effects["filter"] == "vintage":
        filters.append("curves=preset=vintage")
    elif effects["filter"] == "cold":
        filters.append("colorbalance=bs=0.3")
    elif effects["filter"] == "warm":
        filters.append("colorbalance=rs=0.3:gs=0.1")
    
    # Brilho, contraste, saturação
    eq_parts = []
    if effects.get("brightness", 1.0) != 1.0:
        eq_parts.append(f"brightness={effects['brightness'] - 1}")
    if effects.get("contrast", 1.0) != 1.0:
        eq_parts.append(f"contrast={effects['contrast']}")
    if effects.get("saturation", 1.0) != 1.0:
        eq_parts.append(f"saturation={effects['saturation']}")
    if eq_parts:
        filters.append(f"eq={':'.join(eq_parts)}")
    
    # Glow (brilho suave)
    glow = effects.get("glow", 0)
    if glow > 0:
        glow_amount = glow / 100 * 2
        filters.append(f"gblur=sigma={glow_amount}")
        # Depois precisamos fazer blend, simplificado aqui
    
    # Vinheta (escurecimento nas bordas)
    vignette = effects.get("vignette", 0)
    if vignette > 0:
        vignette_angle = 0.3 + (vignette / 100 * 0.7)
        filters.append(f"vignette=PI/{4 - vignette/50}")
    
    # Film Grain (granulado)
    grain = effects.get("grain", 0)
    if grain > 0:
        grain_strength = grain / 100 * 50
        filters.append(f"noise=alls={int(grain_strength)}:allf=t")
    
    # Blur (desfoque)
    blur = effects.get("blur", 0)
    if blur > 0:
        filters.append(f"gblur=sigma={blur}")
    
    # Sharpen (nitidez)
    sharpen = effects.get("sharpen", 0)
    if sharpen > 0:
        sharpen_amount = sharpen / 100 * 2
        filters.append(f"unsharp=5:5:{sharpen_amount}:5:5:0")
    
    # Light Leak (vazamento de luz)
    light_leak = effects.get("light_leak", "none")
    if light_leak == "warm":
        filters.append("colorbalance=rs=0.2:gs=0.1:bs=-0.1:rm=0.1:gm=0.05")
    elif light_leak == "cool":
        filters.append("colorbalance=rs=-0.1:gs=0.05:bs=0.2:rm=-0.05:bm=0.1")
    elif light_leak == "rainbow":
        filters.append("hue=s=1.5")
    
    return filters


def create_clip_with_effects(img, clip_path, width=1280, height=720):
    """Cria um clip de vídeo a partir de uma imagem com todos os efeitos"""
    
    duration = img["end_time"] - img["start_time"]
    effects = img["effects"]
    overlay_config = img.get("overlay", {})
    trans_in = img["transition_in"]
    trans_out = img["transition_out"]
    fps = 24
    total_frames = int(duration * fps)
    
    # Verificar se tem zoom/pan (Ken Burns)
    zoom_effect = effects.get("zoom", "none")
    pan_effect = effects.get("pan", "none")
    
    # Determinar efeito de movimento
    motion_effect = zoom_effect if zoom_effect != "none" else pan_effect
    
    if motion_effect != "none":
        # Usar zoompan para efeito Ken Burns
        filter_parts = []
        
        # Escalar imagem grande primeiro
        filter_parts.append("scale=8000:-1")
        
        # Construir zoompan
        if motion_effect == "zoom_in":
            zoompan = f"zoompan=z='min(zoom+0.001,1.5)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
        elif motion_effect == "zoom_out":
            zoompan = f"zoompan=z='if(lte(zoom,1.0),1.5,max(1.001,zoom-0.001))':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
        elif motion_effect == "left_to_right":
            zoompan = f"zoompan=z='1.2':x='if(lte(on,1),0,min(x+4,(iw-iw/zoom)))':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
        elif motion_effect == "right_to_left":
            zoompan = f"zoompan=z='1.2':x='if(lte(on,1),(iw-iw/zoom),max(0,x-4))':y='ih/2-(ih/zoom/2)':d={total_frames}:s={width}x{height}:fps={fps}"
        elif motion_effect == "top_to_bottom":
            zoompan = f"zoompan=z='1.2':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),0,min(y+3,(ih-ih/zoom)))':d={total_frames}:s={width}x{height}:fps={fps}"
        elif motion_effect == "bottom_to_top":
            zoompan = f"zoompan=z='1.2':x='iw/2-(iw/zoom/2)':y='if(lte(on,1),(ih-ih/zoom),max(0,y-3))':d={total_frames}:s={width}x{height}:fps={fps}"
        else:
            zoompan = f"zoompan=z='1':d={total_frames}:s={width}x{height}:fps={fps}"
        
        filter_parts.append(zoompan)
        
        # Adicionar efeitos visuais
        visual_filters = build_visual_effects_filter(effects)
        filter_parts.extend(visual_filters)
        
        # Transições fade
        if trans_in["type"] == "fade" and trans_in["duration"] > 0:
            filter_parts.append(f"fade=t=in:st=0:d={trans_in['duration']}")
        
        if trans_out["type"] == "fade" and trans_out["duration"] > 0:
            fade_out_start = duration - trans_out["duration"]
            filter_parts.append(f"fade=t=out:st={fade_out_start}:d={trans_out['duration']}")
        
        filter_str = ",".join(filter_parts)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", img["path"],
            "-vf", filter_str,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            str(clip_path)
        ]
    else:
        # Sem movimento - usar loop simples
        filter_parts = []
        
        # Escalar
        filter_parts.append(f"scale={width}:{height}:force_original_aspect_ratio=decrease")
        filter_parts.append(f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:black")
        
        # Efeitos visuais
        visual_filters = build_visual_effects_filter(effects)
        filter_parts.extend(visual_filters)
        
        # Transições
        if trans_in["type"] == "fade" and trans_in["duration"] > 0:
            filter_parts.append(f"fade=t=in:st=0:d={trans_in['duration']}")
        elif trans_in["type"] == "blur" and trans_in["duration"] > 0:
            # Blur in - começa desfocado e fica nítido
            filter_parts.append(f"gblur=sigma='max(0,20-20*t/{trans_in['duration']})'")
        
        if trans_out["type"] == "fade" and trans_out["duration"] > 0:
            fade_out_start = duration - trans_out["duration"]
            filter_parts.append(f"fade=t=out:st={fade_out_start}:d={trans_out['duration']}")
        elif trans_out["type"] == "blur" and trans_out["duration"] > 0:
            blur_start = duration - trans_out["duration"]
            filter_parts.append(f"gblur=sigma='if(gte(t,{blur_start}),20*(t-{blur_start})/{trans_out['duration']},0)'")
        
        filter_str = ",".join(filter_parts) if filter_parts else "null"
        
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", img["path"],
            "-vf", filter_str,
            "-t", str(duration),
            "-c:v", "libx264",
            "-pix_fmt", "yuv420p",
            "-r", str(fps),
            str(clip_path)
        ]
    
    print(f"  Executando FFmpeg...")
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    if result.returncode != 0:
        print(f"  ❌ Erro FFmpeg: {result.stderr[:500]}")
        return False
    
    # Aplicar overlay se configurado
    if overlay_config.get("enabled") and overlay_config.get("filename"):
        clip_with_overlay = apply_overlay(clip_path, overlay_config, duration, width, height)
        if clip_with_overlay:
            shutil.move(clip_with_overlay, clip_path)
    
    return True


def apply_overlay(clip_path, overlay_config, duration, width, height):
    """Aplica overlay (faíscas, bokeh, etc.) ao clip"""
    
    overlay_file = OVERLAYS_DIR / overlay_config["filename"]
    if not overlay_file.exists():
        print(f"  ⚠️ Overlay não encontrado: {overlay_file}")
        return None
    
    opacity = overlay_config.get("opacity", 0.5)
    blend_mode = overlay_config.get("blend_mode", "screen")
    
    output_path = TEMP_DIR / f"overlay_{datetime.now().timestamp()}.mp4"
    
    # Mapear blend modes para FFmpeg
    blend_modes = {
        "screen": "screen",
        "overlay": "overlay",
        "add": "addition",
        "multiply": "multiply",
        "lighten": "lighten",
        "softlight": "softlight"
    }
    blend = blend_modes.get(blend_mode, "screen")
    
    # Comando FFmpeg para overlay
    # O overlay é redimensionado e aplicado com blend
    filter_complex = f"[1:v]scale={width}:{height},format=rgba,colorchannelmixer=aa={opacity}[ov];[0:v][ov]blend=all_mode='{blend}'"
    
    cmd = [
        "ffmpeg", "-y",
        "-i", str(clip_path),
        "-stream_loop", "-1",  # Loop do overlay
        "-i", str(overlay_file),
        "-filter_complex", filter_complex,
        "-t", str(duration),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(output_path)
    ]
    
    result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
    
    if result.returncode != 0:
        print(f"  ⚠️ Erro ao aplicar overlay: {result.stderr[:300]}")
        return None
    
    return str(output_path)


@app.route('/assemble_video', methods=['POST'])
def assemble_video():
    if not project_state["images"]:
        return jsonify({"error": "Nenhuma imagem adicionada"}), 400
    
    project_state["status"] = "assembling"
    project_dir = Path(project_state["project_dir"])
    
    try:
        images = sorted(project_state["images"], key=lambda x: x["start_time"])
        
        print(f"🎬 Montando vídeo com {len(images)} imagens...")
        
        clip_files = []
        for i, img in enumerate(images):
            print(f"🖼️ Processando imagem {i+1}/{len(images)}: {img['filename']}")
            
            clip_path = TEMP_DIR / f"clip_{i:03d}.mp4"
            success = create_clip_with_effects(img, clip_path)
            
            if success and clip_path.exists():
                clip_files.append(str(clip_path))
                print(f"   ✅ Clip criado!")
            else:
                print(f"   ❌ Falha ao criar clip")
        
        if not clip_files:
            return jsonify({"error": "Nenhum clip foi criado"}), 500
        
        print("🔗 Concatenando clips...")
        
        if len(clip_files) == 1:
            video_no_audio = clip_files[0]
        else:
            video_no_audio = TEMP_DIR / "video_no_audio.mp4"
            
            concat_list = TEMP_DIR / "concat_list.txt"
            with open(concat_list, "w", encoding="utf-8") as f:
                for clip in clip_files:
                    clip_escaped = clip.replace("\\", "/")
                    f.write(f"file '{clip_escaped}'\n")
            
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_list),
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                str(video_no_audio)
            ]
            subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
        
        # Adicionar áudio
        if project_state["audio_path"]:
            print("🔊 Adicionando áudio...")
            video_with_audio = TEMP_DIR / "video_with_audio.mp4"
            cmd = [
                "ffmpeg", "-y",
                "-i", str(video_no_audio),
                "-i", project_state["audio_path"],
                "-c:v", "copy",
                "-c:a", "aac",
                "-shortest",
                str(video_with_audio)
            ]
            subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            current_video = video_with_audio
        else:
            current_video = video_no_audio
        
        # Adicionar legendas
        if project_state["segments"]:
            print("📝 Adicionando legendas...")
            
            ass_path = create_ass_subtitles(
                project_state["segments"],
                project_state["subtitle_config"],
                TEMP_DIR / "subtitles.ass"
            )
            
            video_final = project_dir / "video_final.mp4"
            ass_path_escaped = str(ass_path).replace("\\", "/").replace(":", "\\:")
            
            cmd = [
                "ffmpeg", "-y",
                "-i", str(current_video),
                "-vf", f"ass='{ass_path_escaped}'",
                "-c:v", "libx264",
                "-c:a", "copy",
                str(video_final)
            ]
            result = subprocess.run(cmd, capture_output=True, encoding='utf-8', errors='ignore')
            if result.returncode != 0:
                shutil.copy(current_video, video_final)
        else:
            video_final = project_dir / "video_final.mp4"
            shutil.copy(str(current_video), str(video_final))
        
        # Limpar temporários
        for clip in clip_files:
            try:
                os.remove(clip)
            except:
                pass
        
        project_state["status"] = "completed"
        project_state["video_path"] = str(video_final)
        
        print("✅ Vídeo montado com sucesso!")
        
        return jsonify({
            "success": True,
            "video_path": str(video_final)
        })
        
    except Exception as e:
        project_state["status"] = "error"
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def create_ass_subtitles(segments, config, output_path):
    """Cria arquivo ASS com legendas estilizadas"""
    
    def hex_to_ass(hex_color):
        hex_color = hex_color.lstrip('#')
        r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
        return f"&H00{b:02X}{g:02X}{r:02X}"
    
    alignment = {"top": 8, "center": 5, "bottom": 2}
    align = alignment.get(config["position"], 2)
    
    if config["bg_color"] == "none":
        border_style = 1
        back_color = "&H00000000"
    else:
        border_style = 3
        back_color = hex_to_ass(config["bg_color"])
    
    primary_color = hex_to_ass(config["color"])
    
    ass_content = f"""[Script Info]
Title: Video AI Tool Subtitles
ScriptType: v4.00+
PlayResX: 1280
PlayResY: 720

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{config["font"]},{config["size"]},{primary_color},&H000000FF,&H00000000,{back_color},0,0,0,0,100,100,0,0,{border_style},2,1,{align},10,10,30,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    
    for seg in segments:
        start = format_ass_time(seg["start"])
        end = format_ass_time(seg["end"])
        text = seg["text"].replace("\n", "\\N")
        
        if config["animation"] == "fade":
            text = f"{{\\fad(300,300)}}{text}"
        elif config["animation"] == "typewriter":
            text = f"{{\\fad(0,0)}}{text}"
        
        ass_content += f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n"
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(ass_content)
    
    return output_path


def format_ass_time(seconds):
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    centis = int((seconds % 1) * 100)
    return f"{hours}:{minutes:02d}:{secs:02d}.{centis:02d}"


@app.route('/download_video')
def download_video():
    if not project_state.get("video_path"):
        return jsonify({"error": "Nenhum vídeo gerado"}), 404
    
    return send_file(
        project_state["video_path"],
        as_attachment=True,
        download_name="video_final.mp4"
    )


@app.route('/reset_project', methods=['POST'])
def reset_project():
    global project_state
    project_state = {
        "audio_path": None,
        "segments": [],
        "images": [],
        "subtitle_config": {
            "font": "Arial",
            "size": 48,
            "color": "#FFFFFF",
            "bg_color": "none",
            "position": "bottom",
            "animation": "none"
        },
        "status": "idle",
        "project_dir": None
    }
    return jsonify({"success": True})


if __name__ == '__main__':
    print("=" * 50)
    print("🎬 Video AI Tool v2 - Editor de Vídeo")
    print("   Com Efeitos Visuais e Overlays")
    print("=" * 50)
    print(f"📁 Pasta de overlays: {OVERLAYS_DIR}")
    print("   Coloque vídeos de efeitos (.mp4, .mov, .webm)")
    print("   Ex: sparkles.mp4, bokeh.mp4, light_leak.mp4")
    print("=" * 50)
    print("Acesse: http://localhost:5000")
    print("=" * 50)
    app.run(debug=True, port=5000, threaded=True)
