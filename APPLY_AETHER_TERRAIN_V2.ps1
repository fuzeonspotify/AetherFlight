[CmdletBinding()]
param(
    [switch]$NoLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\UpgradeAetherMeshTerrainMaterialV2_UE58.py"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Aether Terrain V2 script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before applying Aether Terrain V2."
}

Write-Host ""
Write-Host "Aether Terrain V2 is ready."
Write-Host "Project: $project"
Write-Host "Script:  $pythonScript"
Write-Host ""
Write-Host "This creates a new Aether-owned material and preserves M_MeshTerrain_Aether as rollback."
Write-Host "No Sensei master material, displacement, tessellation, or World Position Offset is assigned."

if ($NoLaunch) {
    Write-Host ""
    Write-Host "Launch skipped. Run UpgradeAetherMeshTerrainMaterialV2_UE58.py from Unreal's Output Log."
    exit 0
}

$editorCandidates = @(
    "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe",
    "C:\Program Files\Epic Games\UE_5.8EA\Engine\Binaries\Win64\UnrealEditor.exe"
)
$editor = $editorCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (!$editor) {
    throw "UnrealEditor.exe for UE 5.8 was not found."
}

$arguments = @(
    ('"{0}"' -f $project),
    "-nosound",
    ('-ExecutePythonScript="{0}"' -f $pythonScript)
)

Write-Host ""
Write-Host "Launching Unreal Engine 5.8 and applying Aether Terrain V2..."
Start-Process -FilePath $editor -ArgumentList $arguments
