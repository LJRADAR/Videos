"""Acabamento dos Reels: cor (LUT), legendas, textos na tela, mixagem e volume.

Usado pelo montar.py. Nada aqui altera material/ ou musica/: tudo é gravado em
analise/ (temporários) ou prontos/ (.srt).
"""
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import rodar  # noqa: E402

RAIZ = Path(__file__).resolve().parent.parent
PASTA_FONTES = RAIZ / "fontes"
PASTA_MODELOS = RAIZ / "modelos"
TAXA = 48000
ALVO_LUFS, ALVO_PICO, ALVO_LRA = -14.0, -1.0, 11.0

# Área segura do Instagram Reels (em 1080x1920): em cima ~250 px de interface,
# embaixo ~420 px (legenda do post, botões), à direita ~140 px (curtir, comentar).
SEGURO_TOPO, SEGURO_BAIXO, SEGURO_DIREITA, SEGURO_ESQUERDA = 250, 420, 140, 70


# ---------------------------------------------------------------- caminhos em filtros do ffmpeg

def caminho_filtro(arquivo, cwd):
    """Caminho para usar dentro de um filtro (lut3d, ass): relativo à pasta onde o ffmpeg roda,
    para fugir do "C:" do Windows, que o ffmpeg confunde com separador de opção."""
    try:
        c = os.path.relpath(arquivo, cwd)
    except ValueError:            # outro disco no Windows: usa o caminho completo, escapado
        c = str(Path(arquivo).resolve())
    c = c.replace("\\", "/").replace(":", "\\:")
    if "'" in c:
        raise RuntimeError(f"o caminho {arquivo} tem apóstrofo; renomeie a pasta ou o arquivo.")
    return f"'{c}'"


# ---------------------------------------------------------------- cor

def material_parece_log(analise, info):
    """Material Log tem pouca saturação e pouco contraste. Mede nas miniaturas do analisar.py."""
    import cv2
    stem = Path(info["arquivo"]).stem
    quadros = sorted(analise.glob(f"quadros_*s/{stem}/q_*.jpg"))
    if not quadros:
        return None
    passo = max(1, len(quadros) // 20)
    sats, contrastes = [], []
    for q in quadros[::passo]:
        img = cv2.imread(str(q))
        if img is None:
            continue
        sats.append(cv2.cvtColor(img, cv2.COLOR_BGR2HSV)[:, :, 1].mean())
        contrastes.append(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY).std())
    if not sats:
        return None
    sat, con = float(np.median(sats)), float(np.median(contrastes))
    return sat < 55 and con < 48, sat, con


# ---------------------------------------------------------------- estilo das letras

def fonte_padrao():
    """Montserrat ExtraBold se estiver em fontes\\; senão Arial Black (vem no Windows)."""
    if any(PASTA_FONTES.glob("Montserrat-ExtraBold*.ttf")):
        return "Montserrat ExtraBold"
    return "Arial Black"


def cor_ass(cor, alfa=0):
    """'#RRGGBB' ou nome simples -> &HAABBGGRR do ASS."""
    nomes = {"branco": "#FFFFFF", "preto": "#000000", "amarelo": "#FFE500", "vermelho": "#FF3B30",
             "verde": "#34C759", "azul": "#0A84FF", "rosa": "#FF2D78", "laranja": "#FF9500",
             "dourado": "#E8B54A"}
    c = nomes.get(str(cor).lower(), str(cor)).lstrip("#")
    if not re.fullmatch(r"[0-9A-Fa-f]{6}", c):
        c = "FFFFFF"
    r, g, b = c[0:2], c[2:4], c[4:6]
    return f"&H{alfa:02X}{b}{g}{r}".upper()


# estilos prontos para textos na tela: (tamanho, cor, contorno, caixa, posição y padrão)
ESTILOS_TEXTO = {
    "gancho":  {"tamanho": 96, "cor": "branco", "contorno": 8, "caixa": False, "y": 0.22},
    "nome":    {"tamanho": 60, "cor": "branco", "contorno": 0, "caixa": True, "y": 0.75},
    "chamada": {"tamanho": 88, "cor": "amarelo", "contorno": 8, "caixa": False, "y": 0.45},
    "simples": {"tamanho": 72, "cor": "branco", "contorno": 6, "caixa": False, "y": 0.45},
}
POSICOES = {"topo": 0.22, "centro": 0.45, "baixo": 0.68}


