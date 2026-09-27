<#
  ComfyUI 포터블 + YuE2 음악 모델 자동 설치 (Windows)

  실행 방법 (PowerShell):
    powershell -ExecutionPolicy Bypass -File .\install_windows.ps1
  이미 ComfyUI 포터블이 있으면:
    powershell -ExecutionPolicy Bypass -File .\install_windows.ps1 -ComfyRoot "D:\ComfyUI_windows_portable"

  하는 일
    1) ComfyUI 포터블(v0.36 이상 필요)을 내려받아 압축 해제 — 이미 있으면 stable 업데이트
    2) YuE2 모델 yue2_3b_int8_convrot.safetensors (3.96GB) → ComfyUI\models\checkpoints
    3) generate_music.py 가 쓸 config.json 작성, 실행용 .bat 생성
#>
param(
  [string]$ComfyRoot = "$env:USERPROFILE\ComfyUI_windows_portable",
  [ValidateSet("auto", "nvidia", "nvidia_cu126", "amd", "intel")]
  [string]$Gpu = "auto",
  [switch]$SkipModel
)
$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
$Here = Split-Path -Parent $MyInvocation.MyCommand.Path
$HfBase = "https://huggingface.co/Comfy-Org/YuE2/resolve/main/checkpoints"
$ModelName = "yue2_3b_int8_convrot.safetensors"
$ModelMinBytes = 3900000000

function Step($msg) { Write-Host "`n==> $msg" -ForegroundColor Cyan }

# BOM 없는 UTF-8 로 저장 (한글 경로가 있어도 .bat / python json 에서 깨지지 않게)
function WriteUtf8($path, $text) { [IO.File]::WriteAllText($path, $text, (New-Object Text.UTF8Encoding $false)) }

function Download($url, $dest) {
  # curl.exe (Windows 10 1803+ 기본 포함)는 이어받기(-C -)를 지원함
  & curl.exe -L --fail --retry 5 --retry-delay 5 -C - -o $dest $url
  if ($LASTEXITCODE -ne 0) { throw "다운로드 실패: $url" }
}

# ---------- 1. GPU 판별 ----------
if ($Gpu -eq "auto") {
  $names = (Get-CimInstance Win32_VideoController | ForEach-Object { $_.Name }) -join " | "
  Write-Host "감지된 그래픽카드: $names"
  if ($names -match "NVIDIA") {
    if ($names -match "GTX 10|GTX 9|GTX 7") { $Gpu = "nvidia_cu126" } else { $Gpu = "nvidia" }
  } elseif ($names -match "AMD|Radeon") { $Gpu = "amd" }
  elseif ($names -match "Intel.*Arc") { $Gpu = "intel" }
  else { $Gpu = "nvidia"; Write-Warning "GPU를 판별하지 못해 nvidia 버전을 설치함 (CPU로도 실행 가능하나 매우 느림)" }
}
Write-Host "설치 대상: $Gpu"

# ---------- 2. ComfyUI 포터블 설치/업데이트 ----------
$ComfyDir = Join-Path $ComfyRoot "ComfyUI"
$Python = Join-Path $ComfyRoot "python_embeded\python.exe"

if (Test-Path (Join-Path $ComfyDir "main.py")) {
  Step "기존 ComfyUI 발견 → stable 버전으로 업데이트"
  Push-Location (Join-Path $ComfyRoot "update")
  cmd /c "update_comfyui_stable.bat nopause"
  Pop-Location
} else {
  Step "ComfyUI 포터블 다운로드 ($Gpu)"
  $parent = Split-Path -Parent $ComfyRoot
  New-Item -ItemType Directory -Force -Path $parent | Out-Null
  $archive = Join-Path $parent "ComfyUI_windows_portable_$Gpu.7z"
  Download "https://github.com/comfyanonymous/ComfyUI/releases/latest/download/ComfyUI_windows_portable_$Gpu.7z" $archive
  $sevenZip = Join-Path $parent "7zr.exe"
  if (-not (Test-Path $sevenZip)) { Download "https://www.7-zip.org/a/7zr.exe" $sevenZip }
  Step "압축 해제"
  $tmp = Join-Path $parent "_comfy_extract"
  & $sevenZip x $archive "-o$tmp" -y | Out-Null
  if ($LASTEXITCODE -ne 0) { throw "압축 해제 실패" }
  $inner = Get-ChildItem $tmp -Directory | Select-Object -First 1
  if (Test-Path $ComfyRoot) { throw "$ComfyRoot 가 이미 있지만 ComfyUI가 아님. 다른 경로를 -ComfyRoot 로 지정하세요." }
  Move-Item $inner.FullName $ComfyRoot
  Remove-Item $tmp -Recurse -Force
  Remove-Item $archive -Force
}

# 버전 확인 (YuE2 는 v0.36.0 이상에서 기본 지원)
$verFile = Join-Path $ComfyDir "comfyui_version.py"
$ver = (Select-String -Path $verFile -Pattern '__version__ = "(.+)"').Matches[0].Groups[1].Value
Write-Host "ComfyUI 버전: $ver"
if ([version]$ver -lt [version]"0.36.0") { throw "ComfyUI $ver 는 YuE2 미지원. update\update_comfyui.bat 로 업데이트 후 다시 실행하세요." }
if (-not (Test-Path (Join-Path $ComfyDir "comfy_extras\nodes_yue2.py"))) { throw "YuE2 노드가 없음. ComfyUI 업데이트가 필요함." }

# ---------- 3. 음악 모델 다운로드 ----------
$ckptDir = Join-Path $ComfyDir "models\checkpoints"
New-Item -ItemType Directory -Force -Path $ckptDir | Out-Null
if (-not $SkipModel) {
  $dest = Join-Path $ckptDir $ModelName
  if ((Test-Path $dest) -and ((Get-Item $dest).Length -ge $ModelMinBytes)) {
    Step "모델 이미 있음: $dest"
  } else {
    Step "YuE2 모델 다운로드 (3.96GB, 중단돼도 다시 실행하면 이어받음)"
    Download "$HfBase/$ModelName" $dest
  }
}

# ---------- 4. 자동 생성 설정 ----------
Step "config.json / 실행 파일 작성"
$cfg = [ordered]@{
  comfy_dir  = $ComfyDir
  python     = $Python
  server     = "127.0.0.1:8188"
  ckpt       = $ModelName
  extra_args = @("--windows-standalone-build")
}
# BOM 없는 UTF-8 로 저장 (python json 이 읽을 수 있게)
WriteUtf8 (Join-Path $Here "config.json") ($cfg | ConvertTo-Json)

@"
@echo off
chcp 65001 >nul
cd /d "$ComfyRoot"
.\python_embeded\python.exe -s ComfyUI\main.py --windows-standalone-build
pause
"@ | ForEach-Object { WriteUtf8 (Join-Path $Here "start_comfyui.bat") $_ }

@"
@echo off
chcp 65001 >nul
rem usage: make_song.bat songs\example_ko_ballad.json
"$Python" -s "%~dp0generate_music.py" --song %*
pause
"@ | ForEach-Object { WriteUtf8 (Join-Path $Here "make_song.bat") $_ }

Write-Host "`n설치 완료!" -ForegroundColor Green
Write-Host "  ComfyUI 실행      : $Here\start_comfyui.bat  (브라우저 http://127.0.0.1:8188)"
Write-Host "  노래 자동 생성     : $Python -s generate_music.py --song songs\example_ko_ballad.json"
Write-Host "  결과 저장 위치     : $Here\output"
