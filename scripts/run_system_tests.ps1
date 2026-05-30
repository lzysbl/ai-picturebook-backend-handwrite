<#
用途：
- 一键执行系统验收前的基础检查，并把日志写入 reports/system_tests。

检查内容：
- 运行 pytest。
- 编译关键 Python 文件，检查语法。
- 如果本机有 node，则检查 camera.js 语法。
- 导出 runtime metrics，确认实验数据脚本可运行。

运行方式：
- 在项目根目录执行：powershell -ExecutionPolicy Bypass -File scripts\run_system_tests.ps1
#>

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$reportDir = Join-Path $projectRoot "reports\system_tests"
$logPath = Join-Path $reportDir "system_test_latest.log"

if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir | Out-Null
}

Set-Content -Path $logPath -Value "System test started: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -Encoding UTF8

function Write-LogLine {
    param([string]$Text)
    Write-Host $Text
    Add-Content -Path $logPath -Value $Text -Encoding UTF8
}

function Invoke-LoggedCommand {
    param(
        [string]$Name,
        [scriptblock]$Command
    )

    Write-LogLine ""
    Write-LogLine "## $Name"
    $output = & $Command 2>&1
    $exitCode = $LASTEXITCODE
    $output | ForEach-Object { Write-LogLine ([string]$_) }
    if ($exitCode -ne 0) {
        throw "$Name failed with exit code $exitCode"
    }
}

Push-Location $projectRoot
try {
    Invoke-LoggedCommand "pytest" { pytest }

    Invoke-LoggedCommand "python syntax check" {
        $files = @(
            "app\routers\stories.py",
            "scripts\export_runtime_metrics.py"
        ) + (Get-ChildItem app\services -Filter *.py | ForEach-Object { $_.FullName })
        python -m py_compile @files
    }

    if (Get-Command node -ErrorAction SilentlyContinue) {
        Invoke-LoggedCommand "camera.js syntax check" { node --check app\static\camera.js }
    } else {
        Write-LogLine ""
        Write-LogLine "## camera.js syntax check"
        Write-LogLine "Skipped: node is not installed."
    }

    Invoke-LoggedCommand "runtime metrics export" { python scripts\export_runtime_metrics.py }

    Write-LogLine ""
    Write-LogLine "System test finished: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    Write-LogLine "Runtime metrics: reports\runtime_metrics\runtime_metrics_summary.md"
    Write-LogLine "System test log: reports\system_tests\system_test_latest.log"
} finally {
    Pop-Location
}
