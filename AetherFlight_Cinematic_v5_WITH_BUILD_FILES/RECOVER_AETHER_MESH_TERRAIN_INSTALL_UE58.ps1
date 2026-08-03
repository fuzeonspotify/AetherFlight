[CmdletBinding()]
param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [switch]$DoNotOpenEditor
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$UProject = Join-Path $ProjectRoot "AetherFlight.uproject"
$Generator = Join-Path $ProjectRoot "Tools\generate_production_landscape.py"
$InstallScript = Join-Path $ProjectRoot "Content\Python\InstallAetherMeshTerrainClean_UE58.py"
$InstallReport = Join-Path $ProjectRoot "Saved\AetherMeshTerrainInstall.txt"
$UnrealEditorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$UnrealEditor = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor.exe"

foreach ($Path in @($UProject, $Generator, $InstallScript, $UnrealEditorCmd)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required file was not found: $Path"
    }
}

$RunningEditor = Get-Process -Name "UnrealEditor", "UnrealEditor-Cmd" -ErrorAction SilentlyContinue
if ($RunningEditor) {
    throw "Close every Unreal Editor window before running recovery."
}

$Python = Get-Command python.exe -ErrorAction SilentlyContinue
if (-not $Python) {
    $Python = Get-Command py.exe -ErrorAction SilentlyContinue
}
if (-not $Python) {
    throw "Python was not found. Install Python or add it to PATH."
}

Write-Host "=== Ensuring terrain generator dependencies ===" -ForegroundColor Cyan
if ($Python.Name -ieq "py.exe") {
    & $Python.Source -3 -m pip install --user numpy pillow scipy
} else {
    & $Python.Source -m pip install --user numpy pillow scipy
}
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed with exit code $LASTEXITCODE."
}

Write-Host "=== Regenerating all production terrain source files ===" -ForegroundColor Cyan
if ($Python.Name -ieq "py.exe") {
    & $Python.Source -3 $Generator
} else {
    & $Python.Source $Generator
}
if ($LASTEXITCODE -ne 0) {
    throw "Terrain source generation failed with exit code $LASTEXITCODE."
}

$RequiredSources = @(
    "SourceAssets\ProductionTerrain\Heightmaps\AetherFlight_4033_16bit.png",
    "SourceAssets\ProductionTerrain\Textures\T_ForestFloor_BaseColor.png",
    "SourceAssets\ProductionTerrain\Textures\T_Sand_BaseColor.png",
    "SourceAssets\ProductionTerrain\Textures\T_Wetland_BaseColor.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_Grass_4033.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_ForestFloor_4033.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_Rock_4033.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_Scree_4033.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_Snow_4033.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_Sand_4033.png",
    "SourceAssets\ProductionTerrain\Weightmaps\AetherFlight_Wetland_4033.png"
)
foreach ($RelativePath in $RequiredSources) {
    $FullPath = Join-Path $ProjectRoot $RelativePath
    if (-not (Test-Path -LiteralPath $FullPath)) {
        throw "Terrain generator did not create required source: $FullPath"
    }
}

if (Test-Path -LiteralPath $InstallReport) {
    Remove-Item -LiteralPath $InstallReport -Force
}

Write-Host "=== Installing clean Mesh Terrain authoring assets ===" -ForegroundColor Cyan
& $UnrealEditorCmd `
    $UProject `
    "-ExecutePythonScript=$InstallScript" `
    -unattended `
    -nop4 `
    -nosplash `
    -NoSound `
    -log

if ($LASTEXITCODE -ne 0) {
    throw "Unreal returned exit code $LASTEXITCODE. Check Saved\Logs\AetherFlight.log."
}
if (-not (Test-Path -LiteralPath $InstallReport)) {
    throw "Mesh Terrain installation did not complete. Check Saved\Logs\AetherFlight.log for LogPython errors."
}

$ReportText = Get-Content -LiteralPath $InstallReport -Raw
Write-Host ""
Write-Host $ReportText -ForegroundColor Green
Write-Host "Recovery completed successfully. Continue at Step 2 in MESH_TERRAIN_UE58_SETUP.md." -ForegroundColor Green

if (-not $DoNotOpenEditor) {
    if (-not (Test-Path -LiteralPath $UnrealEditor)) {
        throw "UnrealEditor.exe was not found: $UnrealEditor"
    }
    Start-Process -FilePath $UnrealEditor -ArgumentList @($UProject, "/Game/Maps/AetherWorld")
}
