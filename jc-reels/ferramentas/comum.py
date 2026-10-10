"""Funções compartilhadas pelos scripts do JC-Reels.

Nenhuma função aqui apaga, move ou altera arquivos de material: elas só leem
o vídeo original e gravam arquivos novos em analise/ ou prontos/.
"""
import json
import subprocess
import sys
from functools import lru_cache
from pathlib import Path

EXT_VIDEO = {".mp4", ".mov", ".mxf", ".mts", ".m2ts", ".avi", ".mkv"}
EXT_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".opus"}


def rodar(cmd, **kw):
    """Roda um comando e devolve o resultado (sem levantar erro)."""
    return subprocess.run([str(c) for c in cmd], capture_output=True, text=True,
                          encoding="utf-8", errors="replace", **kw)


def checar_ffmpeg():
    for prog in ("ffmpeg", "ffprobe"):
        try:
            rodar([prog, "-version"])
        except FileNotFoundError:
            sys.exit(f"ERRO: '{prog}' não encontrado. Rode o instalar.ps1 e abra um PowerShell novo.")


def sondar(caminho):
    """Lê duração, resolução, fps, codec e rotação de um vídeo com ffprobe."""
    r = rodar(["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", caminho])
    if r.returncode:
        sys.exit(f"ERRO ao ler {caminho}:\n{r.stderr}")
    dados = json.loads(r.stdout)
    v = next((s for s in dados["streams"] if s["codec_type"] == "video"), None)
    if v is None:
        sys.exit(f"ERRO: {caminho} não tem vídeo.")
    num, den = (v.get("avg_frame_rate") or v.get("r_frame_rate") or "30/1").split("/")
    fps = float(num) / float(den) if float(den) else 30.0
    rot = 0
    for sd in v.get("side_data_list", []):
        if "rotation" in sd:
            rot = int(float(sd["rotation"]))
    rot = int(v.get("tags", {}).get("rotate", rot))
    w, h = int(v["width"]), int(v["height"])
    if abs(rot) % 180 == 90:  # vídeo gravado em pé (celular): troca largura/altura
        w, h = h, w
    return {
        "arquivo": str(caminho),
        "duracao": float(dados["format"].get("duration") or v.get("duration") or 0),
        "largura": w,
        "altura": h,
        "fps": round(fps, 3),
        "codec": v.get("codec_name"),
        "perfil": v.get("profile"),
        "pix_fmt": v.get("pix_fmt"),
        "bitrate_mbps": round(int(dados["format"].get("bit_rate") or 0) / 1e6, 1),
        "tem_audio": any(s["codec_type"] == "audio" for s in dados["streams"]),
    }


@lru_cache(maxsize=None)
def codificador():
    """Escolhe o codificador H.264: Quick Sync, NVENC ou AMF se funcionarem; senão libx264."""
    for enc in ("h264_qsv", "h264_nvenc", "h264_amf"):
        # testa com os mesmos parâmetros usados na exportação de verdade
        r = rodar(["ffmpeg", "-hide_banner", "-v", "error", "-f", "lavfi", "-i",
                   "testsrc2=s=1080x1920:d=0.5", *args_codificador(enc), "-f", "null", "-"])
        if r.returncode == 0:
            return enc
    return "libx264"


def args_codificador(enc, qualidade="alta"):
    """Parâmetros de qualidade de cada codificador. 'alta' fica visualmente sem perdas."""
    q = {"alta": 18, "maxima": 15}[qualidade]
    if enc == "h264_qsv":
        return ["-c:v", "h264_qsv", "-preset", "slower", "-global_quality", str(q),
                "-profile:v", "high", "-pix_fmt", "nv12"]
    if enc == "h264_nvenc":
        return ["-c:v", "h264_nvenc", "-preset", "p7", "-rc", "vbr", "-cq", str(q),
                "-b:v", "0", "-profile:v", "high", "-pix_fmt", "yuv420p"]
    if enc == "h264_amf":
        return ["-c:v", "h264_amf", "-quality", "quality", "-rc", "cqp",
                "-qp_i", str(q), "-qp_p", str(q + 2), "-profile:v", "high", "-pix_fmt", "yuv420p"]
    return ["-c:v", "libx264", "-preset", "slow", "-crf", str(q - 2),
            "-profile:v", "high", "-pix_fmt", "yuv420p"]


def listar(pasta, extensoes):
    pasta = Path(pasta)
    if not pasta.is_dir():
        return []
    return sorted(p for p in pasta.iterdir() if p.is_file() and p.suffix.lower() in extensoes)


def hms(seg):
    seg = max(0.0, seg)
    m, s = divmod(seg, 60)
    return f"{int(m):02d}:{s:05.2f}"
