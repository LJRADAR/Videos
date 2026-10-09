# Vídeos — edição automática

Ferramentas para transformar gravações (cabelo, festas, eventos, imóveis, drone)
em vídeos curtos para YouTube Shorts, Instagram Reels e TikTok.

## Pastas

| Pasta | Para quê |
|---|---|
| `entrada/` | Vídeos brutos que você quer editar |
| `saida/` | Vídeos prontos |
| `ferramenta/` | Scripts de edição |
| `analise/` | Miniaturas e cenas geradas na análise (não vai para o Git) |

## Como pedir uma edição ao Claude

1. Coloque o vídeo em `entrada/` (ou mande um link do Google Drive).
2. Peça, por exemplo: *"transforma o vídeo X em Short de até 3 minutos"*.

## Ferramentas

- `ferramenta/analisar.py VIDEO` — mostra duração, trocas de cena e folhas de miniaturas.
- `ferramenta/vertical.py VIDEO` — converte 16:9 em 9:16 (1080x1920), limitando a 2:59 para Shorts.
  - `--modo fundo` (padrão): vídeo inteiro com fundo desfocado.
  - `--modo corte`: corta o centro e preenche a tela.
  - `--inicio S` e `--max S`: escolhe o trecho.

Requer `ffmpeg` e Python 3.

## Limites das plataformas

- YouTube Shorts: vertical, até 3:00.
- Instagram Reels: até 3:00 no app.
- Upload pelo site do GitHub: até 25 MB por arquivo — vídeos maiores, use link do Google Drive.
