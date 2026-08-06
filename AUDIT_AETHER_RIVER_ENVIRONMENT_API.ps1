[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$auditScript = Join-Path $projectRoot "Content\Python\AuditAetherRiverEnvironmentAPI_UE58.py"
$auditReport = Join-Path $projectRoot "Saved\AetherRiverEnvironmentAPIAudit.txt"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor and Crash Reporter window before auditing Stage 13."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}
if (!(Test-Path -LiteralPath $auditScript)) {
    throw "Stage 13 river environment API audit script was not found: $auditScript"
}

Remove-Item -LiteralPath $auditReport -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "Auditing Stage 13 river exclusion, HISM placement, and environment asset support..."
Write-Host ""

$process = Start-Process `
    -FilePath $editor `
    -ArgumentList @(
        ('"{0}"' -f $project),
        "/Game/Maps/AetherWorld",
        "-nosound",
        "-unattended",
        ('-ExecutePythonScript="{0}"' -f $auditScript)
    ) `
    -PassThru `
    -Wait

if (!(Test-Path -LiteralPath $auditReport)) {
    throw "The Stage 13 audit finished with exit code $($process.ExitCode), but no report was created."
}

Get-Content -LiteralPath $auditReport
Write-Host ""
Write-Host "Stage 13 audit complete. No actors, instances, or packages were changed." -ForegroundColor Green
