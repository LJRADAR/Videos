# JC-Reels — Reels automáticos da JC Creative Works

Fale sempre em **português do Brasil**, de forma direta. O usuário é editor de vídeo e
filmmaker, **não é programador**: explique o resultado, não o código.

## Regras que nunca mudam

- **Nunca apague, mova ou altere** nada em `material/` nem em `musica/`. Os scripts só leem.
- Para apagar qualquer arquivo, mostre a lista primeiro e espere o OK.
- **Nada vai para a internet.** Não envie vídeos, quadros ou músicas a nenhum serviço.
- Pessoas são identificadas **só pela descrição** do pedido (roupa, cabelo, maquiagem,
  idade aproximada). Não tente reconhecer ninguém pelo rosto nem dizer quem é.
- Antes de cada etapa, diga de uma vez tudo o que vai precisar autorizar.

## Estrutura

```
C:\JC-Reels\
  CLAUDE.md                este arquivo
  ferramentas\             scripts (Python + ffmpeg)
  modelos\                 modelo de transcrição (baixado uma vez; nunca enviar áudio para fora)
  fontes\                  fontes das letras (Montserrat ExtraBold vem no instalador)
  <trabalho>\              um por cliente, ex.: 2026-10-cabeleireiro
    material\              vídeo(s) da decupagem (4K, original — só leitura)
    musica\                música: áudio ou vídeo (só o som é usado)
    luts\                  opcional: arquivos .cube de cor (LUT) do usuário
    pedido.txt             quantidade, foco de cada vídeo, pessoas, duração
    plano.json             cenas escolhidas por você (Claude) para cada Reels
    analise\               quadros, folhas de contato, batidas (pode apagar depois)
    prontos\               Reels prontos + relatorio.txt
```

Os comandos usam `py` (o lançador do Python no Windows), rodados de dentro de `C:\JC-Reels`.

## Quando o usuário disser "faz os reels da pasta X"

