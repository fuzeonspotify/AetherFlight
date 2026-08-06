[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$repairScript = Join-Path $projectRoot "Content\Python\RepairAetherVideoRiverEnvironmentGrounding_UE58.py"
$repairReport = Join-Path $projectRoot "Saved\AetherRiverEnvironmentGroundingRepair.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before repairing Stage 13 grounding."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $repairScript)) {
    throw "Stage 13 grounding repair script was not found: $repairScript"
}

Remove-Item -LiteralPath $repairReport -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Repairing Stage 13 riverbank environment grounding..."
Write-Host "The repair replaces only Aether_VideoStage13_RiverEnvironment."
Write-Host "Stage 13 exclusion and all Stage 09-12 terrain/water actors are preserved."
Write-Host "The same deterministic 184-instance layout is retained."
Write-Host "Inner-bank fallback height is reduced and rocks are partially embedded."
Write-Host "No compiled Mesh Partition build will be started."
Write-Host ""

$repairProcess = Start-Process `
    -FilePath $editor `
    -ArgumentList @(
        ('"{0}"' -f $project),
        "/Game/Maps/AetherWorld",
        "-nosound",
        "-unattended",
        ('-ExecutePythonScript="{0}"' -f $repairScript)
    ) `
    -PassThru `
    -Wait

if (!(Test-Path -LiteralPath $repairReport)) {
    throw "The Stage 13 grounding repair finished with exit code $($repairProcess.ExitCode), but no report was created."
}

Write-Host ""
Get-Content -LiteralPath $repairReport
Write-Host ""

$repairText = Get-Content -LiteralPath $repairReport -Raw
if ($repairText -notmatch "REPAIR_RESULT=PASS") {
    throw "Stage 13 river environment grounding repair did not pass. Paste the complete report shown above."
}

Write-Host "Stage 13 river environment grounding repair completed and AetherWorld was saved." -ForegroundColor Green
Write-Host "Open AetherWorld and inspect both banks from a low angle before committing the repaired external actor."
