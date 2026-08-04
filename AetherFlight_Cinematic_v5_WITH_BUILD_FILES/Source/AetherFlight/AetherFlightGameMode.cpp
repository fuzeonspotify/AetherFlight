#include "AetherFlightGameMode.h"

#include "AetherEnvironmentTestActor.h"
#include "AetherFlightHUD.h"
#include "CinematicFlightPawn.h"
#include "EngineUtils.h"
#include "ProceduralWorldDirector.h"

AAetherFlightGameMode::AAetherFlightGameMode()
{
    DefaultPawnClass = ACinematicFlightPawn::StaticClass();
    HUDClass = AAetherFlightHUD::StaticClass();
}

void AAetherFlightGameMode::StartPlay()
{
    Super::StartPlay();

    AProceduralWorldDirector* Director = nullptr;
    for (TActorIterator<AProceduralWorldDirector> It(GetWorld()); It; ++It)
    {
        Director = *It;
        break;
    }

    if (!Director)
    {
        Director = GetWorld()->SpawnActor<AProceduralWorldDirector>();
    }

    if (Director)
    {
        Director->EnsureWorldGenerated();
    }

    // Keep the ecosystem rollout deliberately small until mesh scale, density,
    // collision traces and performance are approved. The test actor also moves
    // the player above the zone after the normal pawn startup has completed.
    AAetherEnvironmentTestActor* EnvironmentTest = nullptr;
    for (TActorIterator<AAetherEnvironmentTestActor> It(GetWorld()); It; ++It)
    {
        EnvironmentTest = *It;
        break;
    }
    if (!EnvironmentTest)
    {
        EnvironmentTest = GetWorld()->SpawnActor<AAetherEnvironmentTestActor>();
    }

    // ACinematicFlightPawn::BeginPlay owns the normal streaming-source startup
    // and flight release. The environment test actor performs one later,
    // intentional teleport into the small approval zone.
}
