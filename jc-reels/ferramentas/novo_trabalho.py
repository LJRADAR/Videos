#!/usr/bin/env python3
"""Cria a pasta de um trabalho novo dentro de C:\\JC-Reels (ou da pasta indicada).

Exemplo:
  py ferramentas\\novo_trabalho.py 2026-10-cabeleireiro
Cria:
  2026-10-cabeleireiro\\material\\   coloque aqui o vídeo da decupagem (pode ser mais de um)
  2026-10-cabeleireiro\\musica\\     coloque aqui a música (áudio ou vídeo; só o som é usado)
  2026-10-cabeleireiro\\prontos\\    os Reels prontos aparecem aqui
  2026-10-cabeleireiro\\pedido.txt   preencha com o que você quer
"""
import argparse
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent

MODELO = """PEDIDO DE REELS
===============
(Preencha as linhas abaixo. Pode escrever do seu jeito.)

Cliente / trabalho:
Quantidade de vídeos:
Duração de cada (30, 45, 60, 75 ou 90 s):
Resolução (1080x1920 padrão, ou 2160x3840):

Foco de cada vídeo:
1.
2.
3.
4.
5.

Descrição das pessoas (cabelo, roupa, maquiagem, idade aproximada):
- Pessoa principal:
- Outras pessoas:

Observações (cenas que não podem faltar, cenas para evitar, estilo do corte):
"""


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("nome", help="nome da pasta, ex.: 2026-10-cabeleireiro")
    p.add_argument("--raiz", default=str(RAIZ), help="onde criar (padrão: a pasta JC-Reels)")
    a = p.parse_args()

    trab = Path(a.raiz) / a.nome
    for sub in ("material", "musica", "prontos"):
        (trab / sub).mkdir(parents=True, exist_ok=True)
    pedido = trab / "pedido.txt"
    if pedido.exists():
        print(f"pedido.txt já existe, mantido: {pedido}")
    else:
        pedido.write_text(MODELO, encoding="utf-8")
    print(f"Trabalho pronto em {trab}")
    print("Agora: coloque o vídeo em material\\, a música em musica\\ e preencha o pedido.txt.")


if __name__ == "__main__":
    sys.exit(main())