def cabecalho_ass(largura, altura, fonte, estilo_leg):
    tam = int(estilo_leg.get("tamanho", 84))
    cor = cor_ass(estilo_leg.get("cor", "branco"))
    margem_v = SEGURO_BAIXO + int(altura * 0.10)   # um pouco acima da área da legenda do post
    linhas = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {largura}", f"PlayResY: {altura}",
        "ScaledBorderAndShadow: yes", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Legenda,{fonte},{tam},{cor},{cor},&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,7,3,2,"
        f"{SEGURO_ESQUERDA + 30},{SEGURO_DIREITA + 30},{margem_v},1",
        f"Style: Texto,{fonte},72,&H00FFFFFF,&H00FFFFFF,&H00000000,&H90000000,0,0,0,0,100,100,0,0,1,6,3,5,"
        f"{SEGURO_ESQUERDA},{SEGURO_DIREITA},0,1",
        f"Style: Caixa,{fonte},64,&H00FFFFFF,&H00FFFFFF,&H00000000,&H50000000,0,0,0,0,100,100,0,0,3,14,0,5,"
        f"{SEGURO_ESQUERDA},{SEGURO_DIREITA},0,1",
        "", "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    return "\n".join(linhas) + "\n"


def tempo_ass(t):
    t = max(0.0, t)
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def limpar_texto(t):
    return str(t).replace("{", "(").replace("}", ")").replace("\r", "").replace("\n", "\\N")


# ---------------------------------------------------------------- eventos (legendas + textos)
# Cada evento: {"ini", "fim", "estilo", "texto", "entrada", "saida", "anim", "camada"}
# "entrada"/"saida" = ms de fade; "anim" = tags de animação que só valem no começo real do evento.

def eventos_textos(textos, duracao, largura, altura, fonte):
    eventos, avisos = [], []
    for i, t in enumerate(textos or [], 1):
        est = ESTILOS_TEXTO.get(t.get("estilo", "simples"), ESTILOS_TEXTO["simples"])
        ini = float(t.get("inicio", 0))
        dur = float(t.get("duracao", 2.5))
        if ini >= duracao:
            avisos.append(f"texto {i} ('{t.get('texto', '')}') começa depois do fim do Reels; ignorado.")
            continue
        fim = min(ini + dur, duracao)
        pos = t.get("posicao", est["y"])
        y = POSICOES.get(pos, pos) if isinstance(pos, str) else pos
        try:
            y = float(y)
        except (TypeError, ValueError):
            y = est["y"]
        y = min(max(y, SEGURO_TOPO / 1920 + 0.03), 1 - SEGURO_BAIXO / 1920 - 0.03)
        x = (SEGURO_ESQUERDA + (largura - SEGURO_DIREITA)) / 2
        tam = int(t.get("tamanho", est["tamanho"]))
        cor = cor_ass(t.get("cor", est["cor"]))
        tags = f"\\an5\\pos({x:.0f},{y * altura:.0f})\\fs{tam}\\c{cor}"
        if t.get("fonte"):
            tags += f"\\fn{t['fonte']}"
        if not est["caixa"]:
            tags += f"\\bord{est['contorno']}"
        anim = ""
        if t.get("estilo") in ("gancho", "chamada"):
            anim = "\\fscx70\\fscy70\\t(0,180,\\fscx100\\fscy100)"   # "pop" de entrada
        eventos.append({"ini": ini, "fim": fim, "estilo": "Caixa" if est["caixa"] else "Texto",
                        "texto": "{" + tags + "}" + limpar_texto(t.get("texto", "")),
                        "entrada": 200, "saida": 200, "anim": anim, "camada": 2})
    return eventos, avisos


def juntar_pedacos(palavras):
    """O transcritor às vezes parte palavras ("bem" + "-vindos"): junta de volta."""
    saida = []
    for p in palavras:
        if saida and (p["texto"][:1] in "-'.,!?;:" or saida[-1]["texto"].endswith("-")):
            ant = dict(saida[-1])
            ant["texto"] += p["texto"]
            ant["fim"] = p["fim"]
            saida[-1] = ant
        else:
            saida.append(dict(p))
    return saida


def agrupar_palavras(palavras, max_palavras=4, max_dur=1.6):
    """Junta palavras em blocos de 2 a 4, quebrando em pausas e pontuação."""
    blocos, atual = [], []
    for p in juntar_pedacos(palavras):
        if atual:
            dur = p["fim"] - atual[0]["ini"]
            pausa = p["ini"] - atual[-1]["fim"]
            fim_frase = atual[-1]["texto"][-1:] in ".!?"
            virgula = atual[-1]["texto"][-1:] in ",;:"
            if (len(atual) >= max_palavras or dur > max_dur or pausa > 0.6 or fim_frase
                    or (len(atual) >= 2 and (virgula or pausa > 0.35))):
                blocos.append(atual)
                atual = []
        atual.append(p)
    if atual:
        blocos.append(atual)
    return blocos


