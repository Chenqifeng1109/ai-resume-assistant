# OfferForge 3.0 一键打包 Windows 桌面端绿色版脚本
param(
    [switch]$SkipFrontendBuild
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not $SkipFrontendBuild) {
    Write-Host "[1/3] 构建前端 Vite 生产产物..." -ForegroundColor Cyan
    Push-Location "$root\frontend"
    npm run lint
    if ($LASTEXITCODE -ne 0) { throw "前端 lint 失败" }
    npm run build
    if ($LASTEXITCODE -ne 0) { throw "前端 build 失败" }
    Pop-Location
}

Write-Host "[2/3] 使用 PyInstaller 构建 OfferForge.exe（无黑框窗口）..." -ForegroundColor Cyan
python -m PyInstaller --noconfirm --clean "$root\OfferForge.spec"
if ($LASTEXITCODE -ne 0) { throw "PyInstaller 打包失败" }

Write-Host "[3/3] 运行独立启动冒烟验收..." -ForegroundColor Cyan
$proc = Start-Process -FilePath "$root\dist\OfferForge\OfferForge.exe" -ArgumentList "--smoke-test" -Wait -PassThru
if ($proc.ExitCode -ne 0) {
    throw "OfferForge.exe 冒烟测试失败（ExitCode=$($proc.ExitCode)），请检查 dist\OfferForge\logs\desktop.log"
}
Remove-Item -Force -ErrorAction SilentlyContinue "$root\dist\OfferForge\logs\smoke_test.json"
Write-Host "[OK] 桌面端构建与验收完成：$root\dist\OfferForge\OfferForge.exe" -ForegroundColor Green
