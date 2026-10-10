#!/usr/bin/env python3
"""Baixa só o áudio de um link (YouTube etc.) para <trabalho>/musica/, em MP3 de alta qualidade.

Usa o yt-dlp. Só baixa: nada do trabalho é enviado para a internet.
Se já houver música na pasta, não baixa (nada é apagado ou substituído).

Atenção: use músicas que você tem direito de usar. Música com direitos autorais pode
ser silenciada pelo Instagram, principalmente em conta comercial.

Exemplo:
  py ferramentas\\baixar_musica.py C:\\JC-Reels\\2026-10-cabeleireiro "https://www.youtube.com/watch?v=..."
"""
import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import EXT_MUSICA, checar_ffmpeg, listar  # noqa: E402


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trabalho")
    p.add_argument("link")
    a = p.parse_args()

    checar_ffmpeg()
    pasta = Path(a.trabalho) / "musica"
    pasta.mkdir(parents=True, exist_ok=True)
    existentes = listar(pasta, EXT_MUSICA)
    if existentes:
        sys.exit(f"Já existe música em {pasta}: {', '.join(m.name for m in existentes)}\n"
                 "Para trocar, tire esse arquivo da pasta primeiro e rode de novo.")

    print("Baixando o áudio (só o som, sem o vídeo)...")
    r = subprocess.run([sys.executable, "-m", "yt_dlp", "--no-playlist", "-x",
                        "--audio-format", "mp3", "--audio-quality", "0",
                        "--restrict-filenames", "--no-progress",
                        "-o", str(pasta / "%(title).80s.%(ext)s"), a.link])
    if r.returncode:
        sys.exit("ERRO ao baixar. Confira o link. Se o erro persistir, atualize o yt-dlp com:\n"
                 "  py -m pip install -U yt-dlp")
    baixados = listar(pasta, EXT_MUSICA)
    if not baixados:
        sys.exit("ERRO: o download terminou, mas nenhum arquivo de áudio apareceu na pasta.")
    print(f"Pronto: {baixados[0]}")


if __name__ == "__main__":
    main()
