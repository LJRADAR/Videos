#!/usr/bin/env python3
"""Converte um vídeo horizontal (16:9) em vertical (9:16, 1080x1920) para Shorts/Reels/TikTok.

Modos:
  fundo  - vídeo inteiro no centro, com uma cópia desfocada preenchendo o fundo (padrão)
  corte  - corta o centro do quadro para preencher a tela toda (bom para pessoa falando)

Exemplos:
  python3 ferramenta/vertical.py entrada/video.mp4
  python3 ferramenta/vertical.py entrada/video.mp4 --modo corte --max 59
  python3 ferramenta/vertical.py entrada/video.mp4 --inicio 12 --max 179 --saida saida/short.mp4
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

LARGURA, ALTURA = 1080, 1920
LIMITE_SHORTS = 179  # YouTube Shorts aceita até 3:00; deixamos 1s de folga


def info(caminho):
    saida = subprocess.run(
        ["ffprobe", "-v", "error", "-show_streams", "-show_format", "-of", "json", str(caminho)],
        check=True, capture_output=True, text=True,
    ).stdout
    dados = json.loads(saida)
    tem_audio = any(s["codec_type"] == "audio" for s in dados["streams"])
    return float(dados["format"]["duration"]), tem_audio


def filtro_video(modo):
    if modo == "corte":
        return f"[0:v]scale=-2:{ALTURA},crop={LARGURA}:{ALTURA},setsar=1[v]"
    return (
        f"[0:v]split[a][b];"
        f"[a]scale={LARGURA}:{ALTURA}:force_original_aspect_ratio=increase,"
        f"crop={LARGURA}:{ALTURA},boxblur=30:3,eq=brightness=-0.08[fundo];"
        f"[b]scale={LARGURA}:-2[frente];"
        f"[fundo][frente]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
    )


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("entrada")
    p.add_argument("--saida", help="arquivo final (padrão: saida/<nome>_vertical.mp4)")
    p.add_argument("--modo", choices=["fundo", "corte"], default="fundo")
    p.add_argument("--inicio", type=float, default=0, help="segundo onde começar")
    p.add_argument("--max", type=float, default=LIMITE_SHORTS, help="duração máxima em segundos")
    a = p.parse_args()

    entrada = Path(a.entrada)
    saida = Path(a.saida) if a.saida else Path("saida") / f"{entrada.stem}_vertical.mp4"
    saida.parent.mkdir(parents=True, exist_ok=True)

    duracao, tem_audio = info(entrada)
    final = min(duracao - a.inicio, a.max)
    if duracao - a.inicio > a.max:
        print(f"Aviso: vídeo tem {duracao - a.inicio:.0f}s; cortado em {a.max:.0f}s.", file=sys.stderr)

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-stats",
           "-ss", str(a.inicio), "-i", str(entrada), "-t", f"{final:.3f}",
           "-filter_complex", filtro_video(a.modo), "-map", "[v]"]
    if tem_audio:
        cmd += ["-map", "0:a:0", "-af", "loudnorm=I=-14:TP=-1.5:LRA=11", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-c:v", "libx264", "-preset", "medium", "-crf", "20", "-pix_fmt", "yuv420p",
            "-movflags", "+faststart", str(saida)]
    subprocess.run(cmd, check=True)
    print(f"Pronto: {saida} ({final:.0f}s, {LARGURA}x{ALTURA})")


if __name__ == "__main__":
    main()
