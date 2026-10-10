#!/usr/bin/env python3
"""Passo 4 de cada trabalho: monta e exporta os Reels a partir do plano.json.

Lê <trabalho>/plano.json (as cenas escolhidas para cada Reels), encaixa os cortes nas
batidas da música (analise/batidas.json), reenquadra para 9:16 a partir do arquivo
ORIGINAL e grava em <trabalho>/prontos/:
  NN-nome.mp4      o Reels pronto (H.264 alta qualidade, só a música, fade no fim)
  relatorio.txt    trechos usados de cada vídeo (tempo no material) e duração

Exemplos:
  py ferramentas\\montar.py C:\\JC-Reels\\2026-10-cabeleireiro
  py ferramentas\\montar.py C:\\JC-Reels\\2026-10-cabeleireiro --previa      (rápido, baixa resolução)
  py ferramentas\\montar.py C:\\JC-Reels\\2026-10-cabeleireiro --so 02-penteado
  py ferramentas\\montar.py C:\\JC-Reels\\2026-10-cabeleireiro --conferir    (só confere o plano)

Formato do plano.json (o CLAUDE.md explica cada campo):
{
  "resolucao": "1080x1920",
  "batidas_por_corte": 2,
  "reels": [
    {"nome": "01-maquiagem", "duracao": 45, "musica_inicio": 12.3,
     "cenas": [
        {"material": "C0001.MP4", "inicio": 83.0, "batidas": 4, "foco_x": "auto", "nota": "close do olho"},
        {"material": "C0001.MP4", "inicio": 140.5, "batidas": 2, "velocidade": 0.5}
     ]}
  ]
}
"""
import argparse
import csv
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from comum import (EXT_AUDIO, args_codificador, checar_ffmpeg, codificador,  # noqa: E402
                   hms, listar, rodar, sondar)

FADE_AUDIO = 1.5   # segundos de fade da música no fim
FADE_VIDEO = 0.5   # segundos de fade para o preto no fim
MIN_CENA = 0.4     # nenhuma cena menor que isso na tela


class ErroPlano(Exception):
    pass


# ---------------------------------------------------------------- leitura

