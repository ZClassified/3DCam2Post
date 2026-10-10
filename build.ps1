# Builds a single-file Windows executable with ffmpeg bundled and collects the release files.
#
#   .\build.ps1                      # uses ffmpeg.exe from PATH
#   .\build.ps1 -Ffmpeg C:\path\to\ffmpeg.exe
#   .\build.ps1 -SkipBuild           # only (re)create the release files for an existing exe
#
# Output in dist\ (upload these three files to the GitHub release):
#   3DCam2Post.exe
#   3DCam2Post-<version>-licenses.zip   license texts + third-party notices
#   ffmpeg-<version>.tar.xz             FFmpeg source of the bundled version (required by the GPL)

param(
    [string]$Ffmpeg = "",
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
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

if (-not $SkipBuild) {
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
    Remove-Item -Recurse -Force build, 3DCam2Post.spec -ErrorAction SilentlyContinue
}
if (-not (Test-Path dist\3DCam2Post.exe)) { throw "dist\3DCam2Post.exe missing - run without -SkipBuild" }

# License files
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
$zip = "dist\3DCam2Post-$version-licenses.zip"
Get-ChildItem dist -Filter "3DCam2Post-*-licenses.zip" | Remove-Item -Force
Compress-Archive -Path "$lic\*" -DestinationPath $zip

# FFmpeg source of the bundled release version
$tar = $null
if ($ffVersion -match 'ffmpeg version (\d+(\.\d+)+)') {
    $ffNum = $Matches[1]
    $tar = "dist\ffmpeg-$ffNum.tar.xz"
    if (-not (Test-Path $tar)) {
        Write-Host "Downloading FFmpeg $ffNum source..."
        Invoke-WebRequest "https://ffmpeg.org/releases/ffmpeg-$ffNum.tar.xz" -OutFile $tar
    }
} else {
    Write-Warning "Not an FFmpeg release build ($ffVersion) - add the matching source archive manually."
}

Write-Host ""
Write-Host "Upload to the GitHub release:"
Get-Item dist\3DCam2Post.exe, $zip, $tar -ErrorAction SilentlyContinue |
    ForEach-Object { Write-Host ("  {0,-36} {1,8:N1} MB" -f $_.Name, ($_.Length / 1MB)) }
