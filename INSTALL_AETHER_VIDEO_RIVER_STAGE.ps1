[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$auditScript = Join-Path $projectRoot "Content\Python\AuditAetherMeshTerrainRiverAPI_UE58_v2.py"
$auditReport = Join-Path $projectRoot "Saved\AetherMeshTerrainRiverAPIAudit.txt"
$installScript = Join-Path $projectRoot "Content\Python\InstallAetherVideoRiverStage_UE58_v2.py"
$installReport = Join-Path $projectRoot "Saved\AetherVideoRiverInstall.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before installing Stage 11."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $auditScript)) {
    throw "Stage 11 river API audit script was not found: $auditScript"
}
if (!(Test-Path -LiteralPath $installScript)) {
    throw "Stage 11 river installer script was not found: $installScript"
}

Remove-Item -LiteralPath $auditReport -Force -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $installReport -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Preflighting UE 5.8 Water, WaterZone, and Mesh Terrain RiverModifier APIs..."
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
    throw "The Stage 11 preflight finished with exit code $($auditProcess.ExitCode), but no audit report was created."
}

$auditText = Get-Content -LiteralPath $auditReport -Raw
Get-Content -LiteralPath $auditReport
Write-Host ""

if ($auditText -notmatch "AETHER_MESH_TERRAIN_RIVER_API=PASS") {
    throw "Stage 11 preflight did not pass. Paste the complete audit report shown above."
}

Write-Host "Installing Stage 11: local WaterBodyRiver and WaterZone along the repaired Stage 09 channel..."
Write-Host "River: requested 20 m total width, engine-default depth metadata, 3 m above the Stage 09 channel."
Write-Host "RiverModifier priority: 50, after Stage 09. Water Zone extent: 1.6 km."
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
    throw "The Stage 11 installer finished with exit code $($installProcess.ExitCode), but no install report was created."
}

Write-Host ""
Get-Content -LiteralPath $installReport
Write-Host ""

$installText = Get-Content -LiteralPath $installReport -Raw
if ($installText -notmatch "INSTALL_RESULT=PASS") {
    throw "Stage 11 river did not install successfully. Paste the complete report shown above."
}

Write-Host "Stage 11 local river installed and AetherWorld saved." -ForegroundColor Green
Write-Host "Open AetherWorld, select Aether_VideoStage11_River, Build To through its RiverModifier, and verify the water mesh."