def ler_json(caminho, o_que):
    if not caminho.exists():
        sys.exit(f"ERRO: falta {caminho} ({o_que}).")
    try:
        return json.loads(caminho.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as e:
        sys.exit(f"ERRO: {caminho} está com erro de formato na linha {e.lineno}: {e.msg}")


def ler_indice(trab):
    """Posição dos rostos por quadro (do analisar.py), para o reenquadramento automático."""
    arq = trab / "analise" / "indice.csv"
    rostos = {}
    if arq.exists():
        with open(arq, encoding="utf-8") as f:
            for ln in csv.DictReader(f):
                if ln.get("rosto_x"):
                    rostos.setdefault(ln["material"], []).append((float(ln["tempo"]), float(ln["rosto_x"])))
    return rostos


def foco_auto(rostos, material, ini, fim):
    """Centro horizontal da pessoa principal no trecho (mediana dos rostos encontrados)."""
    pontos = rostos.get(material, [])
    for folga in (0, 2, 4):
        xs = [x for t, x in pontos if ini - folga <= t <= fim + folga]
        if xs:
            return statistics.median(xs), "auto"
    return 0.5, "centro (nenhum rosto achado)"


def fps_saida(fps_material, pedido):
    if pedido:
        return float(pedido)
    f = fps_material
    if f > 31:          # 50/60 fps -> 25/30
        f /= 2
    return round(f, 3)


# ---------------------------------------------------------------- planejamento

def planejar(plano, batidas, materiais, rostos):
    """Transforma o plano em cortes exatos (tempo no material e na tela). Não grava nada."""
    padrao = int(plano.get("batidas_por_corte", 2))
    todas = batidas["batidas"]
    resultado, usados = [], []
    for r in plano["reels"]:
        nome = r["nome"]
        alvo = float(r["duracao"])
        ini_mus = r.get("musica_inicio")
        if ini_mus is None:
            ini_mus = batidas.get("trechos", {}).get(str(int(alvo)), 0.0)
        ini_mus = min(todas, key=lambda b: abs(b - float(ini_mus)))  # começa exatamente numa batida
        cortes = [round(b - ini_mus, 3) for b in todas if b >= ini_mus - 0.001]
        if batidas["duracao"] - ini_mus < alvo:
            raise ErroPlano(f"[{nome}] a música só tem {hms(batidas['duracao'] - ini_mus)} a partir de "
                            f"{hms(ini_mus)}, menos que os {alvo:g} s pedidos. Comece a música mais cedo.")
        # depois da última batida, a música ainda segue: deixa cortar até o fim dela
        cortes.append(round(batidas["duracao"] - ini_mus, 3))
        fim_alvo = min(cortes, key=lambda c: abs(c - alvo))  # termina numa batida perto da duração pedida

        cenas, k = [], 0
        for i, c in enumerate(r["cenas"]):
            if cortes[k] >= fim_alvo - 0.001:
                print(f"   aviso [{nome}]: cena {i + 1} em diante não coube na duração; ignorada.")
                break
            n = int(c.get("batidas", padrao))
            k2 = min(k + n, len(cortes) - 1)
            if cortes[k2] > fim_alvo:
                k2 = cortes.index(fim_alvo)
            t0, t1 = cortes[k], cortes[k2]
            if t1 - t0 < MIN_CENA:
                raise ErroPlano(f"[{nome}] cena {i + 1}: só {t1 - t0:.2f} s na tela; use mais batidas.")
            mat = c["material"]
            if mat not in materiais:
                raise ErroPlano(f"[{nome}] cena {i + 1}: material '{mat}' não está em material/.")
            info = materiais[mat]
            vel = float(c.get("velocidade", 1.0))
            ini = float(c["inicio"])
            fim = ini + (t1 - t0) * vel
            if ini < 0 or fim > info["duracao"] - 0.05:
                raise ErroPlano(f"[{nome}] cena {i + 1}: {hms(ini)}–{hms(fim)} passa do fim de "
                                f"{mat} ({hms(info['duracao'])}).")
            fx = c.get("foco_x", "auto")
            if fx == "auto":
                fx, origem_foco = foco_auto(rostos, mat, ini, fim)
            else:
                fx, origem_foco = float(fx), "manual"
            cenas.append({"n": i + 1, "material": mat, "inicio": ini, "fim": fim, "tela_ini": t0,
                          "tela_fim": t1, "velocidade": vel, "foco_x": fx, "foco": origem_foco,
                          "foco_y": float(c.get("foco_y", 0.5)), "zoom": float(c.get("zoom", 1.0)),
                          "nota": c.get("nota", "")})
            usados.append((mat, ini, fim, nome, i + 1))
            k = k2
        total = cortes[k]
        if total < fim_alvo - 0.001:
            raise ErroPlano(f"[{nome}] as cenas só preenchem {total:.1f} s de {alvo:g} s. "
                            f"Faltam cerca de {fim_alvo - total:.1f} s: acrescente cenas ou batidas.")
        resultado.append({"nome": nome, "musica_inicio": ini_mus, "duracao": total, "cenas": cenas})

    if not plano.get("permitir_repeticao", False):
        usados.sort()
        for a, b in zip(usados, usados[1:]):
            if a[0] == b[0] and b[1] < a[2] - 0.2 and a[3] != b[3]:
                raise ErroPlano(f"Trecho repetido entre Reels: {a[0]} {hms(b[1])}–{hms(a[2])} aparece em "
                                f"[{a[3]}] cena {a[4]} e [{b[3]}] cena {b[4]}.")
    return resultado


# ---------------------------------------------------------------- exportação

def filtro(info, cena, largura, altura, fps, ultimo, dur):
    W, H = info["largura"], info["altura"]
    z = max(1.0, cena["zoom"])
    alvo = largura / altura
    if W / H > alvo:                      # material mais largo (16:9): corta as laterais
        ch = H / z
        cw = ch * alvo
    else:                                 # material já em pé: corta em cima/embaixo
        cw = W / z
        ch = cw / alvo
    cw, ch = int(cw) // 2 * 2, int(ch) // 2 * 2
    x = int(min(max(cena["foco_x"] * W - cw / 2, 0), W - cw))
    y = int(min(max(cena["foco_y"] * H - ch / 2, 0), H - ch))
    f = []
    if cena["velocidade"] != 1.0:
        f.append(f"setpts=PTS/{cena['velocidade']}")
    f += [f"fps={fps}", f"crop={cw}:{ch}:{x}:{y}", f"scale={largura}:{altura}:flags=lanczos", "setsar=1"]
    if ultimo:
        f.append(f"fade=t=out:st={max(0, dur - FADE_VIDEO):.3f}:d={FADE_VIDEO}")
    return ",".join(f)


def exportar_cena(info, cena, destino, largura, altura, fps, quadros, ultimo, enc, previa):
    dur = quadros / fps
    vf = filtro(info, cena, largura, altura, fps, ultimo, dur)
    if previa:
        codecs = [["-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p"]]
    else:
        codecs = [args_codificador(enc)]
        if enc != "libx264":
            codecs.append(args_codificador("libx264"))  # se o hardware falhar, usa o processador
    ultimo_erro = ""
    for cod in codecs:
        for hw in (["-hwaccel", "auto"], []):
            cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-y", *hw, "-ss", f"{cena['inicio']:.3f}",
                   "-i", info["arquivo"], "-vf", vf, "-frames:v", str(quadros), "-an", *cod,
                   "-r", str(fps), "-video_track_timescale", "90000", destino]
            r = rodar(cmd)
            if r.returncode == 0:
                return cod[1]
            ultimo_erro = r.stderr
    raise RuntimeError(f"falha ao exportar a cena {cena['n']}:\n{ultimo_erro[-1500:]}")


