param(
    [string]$ProxyHost = "127.0.0.1",
    [int]$ProxyPort = 7897,
    [switch]$RestartDockerDesktop
)

$settingsPath = Join-Path $env:APPDATA "Docker\settings-store.json"
if (-not (Test-Path $settingsPath)) {
    throw "Docker Desktop settings file not found: $settingsPath"
}

$proxyUrl = "http://$ProxyHost`:$ProxyPort"
$exclude = "localhost,127.0.0.1,::1"

$settings = Get-Content $settingsPath -Raw -Encoding UTF8 | ConvertFrom-Json

$settings | Add-Member -NotePropertyName "ProxyHTTPMode" -NotePropertyValue "manual" -Force
$settings | Add-Member -NotePropertyName "OverrideProxyHTTP" -NotePropertyValue $proxyUrl -Force
$settings | Add-Member -NotePropertyName "OverrideProxyHTTPS" -NotePropertyValue $proxyUrl -Force
$settings | Add-Member -NotePropertyName "OverrideProxyExclude" -NotePropertyValue $exclude -Force

$settings | ConvertTo-Json -Depth 100 | Set-Content $settingsPath -Encoding UTF8
Write-Host "Docker Desktop proxy settings updated to $proxyUrl"

if ($RestartDockerDesktop) {
    Get-Process "Docker Desktop" -ErrorAction SilentlyContinue | Stop-Process -Force
    Start-Sleep -Seconds 2
    Start-Process "C:\Program Files\Docker\Docker\Docker Desktop.exe" -WindowStyle Hidden
    Write-Host "Docker Desktop restart requested."
}
