#!/usr/bin/env python3
"""Passo 2 de cada trabalho: detecta as batidas da música.

Lê o arquivo de áudio em <trabalho>/musica/ e grava <trabalho>/analise/batidas.json com:
  bpm         andamento estimado
  batidas     tempo (s) de cada batida
  fortes      tempo (s) das batidas fortes (o "1" de cada compasso de 4)
  energia     intensidade de cada batida (0-1), para achar o trecho mais forte
  trechos     sugestões de onde começar a música para cada duração (trecho mais energético)

Exemplo:
  py ferramentas\\batidas.py C:\\JC-Reels\\2026-10-cabeleireiro
"""
import argparse
import json
import sys
import tempfile
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import EXT_AUDIO, checar_ffmpeg, hms, listar, rodar  # noqa: E402

TAXA = 22050
DURACOES = (30, 45, 60, 75, 90)


def carregar(musica):
    """Decodifica qualquer formato com o ffmpeg para um WAV mono temporário e lê com o librosa."""
    import librosa
    with tempfile.TemporaryDirectory() as tmp:
        wav = Path(tmp) / "musica.wav"
        r = rodar(["ffmpeg", "-hide_banner", "-v", "error", "-i", musica, "-vn", "-ac", "1",
                   "-ar", str(TAXA), "-y", wav])
        if r.returncode:
            sys.exit(f"ERRO ao ler a música {musica}:\n{r.stderr}")
        y, _ = librosa.load(str(wav), sr=TAXA, mono=True)
    return y


def analisar(y):
    import librosa
    env = librosa.onset.onset_strength(y=y, sr=TAXA)
    bpm, quadros = librosa.beat.beat_track(onset_envelope=env, sr=TAXA, units="frames")
    bpm = float(np.atleast_1d(bpm)[0])
    tempos = librosa.frames_to_time(quadros, sr=TAXA)
    forca = env[np.clip(quadros, 0, len(env) - 1)] if len(quadros) else np.array([])
    # energia sonora (volume) em torno de cada batida, suavizada
    rms = librosa.feature.rms(y=y)[0]
    energia = rms[np.clip(quadros, 0, len(rms) - 1)] if len(quadros) else np.array([])
    if len(energia):
        energia = np.convolve(energia, np.ones(4) / 4, mode="same")
        energia = (energia - energia.min()) / (np.ptp(energia) or 1)
    # o "1" do compasso: das 4 fases possíveis, a que tem batidas mais fortes em média
    fase = int(np.argmax([forca[k::4].mean() if len(forca[k::4]) else 0 for k in range(4)])) if len(forca) else 0
    return bpm, tempos, energia, tempos[fase::4]


def sugerir_trechos(tempos, energia, fortes, duracao_total):
    """Para cada duração de Reels, o início (numa batida forte) do trecho com mais energia."""
    sugestoes = {}
    for d in DURACOES:
        melhor, inicio = -1.0, 0.0
        for t0 in fortes:
            if t0 + d > duracao_total:
                break
            dentro = (tempos >= t0) & (tempos < t0 + d)
            if dentro.any() and energia[dentro].mean() > melhor:
                melhor, inicio = float(energia[dentro].mean()), float(t0)
        if melhor >= 0:
            sugestoes[str(d)] = round(inicio, 3)
    return sugestoes


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trabalho")
    a = p.parse_args()

    checar_ffmpeg()
    trab = Path(a.trabalho)
    musicas = listar(trab / "musica", EXT_AUDIO)
    if not musicas:
        sys.exit(f"ERRO: nenhum arquivo de áudio em {trab / 'musica'}")
    if len(musicas) > 1:
        print(f"Aviso: mais de uma música; usando {musicas[0].name}")
    musica = musicas[0]

    print(f"Analisando {musica.name}...")
    y = carregar(musica)
    duracao = len(y) / TAXA
    bpm, tempos, energia, fortes = analisar(y)
    if len(tempos) < 8:
        sys.exit("ERRO: não consegui achar batidas suficientes nessa música.")

    dados = {
        "musica": musica.name,
        "duracao": round(duracao, 3),
        "bpm": round(bpm, 1),
        "intervalo_batida": round(60 / bpm, 3) if bpm else None,
        "batidas": [round(float(t), 3) for t in tempos],
        "fortes": [round(float(t), 3) for t in fortes],
        "energia": [round(float(e), 3) for e in energia],
        "trechos": sugerir_trechos(tempos, energia, fortes, duracao),
    }
    saida = trab / "analise" / "batidas.json"
    saida.parent.mkdir(exist_ok=True)
    saida.write_text(json.dumps(dados, indent=1, ensure_ascii=False), encoding="utf-8")

    print(f"Duração {hms(duracao)} | {dados['bpm']} BPM | {len(tempos)} batidas "
          f"(uma a cada {dados['intervalo_batida']} s) | {len(fortes)} batidas fortes")
    print("Melhor início da música para cada duração:")
    for d, t in dados["trechos"].items():
        print(f"   {d:>3} s -> começar em {hms(t)}")
    print(f"Salvo em {saida}")


if __name__ == "__main__":
    main()
