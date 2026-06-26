# install_plugins.ps1 — 권장 QGIS 플러그인 일괄 설치 (Windows / PowerShell)
#
# 본인 PC(QGIS 데스크톱 설치 환경)에서 실행한다.
# 사용법:
#   powershell -ExecutionPolicy Bypass -File qgis\scripts\install_plugins.ps1
#
# 설치 후 QGIS 재시작 → '플러그인 → 플러그인 관리 및 설치 → 설치됨'에서 활성화 확인.

$ErrorActionPreference = "Continue"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ListFile  = Join-Path $ScriptDir "plugins.txt"

# 1) 플러그인 디렉터리 (필요시 $env:QGIS_PLUGIN_DIR 로 덮어쓰기)
$PluginDir = if ($env:QGIS_PLUGIN_DIR) { $env:QGIS_PLUGIN_DIR }
             else { Join-Path $env:APPDATA "QGIS\QGIS3\profiles\default\python\plugins" }
Write-Host "▶ 플러그인 설치 대상: $PluginDir"
New-Item -ItemType Directory -Force -Path $PluginDir | Out-Null

# 2) qgis-plugin-manager 준비
if (-not (Get-Command qgis-plugin-manager -ErrorAction SilentlyContinue)) {
  Write-Host "▶ qgis-plugin-manager 설치 중 (pip)..."
  python -m pip install --user qgis-plugin-manager
}

# 3) 메타데이터 갱신
Set-Location $PluginDir
qgis-plugin-manager init   2>$null
qgis-plugin-manager update

# 4) 목록 설치
$ok = @(); $fail = @()
Get-Content $ListFile | ForEach-Object {
  $name = ($_ -replace '#.*','').Trim()
  if ($name) {
    Write-Host "▶ 설치: $name"
    qgis-plugin-manager install $name
    if ($LASTEXITCODE -eq 0) { $ok += $name } else { $fail += $name }
  }
}

Write-Host "✔ 성공 ($($ok.Count)): $($ok -join ', ')"
if ($fail.Count) { Write-Host "✖ 실패 ($($fail.Count)): $($fail -join ', ')" }
Write-Host "다음 단계: QGIS 재시작 후 활성화 확인."
