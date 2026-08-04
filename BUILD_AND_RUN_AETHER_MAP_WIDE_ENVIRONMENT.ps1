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
    throw "Close every Unreal Editor and Crash Reporter window before building the cinematic map-wide environment."
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
Write-Host "Building the Aether cinematic map-wide environment..."
Write-Host "Trees: DZ Pine, Aspen, Cork Oak, and Coconut/Palm"
Write-Host "Shrubs: GV Free Shrubs Pack A and B"
Write-Host "Ground plant: Nanite Plants Sample Abelia"
Write-Host "Rock: PCG Boulder until a cinematic rock pack is installed"
Write-Host "Coverage: entire 48 km AetherWorld through a reusable local ring"
Write-Host "Renderer design: eight persistent HISM components; no runtime component creation or destruction"
Write-Host "Runtime: one 1.6 km terrain chunk generated per second"
Write-Host "Density per chunk: up to 72 trees, 28 shrubs, 20 plants, and 10 rocks"
Write-Host "Renderer safety: no foliage collision, dynamic shadows, distance fields, or density scaling"
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
    Write-Host "AETHER CINEMATIC ENVIRONMENT BUILD FAILED" -ForegroundColor Red
    if (Test-Path -LiteralPath $logPath) {
        Get-Content -LiteralPath $logPath -Tail 460 |
            Select-String -Pattern "error C|fatal error|AetherVerifiedEnvironmentActor|AetherFlightGameMode|CinematicFlightPawn" -Context 5,18
    }
    throw "Aether cinematic environment build failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "AETHER CINEMATIC ENVIRONMENT BUILD SUCCEEDED" -ForegroundColor Green
Write-Host "Launching AetherWorld with -AetherMapEnvironment..."
Write-Host "Press Play and wait for: AETHER CINEMATIC ENVIRONMENT"
Write-Host "A normal editor launch remains terrain-only."
Write-Host ""

$arguments = @(
    ('"{0}"' -f $project),
    "/Game/Maps/AetherWorld",
    "-AetherMapEnvironment",
    "-nosound",
    "-log"
)
Start-Process -FilePath $editor -ArgumentList $arguments
