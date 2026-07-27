$ErrorActionPreference = "Stop"

$ProjectRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path
$VenvPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot ".venv"))
$ExpectedVenvPath = [System.IO.Path]::GetFullPath((Join-Path $ProjectRoot ".venv"))
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$Requirements = Join-Path $ProjectRoot "requirements-dev.txt"
$BundledPython = "C:\Users\kono707da\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe"

if ($VenvPath -ne $ExpectedVenvPath -or (Split-Path -Parent $VenvPath) -ne $ProjectRoot) {
    throw "Virtual environment path validation failed."
}
if (-not (Test-Path -LiteralPath $Requirements)) {
    throw "Development requirements file was not found: $Requirements"
}

function Test-AtelierEnvironment {
    param([string]$PythonPath)
    try {
        if (-not (Test-Path -LiteralPath $PythonPath)) {
            return $false
        }
        & $PythonPath -c "import fastapi, uvicorn, httpx, anyio._backends._asyncio" 2>$null
        return $LASTEXITCODE -eq 0
    } catch {
        return $false
    }
}

function Resolve-BasePython {
    if (Test-Path -LiteralPath $BundledPython) {
        return $BundledPython
    }
    foreach ($candidate in @("py.exe", "python.exe")) {
        $command = Get-Command $candidate -ErrorAction SilentlyContinue
        if ($command) {
            return $command.Source
        }
    }
    throw "Python 3 was not found."
}

Set-Location -LiteralPath $ProjectRoot

if ((Test-Path -LiteralPath $VenvPath) -and -not (Test-AtelierEnvironment $VenvPython)) {
    $BackupPath = Join-Path $ProjectRoot (".venv.broken." + (Get-Date -Format "yyyyMMdd-HHmmss"))
    $ResolvedBackup = [System.IO.Path]::GetFullPath($BackupPath)
    if ((Split-Path -Parent $ResolvedBackup) -ne $ProjectRoot) {
        throw "Virtual environment backup path validation failed."
    }
    Write-Host "Existing virtual environment is incomplete."
    Write-Host "Moving it to: $ResolvedBackup"
    Move-Item -LiteralPath $VenvPath -Destination $ResolvedBackup
}

if (-not (Test-Path -LiteralPath $VenvPython)) {
    $BasePython = Resolve-BasePython
    Write-Host "Creating Atelier virtual environment..."
    & $BasePython -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Virtual environment creation failed."
    }
}

Write-Host "Installing Atelier runtime and test dependencies..."
& $VenvPython -m pip install --disable-pip-version-check --upgrade -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Dependency installation failed."
}

if (-not (Test-AtelierEnvironment $VenvPython)) {
    throw "Dependency validation failed."
}

Write-Host "Atelier environment is ready."
