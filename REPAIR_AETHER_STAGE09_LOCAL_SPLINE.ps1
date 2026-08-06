[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$script = Join-Path $projectRoot "Content\Python\RepairAetherStage09LocalSpline_UE58.py"
$report = Join-Path $projectRoot "Saved\AetherStage09LocalSplineRepair.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before repairing Stage 09."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $script)) {
    throw "Stage 09 spline repair script was not found: $script"
}

Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Repairing Stage 09 spline into local coordinate space..."
Write-Host "This resets the five-point channel around the actor's current pivot and refreshes Stage 10."
Write-Host "Safety: this saves AetherWorld but does NOT start the compiled Mesh Partition build."
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
    throw "The repair finished with exit code $($process.ExitCode), but no report was created."
}

Write-Host ""
Get-Content -LiteralPath $report
Write-Host ""

$reportText = Get-Content -LiteralPath $report -Raw
if ($reportText -notmatch "REPAIR_RESULT=PASS") {
    throw "Stage 09 local-space repair did not pass. Paste the complete report shown above."
}

Write-Host "Stage 09 spline repaired and Stage 10 reference refreshed." -ForegroundColor Green
Write-Host "Open AetherWorld, confirm the repaired spline is local-sized, then test Stage 10 with Build To."
