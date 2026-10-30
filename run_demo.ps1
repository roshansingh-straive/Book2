$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    throw "Python environment not found. Run the setup commands in README.md first."
}

npm --prefix app run build
if ($LASTEXITCODE -ne 0) {
    throw "Frontend build failed."
}

$serverHost = if ($env:HOST) { $env:HOST } else { "127.0.0.1" }
$port = if ($env:PORT) { $env:PORT } else { "8000" }
Write-Host "Shelf Check is starting at http://${serverHost}:${port}"
Write-Host "Use the app's Sign in button for Straive LLM Foundry recognition."
Write-Host "Press Ctrl+C to stop."
& $python -m uvicorn server.main:app --host $serverHost --port $port
