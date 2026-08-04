[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$script = Join-Path $projectRoot "Content\Python\InstallAetherVideoSculptPaintStage_UE58.py"
$report = Join-Path $projectRoot "Saved\AetherVideoSculptPaintInstall.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before installing the Sculpt/Paint stage."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $script)) {
    throw "Sculpt/Paint installer script was not found: $script"
}

Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Installing the next full-video Mesh Terrain feature: Sculpt and Paint..."
Write-Host "Creates a real BrushModifier inside the verified local Remesh zone."
Write-Host "Safety: this does NOT start the compiled Mesh Partition build."
Write-Host ""

$process = Start-Process `
    -FilePath $editor `
    -ArgumentList @(
        ('"{0}"' -f $project),
        "/Game/Maps/AetherWorld",
        "-nosound",
        "-unattended",
        ('-ExecutePythonScript="{0}"' -f $script)
    ) `
    -PassThru `
    -Wait

if (!(Test-Path -LiteralPath $report)) {
    throw "The installer finished with exit code $($process.ExitCode), but no report was created."
}

Write-Host ""
Get-Content -LiteralPath $report
Write-Host ""

$reportText = Get-Content -LiteralPath $report -Raw
if ($reportText -notmatch "INSTALL_RESULT=PASS") {
    throw "The Sculpt/Paint stage did not install successfully. Paste the report shown above."
}

Write-Host "Sculpt/Paint tutorial stage installed and AetherWorld saved." -ForegroundColor Green
Write-Host "Open AetherWorld and select: Aether_VideoStage06_SculptPaint"
