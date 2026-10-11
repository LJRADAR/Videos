# Instalador do JC-Reels.
# Instala ffmpeg e Python (via winget), as bibliotecas Python e baixa os scripts para C:\JC-Reels.
# Não mexe em nenhum vídeo ou foto. Pode rodar de novo para atualizar os scripts:
# as pastas de trabalho (material, musica, prontos) não são tocadas.
#
# Como rodar (PowerShell normal, não precisa ser administrador):
#   powershell -ExecutionPolicy Bypass -File instalar.ps1

$ErrorActionPreference = 'Stop'
$raiz = 'C:\JC-Reels'
$repo = 'https://raw.githubusercontent.com/LJRADAR/Videos/main/jc-reels'
$arquivos = 'CLAUDE.md', 'ferramentas/comum.py', 'ferramentas/analisar.py',
            'ferramentas/batidas.py', 'ferramentas/montar.py', 'ferramentas/novo_trabalho.py',
            'ferramentas/baixar_musica.py', 'ferramentas/acabamento.py', 'ferramentas/transcrever.py'
$fonte = 'https://raw.githubusercontent.com/JulietaUla/Montserrat/master/fonts/ttf/Montserrat-ExtraBold.ttf'

function Passo($t) { Write-Host "`n== $t ==" -ForegroundColor Cyan }
function AtualizarPath {
    $env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
                [Environment]::GetEnvironmentVariable('Path', 'User')
}
function Tem($cmd) { [bool](Get-Command $cmd -ErrorAction SilentlyContinue) }

Passo '1/4 ffmpeg'
AtualizarPath
if (Tem 'ffmpeg') { Write-Host 'ffmpeg já instalado.' }
else {
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    AtualizarPath
    if (-not (Tem 'ffmpeg')) { throw 'ffmpeg não apareceu no PATH. Feche o PowerShell, abra de novo e rode este instalador outra vez.' }
}

Passo '2/4 Python 3.12'
# Testa se o Python 3.12 realmente roda (o "py" pode existir apontando para um Python já removido)
function Py312Ok {
    if (-not (Tem 'py')) { return $false }
    try { $null = & py -3.12 -c "print(1)" 2>&1; return ($LASTEXITCODE -eq 0) } catch { return $false }
}
if (Py312Ok) { Write-Host 'Python 3.12 já instalado.' }
else {
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    AtualizarPath
    if (-not (Py312Ok)) { throw 'O Python 3.12 não respondeu. Feche o PowerShell, abra de novo e rode este instalador outra vez.' }
}
# Faz o comando "py" usar sempre o 3.12 (ignora instalações antigas quebradas)
[Environment]::SetEnvironmentVariable('PY_PYTHON', '3.12', 'User')
$env:PY_PYTHON = '3.12'
Write-Host "Usando $(py --version)"

Passo '3/4 Bibliotecas Python (cerca de 500 MB, alguns minutos)'
py -m pip install --upgrade pip --quiet
py -m pip install --quiet --upgrade numpy librosa soundfile pillow "opencv-python<5" yt-dlp faster-whisper
if ($LASTEXITCODE) { throw 'Falha ao instalar as bibliotecas Python.' }

Passo '4/4 Scripts em C:\JC-Reels'
foreach ($p in 'ferramentas', 'modelos', 'fontes') { New-Item -ItemType Directory -Force -Path "$raiz\$p" | Out-Null }
foreach ($a in $arquivos) {
    $destino = Join-Path $raiz ($a -replace '/', '\')
    Invoke-WebRequest "$repo/$a" -OutFile $destino -UseBasicParsing
    Write-Host "  $destino"
}

Passo 'Fonte e modelo de transcrição (só na primeira vez)'
$arqFonte = "$raiz\fontes\Montserrat-ExtraBold.ttf"
if (-not (Test-Path $arqFonte)) { Invoke-WebRequest $fonte -OutFile $arqFonte -UseBasicParsing; Write-Host "  $arqFonte" }
else { Write-Host '  fonte já instalada.' }
# baixa o modelo "small" (~480 MB) uma vez; o áudio dos trabalhos nunca sai do notebook
py -c "from faster_whisper import WhisperModel; WhisperModel('small', device='cpu', compute_type='int8', download_root=r'$raiz\modelos'); print('  modelo de transcrição pronto.')"
if ($LASTEXITCODE) { Write-Host '  Aviso: o modelo não baixou agora; ele será baixado na primeira legenda.' -ForegroundColor Yellow }

Passo 'Teste'
py -c "import sys; sys.path.insert(0, r'$raiz\ferramentas'); import cv2, librosa, PIL; from comum import codificador; print('Bibliotecas OK. Codificador de vídeo:', codificador())"
if ($LASTEXITCODE) { throw 'O teste falhou. Mande um print desta janela.' }

Write-Host "`nTudo pronto em $raiz." -ForegroundColor Green
Write-Host 'Para criar um trabalho:  cd C:\JC-Reels ; py ferramentas\novo_trabalho.py 2026-10-cabeleireiro'
