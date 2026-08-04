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
$reportPath = Join-Path $projectRoot "Saved\AetherSurfaceDetailReport.txt"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Aether surface-verification script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before verifying the terrain surface."
}

Write-Host ""
Write-Host "Aether terrain surface verification is ready."
Write-Host "Project: $project"
Write-Host "Script:  $pythonScript"
Write-Host ""
Write-Host "The verifier checks the 15 existing Aether BaseColor, Normal, and Roughness overrides."
Write-Host "It also confirms all displacement overrides remain at zero."
Write-Host "It does not modify or save any Unreal asset."

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

if (Test-Path -LiteralPath $reportPath) {
    Remove-Item -LiteralPath $reportPath -Force
}

$arguments = @(
    ('"{0}"' -f $project),
    "-nosound",
    ('-ExecutePythonScript="{0}"' -f $pythonScript)
)

Write-Host ""
Write-Host "Launching Unreal Engine 5.8 and verifying the terrain surface..."
Write-Host "Unreal will close automatically after the Python script finishes."
Write-Host "Waiting for Unreal to exit..."

$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -Wait
Write-Host "Unreal exited with code $($process.ExitCode)."

if (Test-Path -LiteralPath $reportPath) {
    Write-Host ""
    Write-Host "AETHER SURFACE VERIFICATION FINISHED"
    Write-Host "------------------------------------"
    Get-Content -LiteralPath $reportPath
    exit 0
}

Write-Host ""
Write-Host "AETHER SURFACE VERIFICATION FAILED" -ForegroundColor Red
Write-Host "------------------------------------"
Write-Host "The verifier did not create its completion report."

if (Test-Path -LiteralPath $logPath) {
    $logLines = Get-Content -LiteralPath $logPath
    $matches = $logLines | Select-String -Pattern (
        "UpgradeAetherTerrainSurfaceDetail|Aether Surface Verification|" +
        "LogPython: Error|Traceback|RuntimeError|TypeError|AttributeError|" +
        "verification failed|Python script executed with errors"
    ) -Context 8,22

    if ($matches) {
        $matches | Select-Object -Last 20
    } else {
        Write-Host "No filtered traceback was found; showing the last 300 log lines."
        $logLines | Select-Object -Last 300
    }
} else {
    Write-Host "Unreal log was not found: $logPath"
}

throw "Aether surface verification failed. The Unreal traceback is printed above."
