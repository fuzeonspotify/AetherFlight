[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$script = Join-Path $projectRoot "Content\Python\AuditAetherMeshTerrainVideoProgress_UE58.py"
$report = Join-Path $projectRoot "Saved\AetherMeshTerrainVideoProgress.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before running the full-video progress audit."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $script)) {
    throw "Mesh Terrain video-progress audit script was not found: $script"
}

Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Comparing AetherWorld against the complete Unreal Sensei Mesh Terrain workflow..."
Write-Host "Checks the authoritative terrain, MPD, material/weight assets, and every modifier stage."
Write-Host "This audit is read-only."
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
    throw "The audit finished with exit code $($process.ExitCode), but no report was created."
}

Write-Host ""
Get-Content -LiteralPath $report
Write-Host ""
Write-Host "Report saved to: $report" -ForegroundColor Green
