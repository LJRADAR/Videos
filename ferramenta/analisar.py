#!/usr/bin/env python3
"""Analisa um vídeo para escolher os melhores trechos: duração, resolução,
mudanças de cena e uma folha de contato (miniaturas a cada N segundos).

Exemplo:
  python3 ferramenta/analisar.py entrada/video.mp4 --cada 5
Gera em analise/<nome>/: cenas.txt e contato_XX.jpg
"""
import argparse
import re
import subprocess
from pathlib import Path


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("entrada")
    p.add_argument("--cada", type=float, default=5, help="segundos entre miniaturas")
    p.add_argument("--limiar", type=float, default=0.3, help="sensibilidade da troca de cena (0-1)")
    a = p.parse_args()

    entrada = Path(a.entrada)
    pasta = Path("analise") / entrada.stem
    pasta.mkdir(parents=True, exist_ok=True)

    print(subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,r_frame_rate", "-of", "default=nw=1", str(entrada)],
        capture_output=True, text=True).stdout)

    log = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(entrada), "-vf",
         f"select='gt(scene,{a.limiar})',showinfo", "-an", "-f", "null", "-"],
        capture_output=True, text=True).stderr
    cenas = [float(t) for t in re.findall(r"pts_time:([\d.]+)", log)]
    (pasta / "cenas.txt").write_text("\n".join(f"{t:.2f}" for t in cenas))
    print(f"{len(cenas)} trocas de cena -> {pasta / 'cenas.txt'}")

    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(entrada), "-vf",
         f"fps=1/{a.cada},scale=320:-2,drawtext=text='%{{pts\\:hms}}':x=5:y=5:fontsize=18:"
         f"fontcolor=white:box=1:boxcolor=black@0.6,tile=5x4",
         str(pasta / "contato_%02d.jpg")], check=True)
    print(f"Folhas de contato -> {pasta}/contato_*.jpg (uma miniatura a cada {a.cada:g}s)")


if __name__ == "__main__":
    main()
