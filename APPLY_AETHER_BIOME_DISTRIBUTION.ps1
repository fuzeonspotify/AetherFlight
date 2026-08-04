[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\ApplyAetherBiomeDistribution_UE58.py"
$reportPath = Join-Path $projectRoot "Saved\AetherBiomeDistributionReport.txt"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Aether biome-distribution script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before applying the biome distribution update."
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
Write-Host "Aether biome distribution update is ready."
Write-Host ""
Write-Host "This creates an Aether-owned biome material using height, slope, and macro variation."
Write-Host "The current Sensei surface material remains available as rollback."
Write-Host "Terrain geometry, collision, Mesh Partition resolution, channels, and streaming are unchanged."
Write-Host ""
Write-Host "Launching Unreal Engine 5.8..."
Write-Host "Unreal will close automatically when the script finishes."
Write-Host "Waiting for Unreal to exit..."

$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -Wait
Write-Host "Unreal exited with code $($process.ExitCode)."

if (Test-Path -LiteralPath $reportPath) {
    Write-Host ""
    Write-Host "AETHER BIOME DISTRIBUTION FINISHED"
    Write-Host "----------------------------------"
    Get-Content -LiteralPath $reportPath
    exit 0
}

Write-Host ""
Write-Host "AETHER BIOME DISTRIBUTION FAILED" -ForegroundColor Red
Write-Host "----------------------------------"
Write-Host "The update did not create its completion report."

if (Test-Path -LiteralPath $logPath) {
    $logLines = Get-Content -LiteralPath $logPath
    $matches = $logLines | Select-String -Pattern (
        "ApplyAetherBiomeDistribution|Aether Biome Distribution|" +
        "LogPython: Error|Traceback|RuntimeError|TypeError|AttributeError|" +
        "Could not connect|Python script executed with errors"
    ) -Context 8,24

    if ($matches) {
        $matches | Select-Object -Last 20
    } else {
        $logLines | Select-Object -Last 320
    }
} else {
    Write-Host "Unreal log was not found: $logPath"
}

throw "Aether biome distribution update failed. The Unreal traceback is printed above."
