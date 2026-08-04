[CmdletBinding()]
param(
    [switch]$NoLaunch
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\UpgradeAetherTerrainSurfaceDetail_UE58.py"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Aether surface-detail script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before applying the surface-detail update."
}

Write-Host ""
Write-Host "Aether surface-detail update is ready."
Write-Host "Project: $project"
Write-Host "Script:  $pythonScript"
Write-Host ""
Write-Host "The updater detects the material currently assigned to MPD_AetherWorld."
Write-Host "It refreshes normal parameters on a material instance, or duplicates an editable Aether material before adding normals."
Write-Host "It does not alter terrain geometry, collision, Mesh Partition resolution, displacement, or World Position Offset."

if ($NoLaunch) {
    Write-Host ""
    Write-Host "Unreal launch skipped."
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
Write-Host "Launching Unreal Engine 5.8 and applying the safe surface-detail update..."
Start-Process -FilePath $editor -ArgumentList $arguments
