$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$releaseDir = Join-Path $projectRoot "release"
$zipPath = Join-Path $releaseDir "deploy.zip"

if (-not (Test-Path $releaseDir)) {
    New-Item -ItemType Directory -Path $releaseDir | Out-Null
}

if (Test-Path $zipPath) {
    Remove-Item $zipPath -Force
}

$items = @(
    "app",
    "scripts",
    "tests",
    "README.md",
    "DEPLOY.md",
    "Dockerfile",
    "docker-compose.yml",
    "deploy.sh",
    "pytest.ini",
    "requirements.txt",
    ".dockerignore",
    ".gitignore",
    ".env.example"
) | ForEach-Object {
    Join-Path $projectRoot $_
}

Compress-Archive -Path $items -DestinationPath $zipPath -Force

Write-Host "Deploy package created:"
Write-Host $zipPath
