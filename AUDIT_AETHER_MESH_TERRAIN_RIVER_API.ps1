[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$script = Join-Path $projectRoot "Content\Python\AuditAetherMeshTerrainRiverAPI_UE58.py"
$report = Join-Path $projectRoot "Saved\AetherMeshTerrainRiverAPIAudit.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before auditing Stage 11."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $script)) {
    throw "Stage 11 river API audit script was not found: $script"
}

Remove-Item -LiteralPath $report -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Auditing the UE 5.8 Water and MeshPartitionWater APIs..."
Write-Host "Read-only: this does not spawn actors, save packages, or start a Mesh Partition build."
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
    throw "The Stage 11 API audit finished with exit code $($process.ExitCode), but no report was created."
}

Write-Host ""
Get-Content -LiteralPath $report
Write-Host ""

$reportText = Get-Content -LiteralPath $report -Raw
if ($reportText -notmatch "AETHER_MESH_TERRAIN_RIVER_API=PASS") {
    throw "Stage 11 river API audit did not pass. Paste the complete report shown above."
}

Write-Host "Stage 11 river API audit passed." -ForegroundColor Green
