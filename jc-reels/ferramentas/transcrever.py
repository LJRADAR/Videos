#!/usr/bin/env python3
"""Transcreve em português o som das cenas de um Reels (chamado pelo montar.py).

Roda num processo separado para devolver a memória ao terminar (o notebook tem 4 GB).
Tudo acontece no notebook: o áudio nunca sai dele. Na primeira vez, baixa o modelo de
transcrição para C:\\JC-Reels\\modelos (só o modelo é baixado).

Motor padrão: faster-whisper (modelo small, int8, no processador), que dá o tempo de cada
palavra. Alternativa: o filtro whisper do ffmpeg (dá só o tempo de cada frase; o tempo das
palavras é estimado).

Uso: py ferramentas\\transcrever.py som.wav saida.json
"""
import json
import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from acabamento import PASTA_MODELOS, motor_transcricao  # noqa: E402
from comum import rodar  # noqa: E402

MODELO_GGML = "https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin"


def com_faster_whisper(wav):
    from faster_whisper import WhisperModel
    print("   transcrevendo com faster-whisper (modelo small, int8)...", flush=True)
    modelo = WhisperModel("small", device="cpu", compute_type="int8",
                          cpu_threads=os.cpu_count() or 4, download_root=str(PASTA_MODELOS))
    # o ffmpeg converte o som para 16 kHz mono (não depende da biblioteca "av", que muda muito)
    import subprocess
    import numpy as np
    p = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-i", str(wav), "-ac", "1", "-ar", "16000",
                        "-f", "f32le", "-"], capture_output=True)
    if p.returncode:
        raise RuntimeError(p.stderr.decode(errors="replace")[-800:])
    audio = np.frombuffer(p.stdout, dtype=np.float32)
    segmentos, _ = modelo.transcribe(audio, language="pt", word_timestamps=True, beam_size=3,
                                     vad_filter=True, vad_parameters={"min_silence_duration_ms": 400},
                                     condition_on_previous_text=False)
    palavras = []
    for s in segmentos:
        for w in s.words or []:
            texto = w.word.strip()
            if texto and w.probability > 0.15:
                palavras.append({"ini": round(w.start, 3), "fim": round(w.end, 3), "texto": texto,
                                 "palavras": True})
    return palavras


def com_filtro_ffmpeg(wav):
    modelo = PASTA_MODELOS / "ggml-small.bin"
    if not modelo.exists():
        import urllib.request
        print("   baixando o modelo do filtro whisper (uma vez, ~470 MB)...", flush=True)
        urllib.request.urlretrieve(MODELO_GGML, modelo)
    srt = Path(wav).with_suffix(".srt")
    print("   transcrevendo com o filtro whisper do ffmpeg...", flush=True)
    cwd = Path(wav).parent
    rel_modelo = os.path.relpath(modelo, cwd).replace("\\", "/")
    r = rodar(["ffmpeg", "-hide_banner", "-v", "error", "-y", "-i", Path(wav).name, "-af",
               f"whisper=model='{rel_modelo}':language=pt:queue=10:destination='{srt.name}':format=srt",
               "-f", "null", "-"], cwd=cwd)
    if r.returncode or not srt.exists():
        raise RuntimeError(r.stderr[-800:])
    palavras = []
    for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)\s*\n(.*?)(?:\n\s*\n|\Z)",
                         srt.read_text(encoding="utf-8", errors="replace"), re.S):
        g = [int(x) for x in m.groups()[:8]]
        ini = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        fim = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        ws = m.group(9).split()
        if not ws:
            continue
        # sem tempo por palavra: distribui a frase pelo número de letras de cada palavra
        total = sum(len(w) + 1 for w in ws)
        t = ini
        for w in ws:
            d = (fim - ini) * (len(w) + 1) / total
            palavras.append({"ini": round(t, 3), "fim": round(t + d, 3), "texto": w, "palavras": True})
            t += d
    return palavras


def main():
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    wav, saida = Path(sys.argv[1]), Path(sys.argv[2])
    PASTA_MODELOS.mkdir(parents=True, exist_ok=True)
    motor = motor_transcricao()
    if motor is None:
        sys.exit("ERRO: nenhum transcritor disponível. Instale com:  py -m pip install faster-whisper")
    t = time.time()
    palavras = com_faster_whisper(wav) if motor == "faster-whisper" else com_filtro_ffmpeg(wav)
    saida.parent.mkdir(parents=True, exist_ok=True)
    saida.write_text(json.dumps({"motor": motor, "palavras": palavras}, ensure_ascii=False, indent=1),
                     encoding="utf-8")
    print(f"   {len(palavras)} palavras em {time.time() - t:.0f} s", flush=True)


if __name__ == "__main__":
    main()
