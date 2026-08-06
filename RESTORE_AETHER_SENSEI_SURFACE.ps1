[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\RestoreAetherSenseiSurface_UE58.py"
$reportPath = Join-Path $projectRoot "Saved\AetherBiomeRollbackReport.txt"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before restoring the Sensei surface."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Rollback script was not found: $pythonScript"
}

$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
if (!(Test-Path -LiteralPath $editor)) {
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

Write-Host "Restoring the verified Sensei terrain surface..."
$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -Wait
Write-Host "Unreal exited with code $($process.ExitCode)."

if (Test-Path -LiteralPath $reportPath) {
    Get-Content -LiteralPath $reportPath
    exit 0
}

if (Test-Path -LiteralPath $logPath) {
    Get-Content -LiteralPath $logPath -Tail 220 |
        Select-String -Pattern "RestoreAetherSenseiSurface|LogPython: Error|Traceback|RuntimeError" -Context 6,20
}
throw "Sensei surface rollback failed."
