[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$auditScript = Join-Path $projectRoot "Content\Python\AuditAetherSplineRemeshModifierAPI_UE58.py"
$auditReport = Join-Path $projectRoot "Saved\AetherSplineRemeshModifierAPIAudit.txt"
$installScript = Join-Path $projectRoot "Content\Python\InstallAetherVideoSplineRemeshStage_UE58.py"
$installReport = Join-Path $projectRoot "Saved\AetherVideoSplineRemeshInstall.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before installing Stage 10."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $auditScript)) {
    throw "Spline Remesh API audit script was not found: $auditScript"
}
if (!(Test-Path -LiteralPath $installScript)) {
    throw "Stage 10 Spline Remesh installer script was not found: $installScript"
}

Remove-Item -LiteralPath $auditReport -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installReport -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Preflighting UE 5.8 Spline Remesh API and the saved Stage 09 spline..."
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
    throw "The Stage 10 preflight finished with exit code $($auditProcess.ExitCode), but no audit report was created."
}

$auditText = Get-Content -LiteralPath $auditReport -Raw
Get-Content -LiteralPath $auditReport
Write-Host ""

if ($auditText -notmatch "AETHER_SPLINE_REMESH_API=PASS") {
    throw "Stage 10 preflight did not pass. Paste the complete audit report shown above."
}

Write-Host "Installing Stage 10: local Spline Remesh along the Stage 09 channel..."
Write-Host "Radius: 60 m. Target edge length: 2.5 m. Priority: 35, before Stage 09."
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
    throw "The Stage 10 installer finished with exit code $($installProcess.ExitCode), but no install report was created."
}

Write-Host ""
Get-Content -LiteralPath $installReport
Write-Host ""

$installText = Get-Content -LiteralPath $installReport -Raw
if ($installText -notmatch "INSTALL_RESULT=PASS") {
    throw "Stage 10 Spline Remesh did not install successfully. Paste the complete report shown above."
}

Write-Host "Stage 10 Spline Remesh installed and AetherWorld saved." -ForegroundColor Green
Write-Host "Open AetherWorld, select Aether_VideoStage10_SplineRemesh, include it in Build To, and compare the channel banks with Stage 10 disabled/enabled."
