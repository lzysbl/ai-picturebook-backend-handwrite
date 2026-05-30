<#
用途：
- 打包项目部署文件到 release/deploy.zip，方便验收或云服务器上传。

关联模块：
- 包含 app、scripts、tests、Dockerfile、requirements.txt 和 .env.example。
- 不包含 .env、数据库文件、缓存目录等本地敏感或运行产物。

运行方式：
- 在项目根目录执行：powershell -ExecutionPolicy Bypass -File scripts\build_deploy_zip.ps1
#>

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
