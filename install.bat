@echo off
setlocal
:: Windows Console を UTF-8 に設定
chcp 65001 >nul

echo ======================================================
echo  FFmpeg Voicevox Integration Setup (Windows)
echo  [Portable Setup Mode]
echo ======================================================
echo.

:: PowerShell を起動し、このファイルの中身をスクリプトとして実行
powershell -NoProfile -ExecutionPolicy Bypass -Command "$lines = Get-Content -LiteralPath '%~f0' -Encoding UTF8; $start = $false; $script = ($lines | ForEach-Object { if ($start) { $_ } if ($_.Trim() -eq '###_POWERSHELL_START_###') { $start = $true } }) -join [Environment]::NewLine; if ($script) { iex $script } else { Write-Error 'PowerShell section not found' }"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Setup failed with error level %errorlevel%
    pause
)
exit /b %errorlevel%

###_POWERSHELL_START_###
# --- PowerShell Script Section ---

# PowerShell の進捗表示を無効化 (curl を使うので不要)
$ProgressPreference = 'SilentlyContinue'

# コンソール出力の安定化
$OutputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8

# BOMなしUTF-8エンコーディングの定義
$Utf8NoBom = New-Object System.Text.UTF8Encoding $false

# 高速ダウンロード用の関数 (Windows標準の curl.exe を使用)
function Download-Fast {
    param([string]$url, [string]$outPath)
    Write-Host "  -> ダウンロード中: $outPath"
    # -L (リダイレクト追従), --progress-bar (進捗表示), -C - (レジューム)
    curl.exe -L --progress-bar -C - -o $outPath $url
}

$repoUrl = 'https://github.com/mug-lab-3/ffmpeg-voice-vox/archive/refs/heads/main.zip'
$zipFile = 'repo.zip'
$extractDir = 'ffmpeg-voice-vox-main'
$finalDir = '.'

