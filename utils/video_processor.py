"""
Video Processor - Processa e combina áudio, vídeo, imagens e legendas
"""
import os
import subprocess
import json
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Tuple


class VideoProcessor:
    """Processador de vídeo usando FFmpeg"""

    def __init__(self, upload_dir: str, output_dir: str):
        self.upload_dir = Path(upload_dir)
        self.output_dir = Path(output_dir)
        self.temp_dir = self.output_dir / "temp"
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # Configurações padrão
        self.width = 1920
        self.height = 1080
        self.fps = 30
        self.video_bitrate = "5M"
        self.audio_bitrate = "192k"

    def get_media_duration(self, file_path: str) -> float:
        """Obtém a duração de um arquivo de mídia em segundos"""
        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            file_path
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            data = json.loads(result.stdout)

            # Tenta pegar duração do formato
            if "format" in data and "duration" in data["format"]:
                return float(data["format"]["duration"])

            # Tenta pegar duração dos streams
            for stream in data.get("streams", []):
                if "duration" in stream:
                    return float(stream["duration"])

            return 0.0
        except Exception as e:
            print(f"Erro ao obter duração: {e}")
            return 0.0

    def is_video_file(self, file_path: str) -> bool:
        """Verifica se o arquivo é um vídeo"""
        video_extensions = {'.mp4', '.avi', '.mov', '.mkv', '.webm', '.flv', '.wmv'}
        return Path(file_path).suffix.lower() in video_extensions

    def is_image_file(self, file_path: str) -> bool:
        """Verifica se o arquivo é uma imagem"""
        image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp', '.tiff'}
        return Path(file_path).suffix.lower() in image_extensions

    def create_video_from_image(self, image_path: str, duration: float, output_path: str) -> str:
        """Cria um vídeo a partir de uma imagem com duração especificada"""
        cmd = [
            "ffmpeg", "-y",
            "-loop", "1",
            "-i", image_path,
            "-c:v", "libx264",
            "-t", str(duration),
            "-pix_fmt", "yuv420p",
            "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black",
            "-r", str(self.fps),
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def prepare_video_segment(self, video_path: str, duration: float, output_path: str) -> str:
        """Prepara um segmento de vídeo com duração e formato específicos"""
        # Obtém duração original do vídeo
        original_duration = self.get_media_duration(video_path)

        # Se o vídeo original é menor que a duração necessária, faz loop
        if original_duration < duration and original_duration > 0:
            loop_count = int(duration / original_duration) + 1
            cmd = [
                "ffmpeg", "-y",
                "-stream_loop", str(loop_count),
                "-i", video_path,
                "-t", str(duration),
                "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-r", str(self.fps),
                "-an",  # Remove áudio original do vídeo
                output_path
            ]
        else:
            # Corta o vídeo para a duração necessária
            cmd = [
                "ffmpeg", "-y",
                "-i", video_path,
                "-t", str(duration),
                "-vf", f"scale={self.width}:{self.height}:force_original_aspect_ratio=decrease,pad={self.width}:{self.height}:(ow-iw)/2:(oh-ih)/2:black",
                "-c:v", "libx264",
                "-pix_fmt", "yuv420p",
                "-r", str(self.fps),
                "-an",  # Remove áudio original do vídeo
                output_path
            ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def concatenate_videos(self, video_paths: List[str], output_path: str) -> str:
        """Concatena múltiplos vídeos em um único arquivo"""
        # Cria arquivo de lista para concatenação
        list_file = self.temp_dir / f"concat_list_{uuid.uuid4().hex}.txt"

        with open(list_file, "w") as f:
            for video_path in video_paths:
                f.write(f"file '{video_path}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            output_path
        ]

        subprocess.run(cmd, capture_output=True, check=True)

        # Remove arquivo temporário
        list_file.unlink()

        return output_path

    def mix_audio(self, narration_path: str, background_path: Optional[str],
                  background_volume_db: float, duration: float, output_path: str) -> str:
        """Mixa áudio de narração com background"""
        if background_path and os.path.exists(background_path):
            # Calcula o fator de volume a partir de dB
            # dB = 20 * log10(amplitude)
            # amplitude = 10^(dB/20)
            volume_factor = 10 ** (background_volume_db / 20)

            cmd = [
                "ffmpeg", "-y",
                "-i", narration_path,
                "-stream_loop", "-1",  # Loop infinito para o background
                "-i", background_path,
                "-filter_complex",
                f"[0:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo[a1];"
                f"[1:a]aformat=sample_fmts=fltp:sample_rates=44100:channel_layouts=stereo,volume={volume_factor}[a2];"
                f"[a1][a2]amix=inputs=2:duration=first:dropout_transition=2[aout]",
                "-map", "[aout]",
                "-t", str(duration),
                "-c:a", "aac",
                "-b:a", self.audio_bitrate,
                output_path
            ]
        else:
            # Apenas narração
            cmd = [
                "ffmpeg", "-y",
                "-i", narration_path,
                "-t", str(duration),
                "-c:a", "aac",
                "-b:a", self.audio_bitrate,
                output_path
            ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def add_subtitles(self, video_path: str, subtitle_path: str, output_path: str) -> str:
        """Adiciona legendas ao vídeo"""
        # Escapa o caminho do arquivo de legendas para o filtro do FFmpeg
        escaped_subtitle_path = subtitle_path.replace("\\", "/").replace(":", "\\:").replace("'", "\\'")

        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"subtitles='{escaped_subtitle_path}':force_style='FontSize=24,FontName=Arial,PrimaryColour=&HFFFFFF,OutlineColour=&H000000,Outline=2,Shadow=1'",
            "-c:v", "libx264",
            "-c:a", "copy",
            output_path
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def combine_video_audio(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Combina vídeo e áudio"""
        cmd = [
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-shortest",
            output_path
        ]

        subprocess.run(cmd, capture_output=True, check=True)
        return output_path

    def process(
        self,
        narration_path: str,
        media_files: List[str],
        subtitle_path: Optional[str],
        background_path: Optional[str],
        background_volume_db: float = -15.0
    ) -> Tuple[str, str]:
        """
        Processa todos os elementos e gera o vídeo final

        Args:
            narration_path: Caminho do áudio de narração
            media_files: Lista de caminhos de imagens/vídeos
            subtitle_path: Caminho do arquivo SRT (opcional)
            background_path: Caminho do áudio de background (opcional)
            background_volume_db: Volume do background em dB (padrão: -15)

        Returns:
            Tuple com (caminho do vídeo final, nome do arquivo)
        """
        try:
            # Gera ID único para este processamento
            process_id = uuid.uuid4().hex[:8]

            # 1. Obtém duração total da narração
            total_duration = self.get_media_duration(narration_path)
            if total_duration <= 0:
                raise ValueError("Não foi possível obter a duração do áudio de narração")

            print(f"Duração total da narração: {total_duration}s")

            # 2. Calcula duração de cada mídia
            num_media = len(media_files)
            if num_media == 0:
                raise ValueError("Nenhuma mídia (imagem/vídeo) foi fornecida")

            duration_per_media = total_duration / num_media
            print(f"Duração por mídia: {duration_per_media}s ({num_media} mídias)")

            # 3. Processa cada mídia
            temp_videos = []
            for i, media_path in enumerate(media_files):
                temp_video = str(self.temp_dir / f"segment_{process_id}_{i}.mp4")

                if self.is_image_file(media_path):
                    print(f"Processando imagem {i+1}/{num_media}: {media_path}")
                    self.create_video_from_image(media_path, duration_per_media, temp_video)
                elif self.is_video_file(media_path):
                    print(f"Processando vídeo {i+1}/{num_media}: {media_path}")
                    self.prepare_video_segment(media_path, duration_per_media, temp_video)
                else:
                    raise ValueError(f"Formato de arquivo não suportado: {media_path}")

                temp_videos.append(temp_video)

            # 4. Concatena todos os vídeos
            concat_video = str(self.temp_dir / f"concat_{process_id}.mp4")
            print("Concatenando vídeos...")
            self.concatenate_videos(temp_videos, concat_video)

            # 5. Mixa áudios
            mixed_audio = str(self.temp_dir / f"audio_{process_id}.aac")
            print("Mixando áudios...")
            self.mix_audio(narration_path, background_path, background_volume_db, total_duration, mixed_audio)

            # 6. Combina vídeo com áudio
            video_with_audio = str(self.temp_dir / f"video_audio_{process_id}.mp4")
            print("Combinando vídeo e áudio...")
            self.combine_video_audio(concat_video, mixed_audio, video_with_audio)

            # 7. Adiciona legendas (se fornecidas)
            output_filename = f"output_{process_id}.mp4"
            output_path = str(self.output_dir / output_filename)

            if subtitle_path and os.path.exists(subtitle_path):
                print("Adicionando legendas...")
                self.add_subtitles(video_with_audio, subtitle_path, output_path)
            else:
                # Copia o vídeo final
                shutil.copy(video_with_audio, output_path)

            # 8. Limpa arquivos temporários
            print("Limpando arquivos temporários...")
            for temp_video in temp_videos:
                if os.path.exists(temp_video):
                    os.remove(temp_video)
            for temp_file in [concat_video, mixed_audio, video_with_audio]:
                if os.path.exists(temp_file):
                    os.remove(temp_file)

            print(f"Vídeo final gerado: {output_path}")
            return output_path, output_filename

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Erro no FFmpeg: {e.stderr.decode() if e.stderr else str(e)}")
        except Exception as e:
            raise RuntimeError(f"Erro no processamento: {str(e)}")

    def cleanup_uploads(self, files: List[str]):
        """Remove arquivos de upload após processamento"""
        for file_path in files:
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Erro ao remover {file_path}: {e}")
