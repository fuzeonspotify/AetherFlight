#include "AetherFlightGameMode.h"

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

    // ACinematicFlightPawn::BeginPlay now owns the complete start sequence:
    // 20,000-foot positioning, World Partition source activation, initial
    // streaming hold, and flight release. Resetting it again here caused a
    // second teleport while cells were loading and made startup streaming do
    // duplicate work.
}