try {
    Write-Host '[1/8] GitHub からリポジトリを取得中...' -ForegroundColor Cyan
    if (-not (Test-Path 'voicevox_controller.py')) {
        Download-Fast $repoUrl $zipFile
        Write-Host '  -> 展開中...'
        Expand-Archive -Path $zipFile -DestinationPath '..' -Force
        Remove-Item $zipFile
        Get-ChildItem -Path "../$extractDir/*" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $finalDir -Recurse -Force
        }
        Remove-Item "../$extractDir" -Recurse -Force
        Write-Host '  -> 完了 (アーカイブを削除しました)'
    } else {
        Write-Host '  -> 既にあるリポジトリを使用します。' -ForegroundColor Yellow
    }

    Write-Host '[2/8] ツール用ディレクトリを準備中...' -ForegroundColor Cyan
    $toolDir = Join-Path (Get-Location) 'tools'
    if (-not (Test-Path $toolDir)) { New-Item -ItemType Directory -Path $toolDir | Out-Null }
    $modelDir = Join-Path (Get-Location) 'models'
    if (-not (Test-Path $modelDir)) { New-Item -ItemType Directory -Path $modelDir | Out-Null }

    Write-Host '[3/8] uv (ポータブル版) を準備中...' -ForegroundColor Cyan
    $uvDir = Join-Path $toolDir 'uv'
    $uvExe = Join-Path $uvDir 'uv.exe'
    if (-not (Test-Path $uvExe)) {
        if (-not (Test-Path $uvDir)) { New-Item -ItemType Directory -Path $uvDir | Out-Null }
        $uvZipUrl = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
        $uvZipFile = Join-Path $toolDir 'uv.zip'
        Download-Fast $uvZipUrl $uvZipFile
        Expand-Archive -Path $uvZipFile -DestinationPath $uvDir -Force
        Remove-Item $uvZipFile
        Write-Host '  -> 完了 (アーカイブを削除しました)'
    } else {
        Write-Host '  -> 既に存在するためスキップします。' -ForegroundColor Yellow
    }

    Write-Host '[4/8] 仮想環境を構築・更新中...' -ForegroundColor Cyan
    if (-not (Test-Path '.venv')) {
        & $uvExe venv --python 3
    }
    # requirements.txt の変更（numpyの追加など）を反映させるため、常に pip install を実行
    # (uv は既にインストール済みの場合は一瞬で終わります)
    & $uvExe pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw "依存ライブラリのインストールに失敗しました。" }

    Write-Host '[5/8] 外部ツールをダウンロード中...' -ForegroundColor Cyan
    
    # FFmpeg
    $existingFfmpeg = Get-ChildItem -Path $toolDir -Filter 'ffmpeg.exe' -Recurse | Select-Object -First 1
    if (-not $existingFfmpeg) {
        $ffmpegUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip'
        $ffmpegZip = Join-Path $toolDir 'ffmpeg.zip'
        Download-Fast $ffmpegUrl $ffmpegZip
        Write-Host '  -> 展開中...'
        Expand-Archive -Path $ffmpegZip -DestinationPath $toolDir -Force
        Remove-Item $ffmpegZip
        Write-Host '  -> 完了 (アーカイブを削除しました)'
    } else {
        Write-Host '  -> FFmpeg は既に存在するためスキップします。' -ForegroundColor Yellow
    }

    # VOICEVOX Editor (DirectML / GPU & CPU version)
    $vvTargetDir = Join-Path $toolDir 'voicevox'
    if (-not (Test-Path (Join-Path $vvTargetDir 'run.exe'))) {
        $vvUrl = 'https://github.com/VOICEVOX/voicevox/releases/download/0.25.1/voicevox-windows-directml-0.25.1.zip'
        $vvZip = Join-Path $toolDir 'voicevox.zip'
        Download-Fast $vvUrl $vvZip
        Write-Host '  -> 展開中 (数分かかります)...'
        Expand-Archive -Path $vvZip -DestinationPath $toolDir -Force
        Remove-Item $vvZip
        $extractedVv = Get-ChildItem -Path $toolDir -Directory -Filter "voicevox-windows-directml*" | Select-Object -First 1
        if ($extractedVv) {
            Move-Item -Path $extractedVv.FullName -Destination $vvTargetDir -Force
        }
        Write-Host '  -> 完了 (アーカイブを削除しました)'
    } else {
        Write-Host '  -> VOICEVOX は既に存在するためスキップします。' -ForegroundColor Yellow
    }

    Write-Host '[6/8] 各種モデルをダウンロード中...' -ForegroundColor Cyan
    # Models
    $whisperFile = Join-Path $modelDir 'ggml-large-v3-turbo.bin'
    if (-not (Test-Path $whisperFile)) {
        $whisperUrl = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin'
        Download-Fast $whisperUrl $whisperFile
    } else {
        Write-Host '  -> Whisper モデルは既に存在するためスキップします。' -ForegroundColor Yellow
    }

    $vadFile = Join-Path $modelDir 'ggml-silero-v6.2.0.bin'
    if (-not (Test-Path $vadFile)) {
        $vadUrl = 'https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin'
        Download-Fast $vadUrl $vadFile
    } else {
        Write-Host '  -> VAD モデルは既に存在するためスキップします。' -ForegroundColor Yellow
    }

    Write-Host '[7/8] 設定ファイルを作成中...' -ForegroundColor Cyan
    $configFolder = Join-Path (Get-Location) 'data'
    if (-not (Test-Path $configFolder)) { New-Item -ItemType Directory -Path $configFolder | Out-Null }
    $configPath = Join-Path $configFolder 'config.json'

    if (-not (Test-Path $configPath)) {
        $ffmpegBinArray = Get-ChildItem -Path $toolDir -Filter 'ffmpeg.exe' -Recurse 
        $ffmpegBin = ($ffmpegBinArray | Select-Object -First 1).FullName
        
        $configObject = @{
            ffmpeg = @{
                ffmpeg_path = $ffmpegBin.Replace('\', '/')
                model_path = $whisperFile.Replace('\', '/')
                vad_model_path = $vadFile.Replace('\', '/')
            }
            system = @{
                output_dir = (Join-Path (Get-Location) 'output').Replace('\', '/')
            }
        }
        $configJson = $configObject | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($configPath, $configJson, $Utf8NoBom)
        Write-Host '  -> config.json を作成しました。'
    } else {
        Write-Host '  -> config.json は既に存在します。' -ForegroundColor Yellow
    }
    
    if (-not (Test-Path 'output')) { New-Item -ItemType Directory -Path 'output' | Out-Null }

    Write-Host '[8/8] 起動用バッチを更新中...' -ForegroundColor Cyan
    $runBatPath = 'run.bat'
    $runBatContent = "@echo off`r`nchcp 65001 >nul`r`necho [Run] Starting application...`r`ntools\uv\uv.exe run voicevox_controller.py 2>&1`r`nif %errorlevel% neq 0 (`r`n  echo.`r`n  echo [ERROR] Application exited with code %errorlevel%`r`n)`r`npause"
    [System.IO.File]::WriteAllText($runBatPath, $runBatContent, $Utf8NoBom)

    Write-Host '------------------------------------------------------' -ForegroundColor Green
    Write-Host 'セットアップの更新が完了しました！' -ForegroundColor Green
    Write-Host 'run.bat を起動して確認してください。'
    Write-Host '------------------------------------------------------'
    Write-Host 'Press any key to exit...'
    [void][System.Console]::ReadKey($true)

} catch {
    Write-Host "`n[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
