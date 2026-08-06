[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$pythonScript = Join-Path $projectRoot "Content\Python\AuditAetherSenseiParameterInfo_UE58.py"
$reportPath = Join-Path $projectRoot "Saved\AetherSenseiParameterInfoAudit.txt"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $pythonScript)) {
    throw "Sensei parameter-info audit script was not found: $pythonScript"
}
if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before running the audit."
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
Write-Host "Reading Sensei's full material parameter info and override arrays..."
Write-Host "This does not modify or save any Unreal asset."
Write-Host "Waiting for Unreal to finish..."

$process = Start-Process -FilePath $editor -ArgumentList $arguments -PassThru -Wait
Write-Host "Unreal exited with code $($process.ExitCode)."

if (Test-Path -LiteralPath $reportPath) {
    Write-Host ""
    Write-Host "AETHER SENSEI PARAMETER-INFO AUDIT FINISHED"
    Write-Host "--------------------------------------------"
    Get-Content -LiteralPath $reportPath
    exit 0
}

Write-Host ""
Write-Host "The audit did not create its report." -ForegroundColor Red
if (Test-Path -LiteralPath $logPath) {
    Get-Content -LiteralPath $logPath -Tail 240 |
        Select-String -Pattern "Parameter Info Audit|LogPython: Error|Traceback|TypeError|RuntimeError|AttributeError" -Context 6,20
}
exit 1
