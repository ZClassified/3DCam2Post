# Builds a single-file Windows executable with ffmpeg bundled.
#
#   .\build.ps1                      # uses ffmpeg.exe from PATH
#   .\build.ps1 -Ffmpeg C:\path\to\ffmpeg.exe
#
# Output: dist\3DCam2Post.exe plus dist\licenses\ (attach both to the release,
# together with the FFmpeg source archive of the bundled version).

param(
    [string]$Ffmpeg = ""
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

if (-not $Ffmpeg) {
    $cmd = Get-Command ffmpeg.exe -ErrorAction SilentlyContinue
    if (-not $cmd) { throw "ffmpeg.exe not found in PATH. Pass -Ffmpeg <path>." }
    $Ffmpeg = $cmd.Source
}
$Ffmpeg = (Resolve-Path $Ffmpeg).Path

$version = (Select-String -Path ui\main_window.py -Pattern 'APP_VERSION = "([^"]+)"').Matches[0].Groups[1].Value
$ffVersion = (& $Ffmpeg -hide_banner -version | Select-Object -First 1)
Write-Host "3DCam2Post $version"
Write-Host "Bundling: $ffVersion"

# flet/PyInstaller log to stderr; Windows PowerShell would treat that as an error, so only the exit code counts
$ErrorActionPreference = "Continue"
flet pack main.py `
    --name 3DCam2Post `
    --icon assets\icon.ico `
    --add-data "assets;assets" `
    --add-binary "$Ffmpeg;." `
    --product-name 3DCam2Post `
    --product-version $version `
    --file-version $version `
    -y 2>&1 | ForEach-Object { "$_" }
$code = $LASTEXITCODE
$ErrorActionPreference = "Stop"
if ($code -ne 0) { throw "flet pack failed ($code)" }

# License files for the release
$lic = "dist\licenses"
New-Item -ItemType Directory -Force $lic | Out-Null
Copy-Item LICENSE "$lic\3DCam2Post-LICENSE.txt"
Copy-Item THIRD_PARTY_NOTICES.md $lic
$ffLicense = Join-Path (Split-Path (Split-Path $Ffmpeg)) "LICENSE"
if (Test-Path $ffLicense) {
    Copy-Item $ffLicense "$lic\FFmpeg-LICENSE.txt"
} else {
    Write-Warning "FFmpeg LICENSE not found next to the build - add it to $lic manually."
}
Set-Content "$lic\FFmpeg-VERSION.txt" $ffVersion -Encoding utf8

Write-Host ""
Write-Host "Done: dist\3DCam2Post.exe"
Write-Host "Attach to the release: the exe, dist\licenses\ and the FFmpeg source archive for: $ffVersion"