def eventos_legendas(blocos, estilo_leg, duracao):
    """Um evento por palavra falada: o bloco inteiro aparece e a palavra da vez fica destacada."""
    destaque = estilo_leg.get("destaque", "amarelo")
    cor_dest = cor_ass(destaque) if destaque else None
    cor_base = cor_ass(estilo_leg.get("cor", "branco"))
    maiusc = bool(estilo_leg.get("maiusculas", False))
    eventos = []
    for b, bloco in enumerate(blocos):
        ini = bloco[0]["ini"]
        fim = bloco[-1]["fim"]
        prox = blocos[b + 1][0]["ini"] if b + 1 < len(blocos) else duracao
        fim = min(prox, max(fim + 0.25, ini + 0.5)) if prox - fim < 0.5 else fim + 0.25
        fim = min(fim, duracao)
        textos = [limpar_texto(p["texto"].upper() if maiusc else p["texto"]) for p in bloco]
        if not cor_dest or "palavras" not in bloco[0]:
            # sem tempo por palavra (ex.: .srt editado): mostra o bloco inteiro
            eventos.append({"ini": ini, "fim": fim, "estilo": "Legenda", "texto": " ".join(textos),
                            "entrada": 0, "saida": 0, "anim": "", "camada": 1})
            continue
        for k, p in enumerate(bloco):
            e_ini = ini if k == 0 else p["ini"]
            e_fim = bloco[k + 1]["ini"] if k + 1 < len(bloco) else fim
            if e_fim <= e_ini:
                continue
            partes = [f"{{\\c{cor_dest}}}{w}{{\\c{cor_base}}}" if j == k else w for j, w in enumerate(textos)]
            eventos.append({"ini": e_ini, "fim": e_fim, "estilo": "Legenda", "texto": " ".join(partes),
                            "entrada": 0, "saida": 0, "anim": "", "camada": 1})
    return eventos


def ass_da_cena(cabecalho, eventos, t0, t1):
    """Recorta os eventos para uma cena [t0, t1) com o tempo zerado no início da cena.
    Fade e animação só no pedaço que contém o começo/fim real do evento: o texto que
    atravessa um corte continua igual do outro lado."""
    linhas = []
    for ev in eventos:
        if ev["fim"] <= t0 + 0.005 or ev["ini"] >= t1 - 0.005:
            continue
        comeca, termina = ev["ini"] >= t0 - 0.005, ev["fim"] <= t1 + 0.005
        a, b = max(ev["ini"], t0) - t0, min(ev["fim"], t1) - t0
        tags = ""
        fi, fo = (ev["entrada"] if comeca else 0), (ev["saida"] if termina else 0)
        if fi or fo:
            tags += f"\\fad({fi},{fo})"
        if comeca and ev["anim"]:
            tags += ev["anim"]
        texto = ("{" + tags + "}" if tags else "") + ev["texto"]
        linhas.append(f"Dialogue: {ev['camada']},{tempo_ass(a)},{tempo_ass(b)},{ev['estilo']},,0,0,0,,{texto}")
    if not linhas:
        return None
    return cabecalho + "\n".join(linhas) + "\n"


# ---------------------------------------------------------------- .srt