def exportar_reels(reel, materiais, musica, prontos, tmp, largura, altura, fps, enc, previa):
    pasta = tmp / reel["nome"]
    pasta.mkdir(parents=True, exist_ok=True)
    # cortes em número de quadros, calculados sobre o tempo total para não acumular erro
    marcas = [round(c["tela_ini"] * fps) for c in reel["cenas"]] + [round(reel["duracao"] * fps)]
    lista, usados = [], set()
    for i, cena in enumerate(reel["cenas"]):
        q = marcas[i + 1] - marcas[i]
        arq = pasta / f"cena_{i + 1:02d}.mp4"
        print(f"      cena {i + 1}/{len(reel['cenas'])}: {cena['material']} {hms(cena['inicio'])} "
              f"({q / fps:.2f} s)", flush=True)
        usados.add(exportar_cena(materiais[cena["material"]], cena, arq, largura, altura, fps, q,
                                 i == len(reel["cenas"]) - 1, enc, previa))
        lista.append(f"file '{arq.name}'")
    (pasta / "lista.txt").write_text("\n".join(lista) + "\n", encoding="utf-8")

    total = marcas[-1] / fps
    saida = prontos / f"{reel['nome']}.mp4"
    af = f"afade=t=in:d=0.03,afade=t=out:st={max(0, total - FADE_AUDIO):.3f}:d={FADE_AUDIO}"
    r = rodar(["ffmpeg", "-hide_banner", "-v", "error", "-y",
               "-f", "concat", "-safe", "0", "-i", pasta / "lista.txt",
               "-ss", f"{reel['musica_inicio']:.3f}", "-i", musica,
               "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-af", af,
               "-c:a", "aac", "-b:a", "320k", "-ar", "48000", "-t", f"{total:.3f}",
               "-movflags", "+faststart", saida])
    if r.returncode:
        raise RuntimeError(f"falha ao juntar o Reels {reel['nome']}:\n{r.stderr[-1500:]}")
    return saida, ", ".join(sorted(usados))


# ---------------------------------------------------------------- relatório

