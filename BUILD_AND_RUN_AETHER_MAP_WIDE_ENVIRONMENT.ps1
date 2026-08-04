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
Write-Host "Base trees: DZ Pine, Aspen, Cork Oak, and Coconut/Palm"
Write-Host "Regular Nanite trees: both Acer variants from the free Nanite sample collection"
Write-Host "Dense ground layer: Nanite Abelia, Lolium grass, and Ophiopogon ground cover"
Write-Host "Additional shrubs: GV Free Shrubs Pack A and B"
Write-Host "Rocks: all 7 Environment - Rock Collection 04 meshes with small, medium, and large scaling"
Write-Host "Coverage: streamed local rings that follow the aircraft across the entire 48 km AetherWorld"
Write-Host "Renderer safety: persistent HISM components, no foliage collision, dynamic shadows, or distance fields"
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
        Get-Content -LiteralPath $logPath -Tail 520 |
            Select-String -Pattern "error C|fatal error|AetherEnhancedEnvironmentActor|AetherEnvironmentDiversityFloorActor|AetherVerifiedEnvironmentActor|AetherFlightGameMode|CinematicFlightPawn" -Context 5,20
    }
    throw "Aether cinematic environment build failed with exit code $LASTEXITCODE."
}

Write-Host ""
Write-Host "AETHER CINEMATIC ENVIRONMENT BUILD SUCCEEDED" -ForegroundColor Green
Write-Host "Launching AetherWorld with -AetherMapEnvironment..."
Write-Host "Press Play and wait for both CINEMATIC MAP-WIDE STREAMING READY and DENSE NANITE PLANTS AND MULTI-ROCK STREAMING READY."
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