1. **Conferir o pedido.** Leia `X\pedido.txt`. Se faltar quantidade, duração (30, 45, 60, 75
   ou 90 s), foco de cada vídeo ou descrição da pessoa principal, pergunte tudo numa
   mensagem só antes de começar. Confira se há vídeo em `material\` e música em `musica\`.
   Se a música vier como **link** (YouTube etc.) e `musica\` estiver vazia, baixe só o áudio:
   `py ferramentas\baixar_musica.py X "LINK"`. Lembre o usuário, uma vez, que música com
   direitos autorais pode ser silenciada pelo Instagram. Nunca envie nada do trabalho para fora.

2. **Analisar o material** (leva alguns minutos em 4K):
   `py ferramentas\analisar.py X`
   Para material curto ou muito dinâmico, use `--cada 1`. Gera `analise\material.json`,
   `analise\indice.csv` e as folhas em `analise\folhas_2s\`.

3. **Detectar as batidas:** `py ferramentas\batidas.py X`
   Gera `analise\batidas.json` com BPM, batidas, batidas fortes e o melhor ponto de início
   da música para cada duração (`trechos`).

4. **Olhar as folhas de contato** (leia cada `.jpg` de `analise\folhas_*`). Cada quadro tem
   o rótulo `V1 mm:ss` (V1 = primeiro vídeo da lista em material.json; o tempo é o do
   material). Monte uma lista de cenas com tempo inicial e final, e classifique cada uma:
   - **tema**: os do pedido (ex.: maquiagem, penteado, sorrisos/descontraído, detalhes,
     plano geral, antes/depois);
   - **pessoa**: pela descrição do pedido (ex.: "cliente: cabelo castanho longo, blusa
     branca"), nunca pelo rosto;
   - **qualidade**: foco, tremido, luz, movimento bonito. Use `indice.csv` para ajudar:
     `nitidez` baixa = desfocado, `movimento` alto = câmera mexendo ou ação, `brilho` muito
     baixo/alto = luz ruim, `rosto_x` = onde está o rosto (0 = esquerda, 1 = direita).
   Para conferir um trecho de perto, extraia quadros maiores só dele, por exemplo:
   `ffmpeg -ss 83 -i X\material\C0001.MP4 -frames:v 1 -vf scale=960:-2 X\analise\conferir.jpg`
   Mostre ao usuário um resumo curto das cenas por tema antes de montar o plano se o
   material for confuso; senão, siga direto.

5. **Escrever `X\plano.json`** (formato abaixo). Critérios:
   - cada Reels usa só cenas do seu tema (o "geral" mistura temas);
   - **nenhum trecho repete entre Reels** (o script recusa o plano se repetir);
   - **abrir com a cena mais forte** (impacto visual nos 2 primeiros segundos) e **fechar
     bem** (sorriso, resultado final, plano bonito); a última cena recebe fade automático;
   - cortes nas batidas: 2 batidas por cena é o padrão; cenas de impacto ou movimento
     bonito podem ter 4 ou 8; sequências rápidas, 1 batida (não abaixo de ~0,4 s);
   - use `velocidade: 0.5` (câmera lenta) só se o material for 50/60 fps ou mais;
   - some as batidas para cobrir a duração: duração ÷ intervalo_batida ≈ total de batidas.
     Ponha algumas cenas a mais no fim da lista: as que não couberem são ignoradas;
   - deixe `musica_inicio` de fora para usar o trecho mais forte da música para aquela
     duração, ou escolha um ponto (o script ajusta para a batida mais próxima).

6. **Acabamento (opcional, campos novos — ver "Acabamento" abaixo):** pergunte numa mensagem
   só, junto com o resto do pedido, se o usuário quer legendas, textos na tela (gancho, nome do
   salão/cliente, chamada final), LUT e som original. Não invente textos: use os que ele der.
   Conferir o plano: `py ferramentas\montar.py X --conferir`. Corrija qualquer ERRO e repasse os
   AVISOS (ex.: material Log sem LUT).

7. **Exportar:** `py ferramentas\montar.py X` (5 Reels de 45 s levam uns 10–15 min neste
   notebook). Antes, peça ao usuário para fechar o Chrome e o CapCut: o notebook tem só 4 GB
   de RAM. Para conferir rápido antes do render final: `--previa` (540x960, em
   `prontos\previa\`). Para refazer um só: `--so 02-penteado`.

   Com `legendas: true`, a primeira vez baixa o modelo de transcrição (~480 MB) se o
   instalador ainda não baixou; depois o .srt fica em `prontos\NN-nome.srt`. Se o usuário
   corrigir alguma palavra no .srt, troque para `legendas: "srt"` e exporte de novo com `--so`.
8. **Entregar:** liste os arquivos de `prontos\` com a duração de cada um, resuma o
   `relatorio.txt` e pergunte se quer ajustar algum (trocar cena, ritmo, mais curto/longo).
   Ajustes = editar o `plano.json` e rodar de novo com `--so`.

## Formato do plano.json

```json
{
  "resolucao": "1080x1920",
  "batidas_por_corte": 2,
  "reels": [
    {
      "nome": "01-maquiagem",
      "duracao": 45,
      "musica_inicio": 12.3,
      "cenas": [
        {"material": "C0001.MP4", "inicio": 83.0, "batidas": 4, "nota": "close do olho, abertura"},
        {"material": "C0001.MP4", "inicio": 140.5, "batidas": 2, "foco_x": 0.35},
        {"material": "C0001.MP4", "inicio": 201.0, "batidas": 2, "zoom": 1.4},
        {"material": "C0001.MP4", "inicio": 260.0, "batidas": 4, "velocidade": 0.5}
      ]
    }
  ]
}
```

| Campo | O que é |
|---|---|
| `resolucao` | `1080x1920` (padrão) ou `2160x3840` se o usuário pedir |
| `fps` | opcional; padrão: o do material (50/60 viram 25/30) |
| `batidas_por_corte` | batidas por cena quando a cena não diz |
| `permitir_repeticao` | `true` só se o usuário pedir para repetir trechos entre Reels |
| `nome` | nome do arquivo final (`01-maquiagem` → `prontos\01-maquiagem.mp4`) |
| `duracao` | segundos; o fim é ajustado para cair numa batida |
| `musica_inicio` | onde a música começa (s); omitido = trecho mais forte |
| `material` | nome do arquivo em `material\` |
| `inicio` | segundo do material onde a cena começa (o fim sai das batidas) |
| `batidas` | quantas batidas a cena dura na tela |
| `foco_x` | centro horizontal do corte 9:16: `"auto"` (padrão, segue o rosto) ou 0–1 |
| `foco_y` | centro vertical (0–1), útil se o material já for vertical; padrão 0.5 |
| `zoom` | 1 = corte 9:16 máximo; 1.3–1.6 aproxima (cuidado: perde nitidez em 1080p acima de ~1.7) |
| `velocidade` | 1 normal; 0.5 = câmera lenta 2x (só com material 50/60 fps) |
| `nota` | texto livre que aparece no relatório |
| `lut` | arquivo .cube de `luts\` (no plano inteiro ou por cena; `""` desliga numa cena) |
| `som_original` | por cena, 0 a 1 (padrão 0): mistura o som da câmera; a música abaixa sozinha na fala |
| `legendas` | no plano ou por Reels: `true` (transcreve), `"srt"` (usa o .srt editado), `false` |
| `estilo_legenda` | no plano: `{"tamanho": 84, "cor": "branco", "destaque": "amarelo", "maiusculas": false}`; `destaque: false` tira a palavra colorida |
| `textos` | por Reels: lista de textos na tela (ver abaixo) |
| `fonte` | no plano: nome da fonte (padrão Montserrat ExtraBold; sem ela, Arial Black) |

## Acabamento: quando usar cada campo

Quem não usar estes campos recebe o mesmo vídeo de antes. Só o volume muda: **o áudio final
sai sempre em -14 LUFS, com pico de no máximo -1 dBTP** (padrão do Instagram).

- **`lut`**: quando o material for **Log** (o `--conferir` avisa: imagem lavada, pouca cor) ou
  quando o usuário pedir um "look". O usuário coloca o .cube em `X\luts\`. A cor é aplicada
  depois do corte e da redução, para pesar menos (é o recurso mais pesado: cerca de +1 min por
  Reels de 45 s no notebook).
- **`legendas: true`**: quando há **fala** útil (cliente comentando, depoimento). Transcreve
  só o som das cenas usadas, em português, no próprio notebook. 2 a 4 palavras por vez, palavra
  da vez destacada, dentro da área segura do Instagram. Sem fala, não use (sairia vazio ou com
  palavras inventadas a partir de ruído).
- **`textos`**: lista de `{"texto", "inicio", "duracao", "estilo", "posicao"}`.
  Estilos: `"gancho"` (grande, no alto, entra com "pop" — use nos 0–3 s), `"nome"` (pequeno
  com caixa, abaixo das legendas — nome do salão/profissional), `"chamada"` (amarelo, no meio
  — fim do vídeo: "Agende seu horário"), `"simples"`. `posicao`: `"topo"`, `"centro"`,
  `"baixo"` ou um número de 0 a 1 (altura). Opcionais: `tamanho`, `cor`, `fonte`.
  Textos curtos (até ~25 letras por linha). Não coloque texto por cima do rosto da cliente.
- **`som_original`**: em cenas com fala ou som bonito (risada, secador, tesoura). 1 = som cheio,
  0.3–0.5 = ambiente de fundo. A música abaixa cerca de 8 dB na fala e volta depois. Em câmera
  lenta o som também fica lento (às vezes estranho: prefira 0 nessas cenas).

Exemplo de Reels com acabamento:

```json
{"nome": "04-descontraidos", "duracao": 45, "legendas": true,
 "textos": [
   {"texto": "O dia da noiva", "inicio": 0, "duracao": 2.5, "estilo": "gancho"},
   {"texto": "Studio Bella", "inicio": 3, "duracao": 3, "estilo": "nome"},
   {"texto": "Agende seu horário", "inicio": 40, "duracao": 5, "estilo": "chamada"}],
 "cenas": [
   {"material": "C0001.MP4", "inicio": 83.0, "batidas": 4, "som_original": 1, "lut": "rec709.cube"}]}
