$ErrorActionPreference = 'Stop'
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    throw 'Docker is not installed or is not on PATH. Install and start Docker Desktop first.'
}
Write-Host 'Checking whether Docker is running...'
& docker info --format '{{.ServerVersion}}' *> $null
if ($LASTEXITCODE -ne 0) {
    throw 'Docker is not running. Start Docker Desktop and wait for its engine to run.'
}
Write-Host 'Docker is running.'

$client = 'D:\android_app\tunnel-client\tunnel-client.exe'
$composeFile = Join-Path $PSScriptRoot 'compose.yaml'
& docker compose -f $composeFile build
if ($LASTEXITCODE -ne 0) { throw 'TV adapter image build failed; tunnel was not started.' }
if (-not $env:CONTROL_PLANE_API_KEY) {
    $secret = Read-Host 'OpenAI runtime API key' -AsSecureString
    $env:CONTROL_PLANE_API_KEY = [System.Net.NetworkCredential]::new('', $secret).Password
    Remove-Variable secret
}
$env:HEALTH_LISTEN_ADDR = '127.0.0.1:8080'
& $client doctor --profile tv-adapter --explain
if ($LASTEXITCODE -ne 0) { throw 'Tunnel checks failed. Fix the reported check before running.' }
& $client run --profile tv-adapter
