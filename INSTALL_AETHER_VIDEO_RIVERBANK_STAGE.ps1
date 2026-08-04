[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$auditScript = Join-Path $projectRoot "Content\Python\AuditAetherRiverbankWeightAPI_UE58.py"
$auditReport = Join-Path $projectRoot "Saved\AetherRiverbankWeightAPIAudit.txt"
$installScript = Join-Path $projectRoot "Content\Python\InstallAetherVideoRiverbankStage_UE58.py"
$installReport = Join-Path $projectRoot "Saved\AetherVideoRiverbankInstall.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before installing Stage 12."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $auditScript)) {
    throw "Stage 12 riverbank API audit script was not found: $auditScript"
}
if (!(Test-Path -LiteralPath $installScript)) {
    throw "Stage 12 riverbank installer script was not found: $installScript"
}

Remove-Item -LiteralPath $auditReport -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installReport -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Preflighting UE 5.8 SplineModifier weight-channel support and the saved river dependencies..."
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
    throw "The Stage 12 preflight finished with exit code $($auditProcess.ExitCode), but no audit report was created."
}

$auditText = Get-Content -LiteralPath $auditReport -Raw
Get-Content -LiteralPath $auditReport
Write-Host ""

if ($auditText -notmatch "AETHER_RIVERBANK_WEIGHT_API=PASS") {
    throw "Stage 12 riverbank preflight did not pass. Paste the complete audit report shown above."
}

Write-Host "Installing Stage 12: weight-only Wetland spline along the verified local river..."
Write-Host "Wetland channel: full influence 14 m from center, 32 m outer falloff, priority 55."
Write-Host "Safety: write mode is Weights only. Terrain positions and water actors are not changed."
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
    throw "The Stage 12 installer finished with exit code $($installProcess.ExitCode), but no install report was created."
}

Write-Host ""
Get-Content -LiteralPath $installReport
Write-Host ""

$installText = Get-Content -LiteralPath $installReport -Raw
if ($installText -notmatch "INSTALL_RESULT=PASS") {
    throw "Stage 12 riverbank wetland modifier did not install successfully. Paste the complete report shown above."
}

Write-Host "Stage 12 riverbank wetland modifier installed and AetherWorld saved." -ForegroundColor Green
Write-Host "Open AetherWorld, Build To through Aether_VideoStage12_RiverbankWetland at priority 55, then compare it disabled/enabled."
