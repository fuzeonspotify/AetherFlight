[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\TuneAetherSenseiBiomes_UE58.py"
$reportPath = Join-Path $projectRoot "Saved\AetherSenseiBiomeTuningReport.txt"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Sensei biome-tuning script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before applying the biome tuning pass."
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
Write-Host "Aether safe Sensei biome tuning is ready."
Write-Host ""
Write-Host "This duplicates the working Sensei surface and tunes only audited scalar controls."
Write-Host "The current MI_AetherTerrain_Sensei_Surface remains untouched as rollback."
Write-Host "Terrain geometry, collision, Mesh Partition resolution, displacement, and streaming are unchanged."
Write-Host ""
Write-Host "Launching Unreal Engine 5.8..."
Write-Host "Unreal will close automatically after the tuning script finishes."
Write-Host "Waiting for Unreal to exit..."

$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -Wait
Write-Host "Unreal exited with code $($process.ExitCode)."

if (Test-Path -LiteralPath $reportPath) {
    Write-Host ""
    Write-Host "AETHER SENSEI BIOME TUNING FINISHED"
    Write-Host "------------------------------------"
    Get-Content -LiteralPath $reportPath
    exit 0
}

Write-Host ""
Write-Host "AETHER SENSEI BIOME TUNING FAILED" -ForegroundColor Red
Write-Host "------------------------------------"
Write-Host "The tuning pass did not create its completion report."

if (Test-Path -LiteralPath $logPath) {
    $logLines = Get-Content -LiteralPath $logPath
    $matches = $logLines | Select-String -Pattern (
        "TuneAetherSenseiBiomes|Aether Sensei Biome Tuning|" +
        "LogPython: Error|Traceback|RuntimeError|TypeError|AttributeError|" +
        "verification failed|rejected audited scalar|Python script executed with errors"
    ) -Context 8,24

    if ($matches) {
        $matches | Select-Object -Last 24
    } else {
        $logLines | Select-Object -Last 340
    }
} else {
    Write-Host "Unreal log was not found: $logPath"
}

throw "Aether Sensei biome tuning failed. The Unreal traceback is printed above."
