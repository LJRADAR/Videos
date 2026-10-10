# Diagnóstico do notebook (Etapas 1 e 2) — SOMENTE LEITURA.
# Não apaga, não move e não altera nenhum arquivo. Só gera um relatório.
#
# Como rodar (PowerShell, de preferência "Executar como administrador"):
#   powershell -ExecutionPolicy Bypass -File diagnostico.ps1
# O relatório fica na Área de Trabalho: diagnostico-JC.txt

$ErrorActionPreference = 'SilentlyContinue'
$relatorio = Join-Path ([Environment]::GetFolderPath('Desktop')) 'diagnostico-JC.txt'
$linhas = New-Object System.Collections.Generic.List[string]
function Diz($t = '') { $linhas.Add($t); Write-Host $t }
function GB($b) { '{0:N1} GB' -f ($b / 1GB) }
function Tamanho($b) { if ($b -ge 1GB) { GB $b } else { '{0:N0} MB' -f ($b / 1MB) } }

# Tamanho de uma pasta (recursivo, ignora atalhos de pasta/junções)
function TamanhoPasta($p) {
    if (-not (Test-Path -LiteralPath $p)) { return 0 }
    $total = 0L
    $pilha = New-Object System.Collections.Stack
    $pilha.Push((Get-Item -LiteralPath $p -Force))
    while ($pilha.Count) {
        $d = $pilha.Pop()
        try { foreach ($f in $d.GetFiles()) { $total += $f.Length } } catch {}
        try {
            foreach ($s in $d.GetDirectories()) {
                if (-not ($s.Attributes -band [IO.FileAttributes]::ReparsePoint)) { $pilha.Push($s) }
            }
        } catch {}
    }
    $total
}

Diz "DIAGNÓSTICO JC CREATIVE WORKS — $(Get-Date -Format 'dd/MM/yyyy HH:mm')"
Diz ('=' * 70)

# ---------------- ETAPA 1: configuração ----------------
Diz ''
Diz '== ETAPA 1: CONFIGURAÇÃO =='
$pc  = Get-CimInstance Win32_ComputerSystem
$os  = Get-CimInstance Win32_OperatingSystem
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
Diz "Modelo:       $($pc.Manufacturer) $($pc.Model)"
Diz "Windows:      $($os.Caption) (versão $($os.Version), build $($os.BuildNumber))"
Diz "Processador:  $($cpu.Name.Trim()) — $($cpu.NumberOfCores) núcleos / $($cpu.NumberOfLogicalProcessors) threads"
Diz "Memória RAM:  $(GB $pc.TotalPhysicalMemory)"
$pentes = Get-CimInstance Win32_PhysicalMemory
foreach ($m in $pentes) { Diz "   pente: $(GB $m.Capacity) a $($m.Speed) MHz" }

Diz ''
Diz 'Placas de vídeo e codificador por hardware:'
foreach ($g in Get-CimInstance Win32_VideoController) {
    $n = $g.Name
    $enc = 'nenhum identificado'
    if ($n -match 'NVIDIA')                    { $enc = 'NVIDIA NVENC (h264_nvenc / hevc_nvenc)' }
    elseif ($n -match 'AMD|Radeon')            { $enc = 'AMD AMF (h264_amf / hevc_amf)' }
    elseif ($n -match 'Intel')                 { $enc = 'Intel Quick Sync (h264_qsv / hevc_qsv)' }
    $vram = if ($g.AdapterRAM -gt 0) { " — memória ~$(GB $g.AdapterRAM)" } else { '' }
    Diz "   $n$vram"
    Diz "      driver $($g.DriverVersion) — codificador: $enc"
}

Diz ''
Diz 'Discos:'
foreach ($d in Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3') {
    $uso = 100 - [math]::Round($d.FreeSpace / $d.Size * 100)
    Diz ("   {0}  total {1}  livre {2}  ({3}% usado)  {4}" -f $d.DeviceID, (GB $d.Size), (GB $d.FreeSpace), $uso, $d.VolumeName)
}
foreach ($f in Get-PhysicalDisk) { Diz "   físico: $($f.FriendlyName) — $($f.MediaType) — $(GB $f.Size)" }

# ---------------- ETAPA 2: o que enche o disco ----------------
Diz ''
Diz '== ETAPA 2: O QUE ESTÁ ENCHENDO O DISCO =='
Diz '(varrendo os discos — pode levar de 5 a 30 minutos, não feche a janela)'

$pastas = @{}
$maiores = New-Object System.Collections.Generic.List[object]
$videos  = New-Object System.Collections.Generic.List[object]
$extVideo = '.mp4','.mov','.mxf','.mts','.m2ts','.avi','.mkv','.insv','.lrv','.braw','.r3d'

