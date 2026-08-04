[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$auditScript = Join-Path $projectRoot "Content\Python\AuditAetherRiverEnvironmentAPI_UE58_v2.py"
$auditReport = Join-Path $projectRoot "Saved\AetherRiverEnvironmentAPIAudit.txt"
$installScript = Join-Path $projectRoot "Content\Python\InstallAetherVideoRiverEnvironmentStage_UE58_v2.py"
$installReport = Join-Path $projectRoot "Saved\AetherVideoRiverEnvironmentInstall.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before installing Stage 13."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $auditScript)) {
    throw "Stage 13 river environment API audit script was not found: $auditScript"
}
if (!(Test-Path -LiteralPath $installScript)) {
    throw "Stage 13 river environment installer script was not found: $installScript"
}

Remove-Item -LiteralPath $auditReport -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installReport -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Preflighting Stage 13 FoliageExclusion, HISM placement, and river environment assets..."
Write-Host ""

$auditProcess = Start-Process `
    -FilePath $editor `
    -ArgumentList @(
        ('"{0}"' -f $project),
        "/Game/Maps/AetherWorld",
        "-nosound",
        "-unattended",
        ('-ExecutePythonScript="{0}"' -f $auditScript)
    ) `
    -PassThru `
    -Wait

if (!(Test-Path -LiteralPath $auditReport)) {
    throw "The Stage 13 preflight finished with exit code $($auditProcess.ExitCode), but no audit report was created."
}

$auditText = Get-Content -LiteralPath $auditReport -Raw
Get-Content -LiteralPath $auditReport
Write-Host ""

if ($auditText -notmatch "AETHER_RIVER_ENVIRONMENT_API=PASS") {
    throw "Stage 13 river environment preflight did not pass. Paste the complete audit report shown above."
}

Write-Host "Installing Stage 13: FoliageExclusion corridor plus deterministic local riverbank environment..."
Write-Host "Exclusion channel: Weights only, priority 56, 14 m full corridor, 24 m falloff."
Write-Host "Environment: local HISM rocks, shrubs, and ground cover placed outside the water corridor."
Write-Host "Safety: environment collision stays disabled until Stage 14 runtime validation."
Write-Host "Safety: this saves AetherWorld but does NOT start the compiled Mesh Partition build."
Write-Host ""

$installProcess = Start-Process `
    -FilePath $editor `
    -ArgumentList @(
        ('"{0}"' -f $project),
        "/Game/Maps/AetherWorld",
        "-nosound",
        "-unattended",
        ('-ExecutePythonScript="{0}"' -f $installScript)
    ) `
    -PassThru `
    -Wait

if (!(Test-Path -LiteralPath $installReport)) {
    throw "The Stage 13 installer finished with exit code $($installProcess.ExitCode), but no install report was created."
}

Write-Host ""
Get-Content -LiteralPath $installReport
Write-Host ""

$installText = Get-Content -LiteralPath $installReport -Raw
if ($installText -notmatch "INSTALL_RESULT=PASS") {
    throw "Stage 13 river environment did not install successfully. Paste the complete report shown above."
}

Write-Host "Stage 13 river environment installed and AetherWorld saved." -ForegroundColor Green
Write-Host "Open AetherWorld, refresh the Stage13 exclusion spline if needed, Build To through priority 56, then inspect the riverbank HISM actor."
