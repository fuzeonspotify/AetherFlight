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
    throw "Close every Unreal Editor and Crash Reporter window before building the map-wide environment."
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
Write-Host "Building the Aether map-wide streamed environment..."
Write-Host "Coverage: entire 48 km AetherWorld"
Write-Host "Runtime: deterministic 1.6 km chunks around the aircraft"
Write-Host "Memory safety: distant chunks are destroyed as new chunks stream in"
Write-Host "Density per active chunk: up to 92 trees, 24 shrubs, 14 rocks"
Write-Host "Renderer safety: no foliage collision, dynamic shadows, or distance-field updates yet"
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
    Write-Host "AETHER MAP-WIDE ENVIRONMENT BUILD FAILED" -ForegroundColor Red
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 360 |
            Select-String -Pattern "error C|fatal error|AetherMapWideEnvironmentActor|AetherFlightGameMode|CinematicFlightPawn" -Context 5,16
    }
    throw "Aether map-wide environment build failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "AETHER MAP-WIDE ENVIRONMENT BUILD SUCCEEDED" -ForegroundColor Green
Write-Host "Launching AetherWorld..."
Write-Host "Press Play and wait for: AETHER // MAP-WIDE FORESTS AND ROCKS STREAMING"
Write-Host "Emergency terrain-only launch flag: -AetherNoEnvironment"
Write-Host ""

$arguments = @(
    ('"{0}"' -f $project),
    "/Game/Maps/AetherWorld",
    "-nosound",
    "-log"
)
Start-Process -FilePath $editor -ArgumentList $arguments