def tempo_srt(t):
    ms = int(round(max(0.0, t) * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def gravar_srt(blocos, destino):
    partes = []
    for i, b in enumerate(blocos, 1):
        partes.append(f"{i}\n{tempo_srt(b[0]['ini'])} --> {tempo_srt(b[-1]['fim'])}\n"
                      + " ".join(p["texto"] for p in b) + "\n")
    destino.write_text("\n".join(partes), encoding="utf-8")


def ler_srt(arquivo):
    """Lê um .srt (talvez editado à mão) e devolve blocos sem tempo por palavra."""
    txt = arquivo.read_text(encoding="utf-8-sig")
    blocos = []
    for m in re.finditer(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)\s*\n(.*?)(?:\n\s*\n|\Z)",
                         txt, re.S):
        g = [int(x) for x in m.groups()[:8]]
        ini = g[0] * 3600 + g[1] * 60 + g[2] + g[3] / 1000
        fim = g[4] * 3600 + g[5] * 60 + g[6] + g[7] / 1000
        texto = " ".join(m.group(9).split())
        if texto:
            blocos.append([{"ini": ini, "fim": fim, "texto": texto}])
    return blocos


# ---------------------------------------------------------------- som original das cenas

def atempo(vel):
    """atempo aceita 0.5–2.0 por filtro; encadeia para valores fora disso."""
    partes = []
    while vel < 0.5:
        partes.append("atempo=0.5")
        vel /= 0.5
    while vel > 2.0:
        partes.append("atempo=2.0")
        vel /= 2.0
    if abs(vel - 1.0) > 1e-6:
        partes.append(f"atempo={vel:.6f}")
    return partes


def extrair_som_cena(info, cena, dur):
    """Som da câmera no trecho da cena, já na velocidade da cena, com duração exata."""
    n = int(round(dur * TAXA))
    if info.get("tem_audio"):
        af = ",".join(atempo(cena["velocidade"]) + ["aresample=48000"])
        p = subprocess.run(["ffmpeg", "-hide_banner", "-v", "error", "-ss", f"{cena['inicio']:.3f}",
                            "-t", f"{dur * cena['velocidade'] + 0.2:.3f}", "-i", str(info["arquivo"]),
                            "-vn", "-ac", "1", "-af", af, "-f", "f32le", "-"], capture_output=True)
        dados = np.frombuffer(p.stdout, dtype=np.float32) if p.returncode == 0 else np.zeros(0, np.float32)
    else:
        dados = np.zeros(0, np.float32)
    out = np.zeros(n, np.float32)
    out[:min(n, len(dados))] = dados[:n]
    return out


def gravar_wav(amostras, destino):
    import soundfile as sf
    sf.write(str(destino), amostras, TAXA, subtype="FLOAT")


def chave_cenas(reel, marcas, fps):
    base = [(c["material"], round(c["inicio"], 3), round(c["velocidade"], 4), marcas[i], marcas[i + 1])
            for i, c in enumerate(reel["cenas"])]
    return hashlib.sha1(json.dumps([base, fps]).encode()).hexdigest()[:12]


# ---------------------------------------------------------------- transcrição

def motor_transcricao():
    """faster-whisper (tempo por palavra) é o padrão; o filtro whisper do ffmpeg é a alternativa."""
    try:
        import faster_whisper  # noqa: F401
        return "faster-whisper"
    except ImportError:
        pass
    r = rodar(["ffmpeg", "-hide_banner", "-filters"])
    if re.search(r"\swhisper\s", r.stdout):
        return "ffmpeg-whisper"
    return None


def transcrever(wav, cache):
    """Roda o transcrever.py num processo separado (libera a memória ao terminar)."""
    if cache.exists():
        return json.loads(cache.read_text(encoding="utf-8"))
    script = Path(__file__).resolve().parent / "transcrever.py"
    p = subprocess.run([sys.executable, str(script), str(wav), str(cache)])
    if p.returncode or not cache.exists():
        raise RuntimeError("a transcrição falhou (veja a mensagem acima).")
    return json.loads(cache.read_text(encoding="utf-8"))


# ---------------------------------------------------------------- mixagem e volume

def mixar(musica, ini_mus, total, voz_wav, destino, fade_audio):
    """Música (abaixando sozinha quando há fala) + som original -> WAV, com fades."""
    fades = f"afade=t=in:d=0.03,afade=t=out:st={max(0, total - fade_audio):.3f}:d={fade_audio}"
    if voz_wav is None:
        fc = f"[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,{fades}[out]"
        entradas = ["-ss", f"{ini_mus:.3f}", "-t", f"{total:.3f}", "-i", musica]
    else:
        fc = ("[1:a]highpass=f=80,dynaudnorm=f=200:g=11:p=0.9:m=8,aformat=sample_fmts=fltp:channel_layouts=stereo,"
              "asplit=2[voz][chave];"
              "[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo[mus];"
              "[mus][chave]sidechaincompress=threshold=0.035:ratio=4:attack=30:release=450:knee=4[musd];"
              f"[musd][voz]amix=inputs=2:normalize=0:duration=first,{fades}[out]")
        entradas = ["-ss", f"{ini_mus:.3f}", "-t", f"{total:.3f}", "-i", musica, "-i", voz_wav]
    r = rodar(["ffmpeg", "-hide_banner", "-v", "error", "-y", *entradas, "-filter_complex", fc,
               "-map", "[out]", "-t", f"{total:.3f}", "-c:a", "pcm_f32le", destino])
    if r.returncode:
        raise RuntimeError(f"falha na mixagem do áudio:\n{r.stderr[-1200:]}")


def medir_volume(wav):
    """1ª passada do loudnorm: mede o volume do áudio mixado."""
    r = rodar(["ffmpeg", "-hide_banner", "-i", wav, "-af",
               f"loudnorm=I={ALVO_LUFS}:TP={ALVO_PICO}:LRA={ALVO_LRA}:print_format=json", "-f", "null", "-"])
    m = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", r.stderr, re.S)
    if not m:
        raise RuntimeError(f"não consegui medir o volume:\n{r.stderr[-800:]}")
    return json.loads(m.group(0))


def filtro_volume(medido):
    """2ª passada do loudnorm: corrige para -14 LUFS / -1 dBTP usando a medição."""
    return (f"loudnorm=I={ALVO_LUFS}:TP={ALVO_PICO}:LRA={ALVO_LRA}"
            f":measured_I={medido['input_i']}:measured_TP={medido['input_tp']}"
            f":measured_LRA={medido['input_lra']}:measured_thresh={medido['input_thresh']}"
            f":offset={medido['target_offset']}:linear=true,aresample=48000")
