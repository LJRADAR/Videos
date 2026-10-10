#!/usr/bin/env python3
"""Passo 1 de cada trabalho: lê o material e monta as folhas de contato.

Para cada vídeo em <trabalho>/material/:
  - lê duração, resolução, fps e codec (ffprobe)
  - tira um quadro pequeno a cada N segundos (padrão 2 s)
  - mede nitidez, brilho, movimento e posição dos rostos em cada quadro
  - monta folhas de contato (6x5 quadros) com o tempo de cada quadro

Saída em <trabalho>/analise/:
  material.json            informações técnicas de cada vídeo
  indice.csv               uma linha por quadro: tempo, nitidez, brilho, movimento, rostos
  folhas_2s/<video>_NN.jpg folhas de contato para olhar e classificar as cenas

Exemplo:
  py ferramentas\\analisar.py C:\\JC-Reels\\2026-10-cabeleireiro
  py ferramentas\\analisar.py C:\\JC-Reels\\2026-10-cabeleireiro --cada 1
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import EXT_VIDEO, checar_ffmpeg, hms, listar, rodar, sondar  # noqa: E402

COLUNAS, LINHAS, CELULA = 6, 5, 320
LARGURA_QUADRO = 640  # tamanho usado para medir nitidez e achar rostos


def extrair_quadros(video, pasta, cada):
    """Extrai um quadro a cada `cada` segundos. Tenta decodificar no hardware primeiro."""
    pasta.mkdir(parents=True, exist_ok=True)
    saida = pasta / "q_%05d.jpg"
    base = ["-i", video, "-vf", f"fps=1/{cada}:round=down,scale={LARGURA_QUADRO}:-2",
            "-q:v", "4", "-an", "-y", saida]
    for hw in (["-hwaccel", "auto"], []):
        r = rodar(["ffmpeg", "-hide_banner", "-v", "error", *hw, *base])
        if r.returncode == 0:
            break
    else:
        sys.exit(f"ERRO ao extrair quadros de {video}:\n{r.stderr}")
    return sorted(pasta.glob("q_*.jpg"))


def detectores():
    d = cv2.data.haarcascades
    return (cv2.CascadeClassifier(d + "haarcascade_frontalface_default.xml"),
            cv2.CascadeClassifier(d + "haarcascade_profileface.xml"))


def rostos(cinza, frontal, perfil):
    """Posições (x central, largura) de rostos, normalizadas 0-1. Só posição, sem identificar ninguém."""
    h, w = cinza.shape
    minimo = (max(24, w // 25),) * 2
    achados = list(frontal.detectMultiScale(cinza, 1.15, 6, minSize=minimo))
    achados += list(perfil.detectMultiScale(cinza, 1.15, 6, minSize=minimo))
    espelho = cv2.flip(cinza, 1)
    achados += [(w - x - fw, y, fw, fh) for x, y, fw, fh in perfil.detectMultiScale(espelho, 1.15, 6, minSize=minimo)]
    return sorted(((x + fw / 2) / w, fw / w) for x, y, fw, fh in achados)


def medir(quadros, cada):
    frontal, perfil = detectores()
    linhas, anterior = [], None
    for i, q in enumerate(quadros):
        img = cv2.imread(str(q))
        cinza = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        pequeno = cv2.resize(cinza, (160, 90))
        mov = float(np.mean(cv2.absdiff(pequeno, anterior))) if anterior is not None else 0.0
        anterior = pequeno
        rs = rostos(cinza, frontal, perfil)
        maior = max(rs, key=lambda r: r[1]) if rs else None
        linhas.append({
            "quadro": q.name,
            "tempo": round(i * cada, 2),
            "nitidez": round(float(cv2.Laplacian(cinza, cv2.CV_64F).var()), 1),
            "brilho": round(float(np.mean(cinza)), 1),
            "movimento": round(mov, 1),
            "rostos": len(rs),
            "rosto_x": round(maior[0], 3) if maior else "",
        })
    return linhas


def fonte(tamanho):
    for nome in ("arialbd.ttf", "arial.ttf", "DejaVuSans-Bold.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(nome, tamanho)
        except OSError:
            pass
    try:
        return ImageFont.load_default(size=tamanho)
    except TypeError:
        return ImageFont.load_default()


def folhas(quadros, linhas, nome, rotulo, destino):
    destino.mkdir(parents=True, exist_ok=True)
    if not quadros:
        return []
    w0, h0 = Image.open(quadros[0]).size
    cw = CELULA if w0 >= h0 else int(CELULA * 0.6)
    ch = int(cw * h0 / w0)
    f = fonte(max(14, cw // 13))
    por_folha = COLUNAS * LINHAS
    geradas = []
    for n in range(0, len(quadros), por_folha):
        lote = list(zip(quadros, linhas))[n:n + por_folha]
        folha = Image.new("RGB", (COLUNAS * cw, LINHAS * ch), "black")
        d = ImageDraw.Draw(folha)
        for k, (q, info) in enumerate(lote):
            x, y = (k % COLUNAS) * cw, (k // COLUNAS) * ch
            folha.paste(Image.open(q).resize((cw - 2, ch - 2)), (x + 1, y + 1))
            texto = f"{rotulo} {hms(info['tempo'])}"
            caixa = d.textbbox((x + 4, y + 3), texto, font=f)
            d.rectangle((caixa[0] - 3, caixa[1] - 2, caixa[2] + 3, caixa[3] + 2), fill="black")
            d.text((x + 4, y + 3), texto, fill="yellow", font=f)
        arq = destino / f"{nome}_{n // por_folha + 1:02d}.jpg"
        folha.save(arq, quality=85)
        geradas.append(arq)
    return geradas


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trabalho", help="pasta do trabalho (com material/ dentro)")
    p.add_argument("--cada", type=float, default=2, help="segundos entre quadros (padrão 2)")
    a = p.parse_args()

    checar_ffmpeg()
    trab = Path(a.trabalho)
    videos = listar(trab / "material", EXT_VIDEO)
    if not videos:
        sys.exit(f"ERRO: nenhum vídeo em {trab / 'material'}")
    analise = trab / "analise"
    analise.mkdir(exist_ok=True)

    infos, todas = [], []
    for i, v in enumerate(videos, 1):
        info = sondar(v)
        info["rotulo"] = f"V{i}"
        infos.append(info)
        print(f"[{info['rotulo']}] {v.name}: {hms(info['duracao'])} | {info['largura']}x{info['altura']} | "
              f"{info['fps']:g} fps | {info['codec']} {info['pix_fmt']} | {info['bitrate_mbps']} Mbps")
        print("     extraindo quadros (pode levar alguns minutos em 4K)...")
        quadros = extrair_quadros(v, analise / f"quadros_{a.cada:g}s" / v.stem, a.cada)
        print(f"     {len(quadros)} quadros. Medindo nitidez, movimento e rostos...")
        linhas = medir(quadros, a.cada)
        for ln in linhas:
            ln["material"] = v.name
        todas += linhas
        pasta_folhas = analise / f"folhas_{a.cada:g}s"
        fs = folhas(quadros, linhas, v.stem, info["rotulo"], pasta_folhas)
        print(f"     {len(fs)} folhas de contato em {pasta_folhas}")

    (analise / "material.json").write_text(json.dumps(infos, indent=2, ensure_ascii=False), encoding="utf-8")
    campos = ["material", "tempo", "quadro", "nitidez", "brilho", "movimento", "rostos", "rosto_x"]
    with open(analise / "indice.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=campos)
        w.writeheader()
        w.writerows(todas)
    print(f"\nPronto. Índice: {analise / 'indice.csv'}")


if __name__ == "__main__":
    main()
