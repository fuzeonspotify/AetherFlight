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
Write-Host "Building the crash-safe Aether Mesh Terrain ecosystem test..."
Write-Host "Test zone: 1.2 km radius around X=-400000, Y=400000"
Write-Host "Spawn: 12,000 ft, 1.8 km west of the test-zone center"
Write-Host "Budget: 220 trees, 70 shrubs, 55 rocks, added in small timed batches"
Write-Host "Shadows and distance-field lighting are disabled for this approval pass"
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
        Get-Content -LiteralPath $logPath -Tail 300 |
            Select-String -Pattern "error C|fatal error|AetherEnvironmentTestActor|AetherFlightGameMode" -Context 4,14
    }
    throw "Aether environment test build failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "AETHER ENVIRONMENT TEST BUILD SUCCEEDED" -ForegroundColor Green
Write-Host "Launching AetherWorld with the opt-in safe test flag..."
Write-Host "Look for: AETHER SAFE TEST READY // trees // shrubs // rocks"
Write-Host "Normal editor launches will not run the environment test."
Write-Host ""

$arguments = @(
    ('"{0}"' -f $project),
    "/Game/Maps/AetherWorld",
    "-AetherEnvironmentTest",
    "-nosound",
    "-log"
)
Start-Process -FilePath $editor -ArgumentList $arguments
