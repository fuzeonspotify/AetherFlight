[CmdletBinding()]
param(
    [string]$EngineRoot = "C:\Program Files\Epic Games\UE_5.8",
    [switch]$SkipBuild,
    [switch]$DoNotOpenEditor
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$UProject = Join-Path $ProjectRoot "AetherFlight.uproject"
$BuildLog = Join-Path $ProjectRoot "Build_AetherFlight.log"
$PythonRoot = Join-Path $ProjectRoot "Content\Python"
$ResetScript = Join-Path $PythonRoot "ResetAetherTerrain_UE58.py"
$ResetReport = Join-Path $ProjectRoot "Saved\AetherTerrainReset.txt"
$RecoveryScript = Join-Path $ProjectRoot "RECOVER_AETHER_MESH_TERRAIN_INSTALL_UE58.ps1"
$EngineBuild = Join-Path $EngineRoot "Engine\Build\BatchFiles\Build.bat"
$UnrealEditorCmd = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor-Cmd.exe"
$UnrealEditor = Join-Path $EngineRoot "Engine\Binaries\Win64\UnrealEditor.exe"

foreach ($Path in @($UProject, $ResetScript, $RecoveryScript, $EngineBuild, $UnrealEditorCmd)) {
    if (-not (Test-Path -LiteralPath $Path)) {
        throw "Required file was not found: $Path"
    }
}

$RunningEditor = Get-Process -Name "UnrealEditor", "UnrealEditor-Cmd" -ErrorAction SilentlyContinue
if ($RunningEditor) {
    throw "Close every Unreal Editor window before running the terrain reset."
}

function Invoke-UnrealPython {
    param(
        [Parameter(Mandatory = $true)]
        [string]$ScriptPath,
        [Parameter(Mandatory = $true)]
        [string]$StepName
    )

    Write-Host ""
    Write-Host "=== $StepName ===" -ForegroundColor Cyan
    & $UnrealEditorCmd `
        $UProject `
        "-ExecutePythonScript=$ScriptPath" `
        -unattended `
        -nop4 `
        -nosplash `
        -NoSound `
        -log

    if ($LASTEXITCODE -ne 0) {
        throw "$StepName failed with Unreal exit code $LASTEXITCODE. Check Saved\Logs\AetherFlight.log."
    }
}

if (-not $SkipBuild) {
    Write-Host "=== Building AetherFlightEditor ===" -ForegroundColor Cyan
    $BuildCommand = (
        "`"$EngineBuild`" AetherFlightEditor Win64 Development " +
        "-Project=`"$UProject`" -WaitMutex -NoHotReloadFromIDE " +
        "> `"$BuildLog`" 2>&1"
    )
    & cmd.exe /d /c $BuildCommand
    $BuildExitCode = $LASTEXITCODE

    if (Test-Path -LiteralPath $BuildLog) {
        Get-Content -LiteralPath $BuildLog
    }
    if ($BuildExitCode -ne 0) {
        throw "AetherFlight build failed with exit code $BuildExitCode. Check $BuildLog"
    }
}

if (Test-Path -LiteralPath $ResetReport) {
    Remove-Item -LiteralPath $ResetReport -Force
}
Invoke-UnrealPython -ScriptPath $ResetScript -StepName "Deleting every existing Landscape and Mesh Terrain actor"
if (-not (Test-Path -LiteralPath $ResetReport)) {
    throw "Terrain reset did not complete. Check Saved\Logs\AetherFlight.log for LogPython errors."
}

# Regenerate every source texture/weightmap and install the clean authoring assets.
# The recovery script also uses a success report because UnrealEditor-Cmd can return
# exit code 0 even when an executed Python script raises an exception.
& $RecoveryScript -EngineRoot $EngineRoot -DoNotOpenEditor
if ($LASTEXITCODE -ne 0) {
    throw "Clean Mesh Terrain authoring-asset installation failed."
}

Write-Host ""
Write-Host "Terrain reset and clean authoring-asset install completed." -ForegroundColor Green
Write-Host "Open MESH_TERRAIN_UE58_SETUP.md and continue at Step 2." -ForegroundColor Green
Write-Host "Use AetherFlight_4033_16bit.png. Do not import the .r16 file." -ForegroundColor Yellow

if (-not $DoNotOpenEditor) {
    if (-not (Test-Path -LiteralPath $UnrealEditor)) {
        throw "UnrealEditor.exe was not found: $UnrealEditor"
    }
    Start-Process -FilePath $UnrealEditor -ArgumentList @($UProject, "/Game/Maps/AetherWorld")
}
