# Verifica o ultimo run do workflow "Clash Royale Sync (Inteligente)" no GitHub Actions.
# Se o run mais recente falhou e ainda nao foi tratado, aciona o Sync_Elite.bat
# (modo silencioso) para sincronizar e subir os dados manualmente como fallback.
# Se nao houve falha nova, nao faz nada e encerra.

$ErrorActionPreference = "Stop"
$scriptDir   = $PSScriptRoot
$projectRoot = Split-Path -Parent $scriptDir
Set-Location $projectRoot

$stateFile = Join-Path $scriptDir ".watcher_last_run_id.txt"
$logFile   = Join-Path $scriptDir "watcher.log"

function Log($msg) {
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') - $msg"
    Add-Content -Path $logFile -Value $line
}

try {
    $raw = & gh run list --workflow "clash-royale-sync.yml" --limit 1 --json databaseId,status,conclusion 2>&1
    $runs = $raw | ConvertFrom-Json

    if (-not $runs -or $runs.Count -eq 0) {
        Log "Nenhum run encontrado para o workflow."
        exit 0
    }

    $run = $runs[0]

    if ($run.status -ne "completed") {
        Log "Run $($run.databaseId) ainda em andamento (status=$($run.status)). Nada a fazer agora."
        exit 0
    }

    $lastProcessed = $null
    if (Test-Path $stateFile) {
        $content = (Get-Content $stateFile -Raw).Trim()
        if ($content) { $lastProcessed = [int64]$content }
    }

    if ($lastProcessed -eq [int64]$run.databaseId) {
        # Este run ja foi avaliado numa checagem anterior; nada novo.
        exit 0
    }

    # Marca este run como avaliado, independente do resultado, para nao reprocessar.
    Set-Content -Path $stateFile -Value $run.databaseId

    if ($run.conclusion -eq "failure") {
        Log "FALHA detectada no run $($run.databaseId). Acionando Sync_Elite.bat (silent)..."
        $batPath = Join-Path $scriptDir "Sync_Elite.bat"
        $output = & cmd.exe /c "`"$batPath`" silent" 2>&1
        Add-Content -Path $logFile -Value $output
        Log "Sync_Elite.bat concluido para o run $($run.databaseId)."
    } else {
        Log "Run $($run.databaseId) concluido sem falha (conclusion=$($run.conclusion)). Nada a fazer."
    }
}
catch {
    Log "ERRO no watcher: $_"
}
