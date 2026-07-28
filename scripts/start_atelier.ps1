param(
    [ValidateSet("production", "test")]
    [string]$Environment = "production",
    [int]$Port = 8110
)

$ErrorActionPreference = "Stop"
$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

# Locate a working Python interpreter (design §13.2 step 2):
# prefer the project virtual environment, then fall back to a system Python.
function Find-AtelierPython {
    param([string]$Root)
    $candidates = @()
    $venvPy = Join-Path $Root ".venv\Scripts\python.exe"
    if (Test-Path -LiteralPath $venvPy -ErrorAction SilentlyContinue) {
        $candidates += $venvPy
    }
    $sysPy = (Get-Command python -ErrorAction SilentlyContinue).Source
    if ($sysPy) { $candidates += $sysPy }
    foreach ($py in $candidates) {
        try {
            & $py -c "import sys, fastapi, uvicorn" 2>$null | Out-Null
            if ($LASTEXITCODE -eq 0) { return $py }
        } catch { }
    }
    return $null
}

$Python = Find-AtelierPython -Root $ProjectRoot
if (-not $Python) {
    Write-Host "No working Python with FastAPI/Uvicorn was found."
    Write-Host "Run setup.bat first."
    exit 1
}
if ($Python -ne (Join-Path $ProjectRoot ".venv\Scripts\python.exe")) {
    Write-Host "Virtual environment unavailable; using system Python: $Python"
}

$Listeners = @(Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue)
if ($Listeners.Count -gt 0) {
    $ProcessIds = @($Listeners | Select-Object -ExpandProperty OwningProcess -Unique)
    foreach ($ProcessId in $ProcessIds) {
        $ProcessInfo = Get-CimInstance Win32_Process -Filter "ProcessId = $ProcessId"
        $CommandLine = [string]$ProcessInfo.CommandLine
        # --atelier-server is an Atelier-only flag; path comparison is unreliable
        # because Windows path casing differs between launchers (e.g. C:\ vs c:\).
        $IsAtelier = $CommandLine.Contains("--atelier-server")
        if (-not $IsAtelier) {
            Write-Host "Port $Port is used by another application (PID $ProcessId)."
            Write-Host "Atelier startup stopped without terminating that process."
            exit 1
        }
    }

    foreach ($ProcessId in $ProcessIds) {
        Write-Host "Stopping previous Atelier process (PID $ProcessId)..."
        & taskkill.exe /PID $ProcessId /T /F | Out-Null
    }

    $Deadline = (Get-Date).AddSeconds(10)
    while ((Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) -and (Get-Date) -lt $Deadline) {
        Start-Sleep -Milliseconds 250
    }
    if (Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue) {
        Write-Host "Port $Port did not become available."
        exit 1
    }
}

$LockArgument = @()
if ($Environment -eq "test") {
    $LockArgument = @("--lock-database")
}

Write-Host "Starting Atelier on http://127.0.0.1:$Port"
Write-Host "Database environment: $Environment"
Set-Location -LiteralPath $ProjectRoot
& $Python -m backend.app.run --atelier-server --project-root $ProjectRoot --host 127.0.0.1 --port $Port --environment $Environment @LockArgument
exit $LASTEXITCODE

