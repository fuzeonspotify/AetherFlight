[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\AuditAetherSenseiMaterialParameters_UE58.py"
$reportPath = Join-Path $projectRoot "Saved\AetherSenseiParameterAudit.txt"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Sensei parameter audit script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before running the parameter audit."
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
Write-Host "Auditing the actual parameters exposed by AetherWorld's active terrain material..."
Write-Host "This is read-only and does not change terrain or material assets."
Write-Host "Waiting for Unreal to finish..."

$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -Wait
Write-Host "Unreal exited with code $($process.ExitCode)."

if (Test-Path -LiteralPath $reportPath) {
    Write-Host ""
    Write-Host "AETHER SENSEI PARAMETER AUDIT FINISHED"
    Write-Host "---------------------------------------"
    Get-Content -LiteralPath $reportPath
    exit 0
}

Write-Host ""
Write-Error "The audit did not create its report."
if (Test-Path -LiteralPath $logPath) {
    Get-Content -LiteralPath $logPath -Tail 200 |
        Select-String -Pattern "Aether Sensei Parameter Audit|Python|Traceback|Error|Fatal"
}
exit 1