def relatorio(planejados, resolucao, fps):
    linhas = [f"RELATÓRIO DOS REELS — {time.strftime('%d/%m/%Y %H:%M')}",
              f"Formato: {resolucao}, {fps:g} fps, H.264 + música (AAC 320k)", ""]
    for r in planejados:
        linhas.append(f"{r['nome']}.mp4 — duração {hms(r['duracao'])} — música a partir de {hms(r['musica_inicio'])}")
        for c in r["cenas"]:
            extra = f", câmera lenta {1 / c['velocidade']:g}x" if c["velocidade"] != 1 else ""
            extra += f", zoom {c['zoom']:g}x" if c["zoom"] != 1 else ""
            nota = f" — {c['nota']}" if c["nota"] else ""
            linhas.append(f"   {c['n']:2d}. {c['material']} {hms(c['inicio'])} → {hms(c['fim'])} "
                          f"| na tela {hms(c['tela_ini'])}–{hms(c['tela_fim'])} "
                          f"({c['tela_fim'] - c['tela_ini']:.2f} s{extra}) | enquadramento {c['foco']}{nota}")
        linhas.append("")
    return "\n".join(linhas)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("trabalho")
    p.add_argument("--previa", action="store_true", help="exporta rápido em 540x960 (para conferir)")
    p.add_argument("--so", help="exporta só o Reels com esse nome (ex.: 02-penteado)")
    p.add_argument("--conferir", action="store_true", help="só confere o plano e mostra o relatório")
    a = p.parse_args()

    checar_ffmpeg()
    trab = Path(a.trabalho)
    plano = ler_json(trab / "plano.json", "o plano com as cenas de cada Reels")
    batidas = ler_json(trab / "analise" / "batidas.json", "rode antes o batidas.py")
    musicas = listar(trab / "musica", EXT_AUDIO)
    if not musicas:
        sys.exit(f"ERRO: nenhum arquivo de áudio em {trab / 'musica'}")
    musica = next((m for m in musicas if m.name == batidas.get("musica")), musicas[0])

    nomes = {c["material"] for r in plano["reels"] for c in r["cenas"]}
    materiais = {}
    for n in sorted(nomes):
        arq = trab / "material" / n
        if not arq.exists():
            sys.exit(f"ERRO: o plano usa '{n}', mas ele não está em {trab / 'material'}")
        materiais[n] = sondar(arq)

    resolucao = plano.get("resolucao", "1080x1920")
    largura, altura = (int(v) for v in resolucao.lower().split("x"))
    primeiro = materiais[plano["reels"][0]["cenas"][0]["material"]]
    fps = fps_saida(primeiro["fps"], plano.get("fps"))

    try:
        planejados = planejar(plano, batidas, materiais, ler_indice(trab))
    except ErroPlano as e:
        sys.exit(f"ERRO NO PLANO: {e}")
    texto = relatorio(planejados, resolucao, fps)
    if a.conferir:
        print(texto)
        return

    if a.previa:
        largura, altura = 540, 960
        prontos = trab / "prontos" / "previa"
        enc = "libx264 (prévia)"
    else:
        prontos = trab / "prontos"
        enc = codificador()
    prontos.mkdir(parents=True, exist_ok=True)
    tmp = trab / "analise" / ("tmp_previa" if a.previa else "tmp")
    alvo = [r for r in planejados if not a.so or r["nome"] == a.so]
    if not alvo:
        sys.exit(f"ERRO: nenhum Reels chamado '{a.so}' no plano.")

    print(f"Exportando {len(alvo)} Reels em {largura}x{altura}, {fps:g} fps, codificador: {enc}")
    for r in alvo:
        t = time.time()
        print(f"\n>> {r['nome']} ({hms(r['duracao'])}, {len(r['cenas'])} cenas)")
        try:
            saida, usado = exportar_reels(r, materiais, musica, prontos, tmp, largura, altura, fps,
                                          enc, a.previa)
        except RuntimeError as e:
            sys.exit(f"ERRO: {e}")
        print(f"   pronto: {saida}  [{usado}, {time.time() - t:.0f} s]")

    (prontos / "relatorio.txt").write_text(texto, encoding="utf-8")
    print(f"\nRelatório: {prontos / 'relatorio.txt'}")


if __name__ == "__main__":
    main()