```

## Detalhes técnicos

- **Uma codificação só:** cor, legendas e textos são aplicados dentro da codificação de cada
  cena (com o tempo ajustado para a cena). Texto que atravessa um corte é dividido no corte,
  igual dos dois lados; fade/"pop" só no começo real. As cenas são unidas sem recodificar.
- A transcrição roda num processo separado (libera ~1 GB de RAM ao terminar) e fica guardada em
  `analise\legendas\`: refazer a exportação não transcreve de novo se as cenas não mudaram.
- Áudio: música + som original → mixagem (música abaixa na fala) → loudnorm em duas passadas.
  Se a música for muito "dinâmica", o limite de pico manda e o volume pode ficar até ~1 LU
  abaixo de -14 (normal).

- Material 4K 16:9 → corte 9:16 de 1215x2160 reduzido para 1080x1920: não perde qualidade.
  Em `2160x3840` o corte é ampliado (fica mais suave); avise o usuário.
- Codificador: Quick Sync (`h264_qsv`) se funcionar; senão NVENC/AMF; senão `libx264`. Cada
  cena é codificada uma vez em alta qualidade e as cenas são unidas sem recodificar.
- O enquadramento automático usa a posição dos rostos achados nas folhas (só posição).
  Se a pessoa principal não for o rosto mais visível, use `foco_x` manual.
- `analise\` pode ser apagada depois que o trabalho for entregue (pergunte antes).
- Notebook: i3-1115G4, 4 GB de RAM, Intel UHD com Quick Sync, SSD de 256 GB. Feche
  outros programas antes de exportar.
