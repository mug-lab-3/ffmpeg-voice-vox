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
set "SELF_PATH=%~f0"
powershell -NoProfile -ExecutionPolicy Bypass -Command "$m='###_POWERSHELL' + '_START_###'; $c=Get-Content -LiteralPath $env:SELF_PATH -Raw -Encoding UTF8; $i=$c.IndexOf($m); if($i -ge 0){iex ($c.Substring($i+$m.Length))}"

if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Setup failed with error level %errorlevel%
    pause
)
exit /b %errorlevel%

###_POWERSHELL_START_###
# --- PowerShell Script Section ---

# uv のリンクモードをコピーに強制（クラウド同期フォルダ/OneDrive対策）
$env:UV_LINK_MODE = 'copy'
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
$zipFile = Join-Path (Get-Location) 'repo.zip'
$extractDir = 'ffmpeg-voice-vox-main'
$finalDir = (Get-Location).Path

try {
    Write-Host '[1/8] GitHub からリポジトリを取得中...' -ForegroundColor Cyan
    if (-not (Test-Path -LiteralPath (Join-Path $finalDir 'voicevox_controller.py'))) {
        Download-Fast $repoUrl $zipFile
        Write-Host '  -> 展開中...'
        Expand-Archive -Path $zipFile -DestinationPath '..' -Force
        Remove-Item -LiteralPath $zipFile -ErrorAction SilentlyContinue
        Get-ChildItem -Path "../$extractDir/*" | ForEach-Object {
            Copy-Item -Path $_.FullName -Destination $finalDir -Recurse -Force
        }
        Remove-Item "../$extractDir" -Recurse -Force
        Write-Host '  -> 完了'
    } else {
        Write-Host '  -> 既にあるリポジトリを使用します。' -ForegroundColor Yellow
    }

    Write-Host '[2/8] ツール用ディレクトリを準備中...' -ForegroundColor Cyan
    $toolDir = Join-Path $finalDir 'tools'
    if (-not (Test-Path -LiteralPath $toolDir)) { New-Item -ItemType Directory -Path $toolDir | Out-Null }
    $modelDir = Join-Path $finalDir 'models'
    if (-not (Test-Path -LiteralPath $modelDir)) { New-Item -ItemType Directory -Path $modelDir | Out-Null }

    Write-Host '[3/8] uv (ポータブル版) を準備中...' -ForegroundColor Cyan
    $uvDir = Join-Path $toolDir 'uv'
    $uvExe = Join-Path $uvDir 'uv.exe'
    if (-not (Test-Path -LiteralPath $uvExe)) {
        if (-not (Test-Path -LiteralPath $uvDir)) { New-Item -ItemType Directory -Path $uvDir | Out-Null }
        $uvZipUrl = 'https://github.com/astral-sh/uv/releases/latest/download/uv-x86_64-pc-windows-msvc.zip'
        $uvZipFile = Join-Path $toolDir 'uv.zip'
        Download-Fast $uvZipUrl $uvZipFile
        Expand-Archive -Path $uvZipFile -DestinationPath $uvDir -Force
        Remove-Item -LiteralPath $uvZipFile -ErrorAction SilentlyContinue
        Write-Host '  -> 完了'
    } else {
        Write-Host '  -> 既に存在するためスキップします。' -ForegroundColor Yellow
    }

    Write-Host '[4/8] 実行環境を構築・更新中 (uv sync)...' -ForegroundColor Cyan
    # uv sync を使用することで、システムPythonに依存せず、.python-version に基づく
    # 正しいバージョンの Python が自動的にダウンロード・使用されます。
    & "$uvExe" sync --link-mode=copy
    if ($LASTEXITCODE -ne 0) { throw "実行環境の構築（uv sync）に失敗しました。" }

    Write-Host '[5/8] 外部ツールをダウンロード中...' -ForegroundColor Cyan
    
    # FFmpeg (Gyan.dev git-full .7z ビルド)
    $existingFfmpeg = Get-ChildItem -Path $toolDir -Filter 'ffmpeg.exe' -Recurse | Select-Object -First 1
    
    $isWhisperSupported = $false
    if ($existingFfmpeg) {
        $filters = & $existingFfmpeg.FullName -filters 2>&1
        if ($filters -like "*whisper*") { $isWhisperSupported = $true }
    }

    if (-not $isWhisperSupported) {
        Write-Host '  -> Whisper 対応版 FFmpeg を取得中 (Gyan.dev git-full .7z)...'
        $ffmpegUrl = 'https://www.gyan.dev/ffmpeg/builds/ffmpeg-git-full.7z'
        $ffmpeg7z = Join-Path $toolDir 'ffmpeg.7z'
        
        if ($existingFfmpeg) {
            Write-Host '  -> 非対応の FFmpeg を入れ替えます...'
            $oldDir = $existingFfmpeg.Directory
            while ($oldDir -and $oldDir.FullName -ne $toolDir) {
                $targetToRemove = $oldDir
                $oldDir = $oldDir.Parent
            }
            if ($targetToRemove) { Remove-Item -Path $targetToRemove.FullName -Recurse -Force -ErrorAction SilentlyContinue }
        }

        Download-Fast $ffmpegUrl $ffmpeg7z
        Write-Host '  -> 展開中...'
        # Windows 11/10 (1803以降) 標準の tar.exe を使用
        # 7z ファイルのサポートは最近の Windows 11 で追加されました 
        & tar.exe -xf $ffmpeg7z -C $toolDir
        Remove-Item -LiteralPath $ffmpeg7z -Force -ErrorAction SilentlyContinue
        # docs/setup.md の推奨構成 (tools/ffmpeg) に合わせるためリネーム
        $ffmpegTargetDir = Join-Path $toolDir 'ffmpeg'
        # ffmpeg-* に一致するディレクトリを探す
        $extractedFfmpegDir = Get-ChildItem -Path $toolDir -Directory -Filter "ffmpeg-*" | Select-Object -First 1
        if ($extractedFfmpegDir) {
            Write-Host "  -> ディレクトリを整理中: $($extractedFfmpegDir.Name) -> ffmpeg"
            if (Test-Path -LiteralPath $ffmpegTargetDir) { Remove-Item -Path $ffmpegTargetDir -Recurse -Force }
            Move-Item -Path $extractedFfmpegDir.FullName -Destination $ffmpegTargetDir -Force
            # リネーム後のパスで既存チェック変数を更新
            $existingFfmpeg = Get-ChildItem -Path $ffmpegTargetDir -Filter 'ffmpeg.exe' -Recurse | Select-Object -First 1
        }
        Write-Host '  -> 完了'
    } else {
        Write-Host "  -> Whisper 対応版 FFmpeg が既に存在します: $($existingFfmpeg.FullName)" -ForegroundColor Yellow
    }

    # VOICEVOX Editor
    $vvTargetDir = Join-Path $toolDir 'voicevox'
    if (-not (Test-Path -LiteralPath (Join-Path $vvTargetDir 'run.exe'))) {
        $vvUrl = 'https://github.com/VOICEVOX/voicevox/releases/download/0.25.1/voicevox-windows-directml-0.25.1.zip'
        $vvZip = Join-Path $toolDir 'voicevox.zip'
        Download-Fast $vvUrl $vvZip
        Write-Host '  -> 展開中 (これには数分かかります)...'
        Expand-Archive -Path $vvZip -DestinationPath $toolDir -Force
        Remove-Item -LiteralPath $vvZip -ErrorAction SilentlyContinue
        $extractedVv = Get-ChildItem -Path $toolDir -Directory -Filter "voicevox-windows-directml*" | Select-Object -First 1
        if ($extractedVv) {
            Move-Item -Path $extractedVv.FullName -Destination $vvTargetDir -Force
        }
        Write-Host '  -> 完了'
    } else {
        Write-Host '  -> VOICEVOX は既にあるためスキップします。' -ForegroundColor Yellow
    }

    Write-Host '[6/8] 各種モデルをダウンロード中...' -ForegroundColor Cyan
    # Models
    $whisperFile = Join-Path $modelDir 'ggml-large-v3-turbo.bin'
    if (-not (Test-Path -LiteralPath $whisperFile)) {
        $whisperUrl = 'https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-large-v3-turbo.bin'
        Download-Fast $whisperUrl $whisperFile
    } else {
        Write-Host '  -> Whisper モデルは既にあるためスキップします。' -ForegroundColor Yellow
    }

    $vadFile = Join-Path $modelDir 'ggml-silero-v6.2.0.bin'
    if (-not (Test-Path -LiteralPath $vadFile)) {
        $vadUrl = 'https://huggingface.co/ggml-org/whisper-vad/resolve/main/ggml-silero-v6.2.0.bin'
        Download-Fast $vadUrl $vadFile
    } else {
        Write-Host '  -> VAD モデルは既にあるためスキップします。' -ForegroundColor Yellow
    }

    Write-Host '[7/8] 設定ファイルを作成中...' -ForegroundColor Cyan
    $configFolder = Join-Path $finalDir 'data'
    if (-not (Test-Path -LiteralPath $configFolder)) { New-Item -ItemType Directory -Path $configFolder | Out-Null }
    $configPath = Join-Path $configFolder 'config.json'

    # ConvertTo-Json を通すとバックスラッシュは自動的にエスケープ (\ -> \\) されます。
    # これによりユーザーの要望通りの JSON 形式になります。
    $ffmpegPath = $existingFfmpeg.FullName
    $modelPath = $whisperFile
    $vadPath = $vadFile
    $outDir = (Join-Path $finalDir 'output')
    
    if (-not (Test-Path -LiteralPath $configPath)) {
        $configObject = @{
            ffmpeg = @{
                ffmpeg_path = $ffmpegPath
                model_path = $modelPath
                vad_model_path = $vadPath
                host = "127.0.0.1"
                queue_length = 10
            }
            system = @{
                output_dir = $outDir
            }
        }
        $configJson = $configObject | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($configPath, $configJson, $Utf8NoBom)
        Write-Host '  -> config.json を作成しました (バックスラッシュをエスケープしました)。'
    } else {
        # 既存の設定があればパスだけ更新
        $currentJson = Get-Content $configPath -Raw | ConvertFrom-Json
        $currentJson.ffmpeg.ffmpeg_path = $ffmpegPath
        $currentJson.ffmpeg.model_path = $modelPath
        $currentJson.ffmpeg.vad_model_path = $vadPath
        $currentJson.system.output_dir = $outDir
        
        $newJson = $currentJson | ConvertTo-Json -Depth 10
        [System.IO.File]::WriteAllText($configPath, $newJson, $Utf8NoBom)
        Write-Host '  -> config.json のパスを更新・修正しました。'
    }
    
    if (-not (Test-Path -LiteralPath (Join-Path $finalDir 'output'))) { New-Item -ItemType Directory -Path (Join-Path $finalDir 'output') | Out-Null }

    Write-Host '[8/8] 起動用バッチを更新中...' -ForegroundColor Cyan
    $runBatPath = Join-Path $finalDir 'run.bat'
    $runBatContent = "@echo off`r`nchcp 65001 >nul`r`nset UV_LINK_MODE=copy`r`necho [Run] Starting application...`r`ntools\uv\uv.exe run voicevox_controller.py`r`nif %errorlevel% neq 0 (`r`n  echo.`r`n  echo [ERROR] Application exited with code %errorlevel%`r`n  pause`r`n)"
    [System.IO.File]::WriteAllText($runBatPath, $runBatContent, $Utf8NoBom)

    Write-Host '------------------------------------------------------' -ForegroundColor Green
    Write-Host 'セットアップの更新が完了しました！' -ForegroundColor Green
    Write-Host 'run.bat をダブルクリックして起動してください。'
    Write-Host '------------------------------------------------------'
    Write-Host 'Press any key to exit...'
    [void][System.Console]::ReadKey($true)

} catch {
    Write-Host "`n[ERROR] $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}
