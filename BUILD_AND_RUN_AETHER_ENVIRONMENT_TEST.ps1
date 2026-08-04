[CmdletBinding()]
param()

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$repoRoot = $PSScriptRoot
$projectRoot = Join-Path $repoRoot "AetherFlight_Cinematic_v5_WITH_BUILD_FILES"
$project = Join-Path $projectRoot "AetherFlight.uproject"
$buildBat = "C:\Program Files\Epic Games\UE_5.8\Engine\Build\BatchFiles\Build.bat"
$editor = "C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
$logPath = Join-Path $projectRoot "Saved\Logs\AetherFlight.log"

if (Get-Process UnrealEditor -ErrorAction SilentlyContinue) {
    throw "Close every Unreal Editor window before building the environment test."
}
if (!(Test-Path -LiteralPath $project)) {
    throw "AetherFlight.uproject was not found: $project"
}
if (!(Test-Path -LiteralPath $buildBat)) {
    throw "UE 5.8 Build.bat was not found: $buildBat"
}
if (!(Test-Path -LiteralPath $editor)) {
    throw "UE 5.8 UnrealEditor.exe was not found: $editor"
}

Write-Host ""
Write-Host "Building the Aether Mesh Terrain ecosystem test..."
Write-Host "Test zone: 3 km radius around X=-400000, Y=400000"
Write-Host "Spawn: 20,000 ft, 1.2 km west of the test-zone center"
Write-Host ""

& $buildBat `
    AetherFlightEditor `
    Win64 `
    Development `
    "-Project=$project" `
    -WaitMutex `
    -FromMsBuild

if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Write-Host "AETHER ENVIRONMENT TEST BUILD FAILED" -ForegroundColor Red
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 260 |
            Select-String -Pattern "error C|fatal error|AetherEnvironmentTestActor|AetherFlightGameMode" -Context 4,12
    }
    throw "Aether environment test build failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "AETHER ENVIRONMENT TEST BUILD SUCCEEDED" -ForegroundColor Green
Write-Host "Launching AetherWorld..."
Write-Host "Look for: AETHER TEST READY // trees // shrubs // rocks"
Write-Host ""

$arguments = @(
    ('"{0}"' -f $project),
    "/Game/Maps/AetherWorld",
    "-nosound",
    "-log"
)
Start-Process -FilePath $editor -ArgumentList $arguments