foreach ($disco in Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3') {
    $raiz = "$($disco.DeviceID)\"
    Write-Host "  varrendo $raiz ..."
    $pilha = New-Object System.Collections.Stack
    $pilha.Push([IO.DirectoryInfo]$raiz)
    while ($pilha.Count) {
        $d = $pilha.Pop()
        $soma = 0L
        try {
            foreach ($f in $d.GetFiles()) {
                $soma += $f.Length
                if ($f.Length -ge 100MB) { $maiores.Add($f) }
                if ($f.Length -ge 50MB -and $extVideo -contains $f.Extension.ToLower()) { $videos.Add($f) }
            }
        } catch {}
        # soma o tamanho em cada pasta-mãe até 4 níveis de profundidade
        $p = $d.FullName.TrimEnd('\')
        $partes = $p.Split('\')
        for ($i = 2; $i -le [math]::Min($partes.Count, 5); $i++) {
            $chave = ($partes[0..($i - 1)] -join '\')
            $pastas[$chave] = $pastas[$chave] + $soma
        }
        try {
            foreach ($s in $d.GetDirectories()) {
                if (-not ($s.Attributes -band [IO.FileAttributes]::ReparsePoint)) { $pilha.Push($s) }
            }
        } catch {}
    }
}

Diz ''
Diz '-- 30 maiores pastas (até 4 níveis) --'
$pastas.GetEnumerator() | Sort-Object Value -Descending | Select-Object -First 30 | ForEach-Object {
    Diz ("{0,10}  {1}" -f (Tamanho $_.Value), $_.Key)
}

Diz ''
Diz '-- 50 maiores arquivos --'
$maiores | Sort-Object Length -Descending | Select-Object -First 50 | ForEach-Object {
    Diz ("{0,10}  {1}  (modificado {2:dd/MM/yyyy})" -f (Tamanho $_.Length), $_.FullName, $_.LastWriteTime)
}

# Culpados comuns
Diz ''
Diz '-- Culpados comuns --'
$la = $env:LOCALAPPDATA; $ra = $env:APPDATA; $up = $env:USERPROFILE
$suspeitos = [ordered]@{
    'CapCut - cache'                  = "$la\CapCut\User Data\Cache"
    'CapCut - projetos (rascunhos)'   = "$la\CapCut\User Data\Projects"
    'Temporários do usuário (%TEMP%)' = $env:TEMP
    'Temporários do Windows'          = "$env:WINDIR\Temp"
    'Atualizações baixadas do Windows'= "$env:WINDIR\SoftwareDistribution\Download"
    'Windows.old'                     = "$env:SystemDrive\Windows.old"
    'Downloads'                       = "$up\Downloads"
    'Chrome - cache'                  = "$la\Google\Chrome\User Data\Default\Cache"
    'Edge - cache'                    = "$la\Microsoft\Edge\User Data\Default\Cache"
    'Firefox - cache'                 = "$la\Mozilla\Firefox\Profiles"
    'Adobe - Media Cache'             = "$ra\Adobe\Common\Media Cache Files"
    'Adobe - Media Cache (índices)'   = "$ra\Adobe\Common\Media Cache"
    'Adobe - Peak Files'              = "$ra\Adobe\Common\Peak Files"
    'DaVinci Resolve - cache'         = "$ra\Blackmagic Design\DaVinci Resolve\Support\CacheClip"
    'DJI - cache'                     = "$la\DJI"
    'Lixo de relatórios de erro'      = "$la\CrashDumps"
}
foreach ($k in $suspeitos.Keys) {
    $t = TamanhoPasta $suspeitos[$k]
    if ($t -gt 0) { Diz ("{0,10}  {1}  -> {2}" -f (Tamanho $t), $k, $suspeitos[$k]) }
}

$lixeira = 0L
foreach ($disco in Get-CimInstance Win32_LogicalDisk -Filter 'DriveType=3') {
    $lixeira += TamanhoPasta "$($disco.DeviceID)\`$Recycle.Bin"
}
Diz ("{0,10}  Lixeira (todos os discos)" -f (Tamanho $lixeira))

foreach ($f in 'hiberfil.sys','pagefile.sys','swapfile.sys') {
    $a = Get-Item -LiteralPath "$env:SystemDrive\$f" -Force
    if ($a) { Diz ("{0,10}  {1} (arquivo do sistema — não mexer)" -f (Tamanho $a.Length), $f) }
}

Diz ''
Diz '-- Instaladores e compactados em Downloads e Área de Trabalho (> 20 MB) --'
$locais = "$up\Downloads", [Environment]::GetFolderPath('Desktop')
$inst = Get-ChildItem -LiteralPath $locais -Recurse -File -Force -Include *.exe,*.msi,*.zip,*.rar,*.7z,*.iso |
    Where-Object Length -ge 20MB | Sort-Object Length -Descending
$somaInst = ($inst | Measure-Object Length -Sum).Sum
foreach ($i in $inst) { Diz ("{0,10}  {1}  ({2:dd/MM/yyyy})" -f (Tamanho $i.Length), $i.FullName, $i.LastWriteTime) }
Diz ("Total instaladores/compactados: {0}" -f (Tamanho $somaInst))

Diz ''
Diz '-- Vídeos possivelmente duplicados (mesmo tamanho e mesmo conteúdo inicial/final) --'
function Impressao($f) {
    $s = [IO.File]::OpenRead($f.FullName)
    try {
        $n = [math]::Min(1MB, $s.Length); $buf = New-Object byte[] ($n * 2)
        [void]$s.Read($buf, 0, $n)
        [void]$s.Seek(-$n, 'End'); [void]$s.Read($buf, $n, $n)
        $md5 = [Security.Cryptography.MD5]::Create()
        [BitConverter]::ToString($md5.ComputeHash($buf))
    } finally { $s.Close() }
}
$somaDup = 0L
$videos | Group-Object Length | Where-Object Count -gt 1 | ForEach-Object {
    $_.Group | Group-Object { Impressao $_ } | Where-Object Count -gt 1 | ForEach-Object {
        $copias = $_.Group | Sort-Object LastWriteTime
        $somaDup += $copias[0].Length * ($copias.Count - 1)
        Diz ("{0,10}  {1} cópias:" -f (Tamanho $copias[0].Length), $copias.Count)
        foreach ($c in $copias) { Diz "              $($c.FullName)" }
    }
}
Diz ("Espaço ocupado por cópias extras: {0}" -f (Tamanho $somaDup))

Diz ''
Diz "Relatório salvo em: $relatorio"
$linhas | Out-File -FilePath $relatorio -Encoding utf8
