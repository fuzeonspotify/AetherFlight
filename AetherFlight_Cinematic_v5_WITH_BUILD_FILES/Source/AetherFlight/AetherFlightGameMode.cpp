#include "AetherFlightGameMode.h"

#include "AetherFlightHUD.h"
#include "CinematicFlightPawn.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
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

    APlayerController* PlayerController = GetWorld()->GetFirstPlayerController();
    if (ACinematicFlightPawn* Aircraft = PlayerController ? Cast<ACinematicFlightPawn>(PlayerController->GetPawn()) : nullptr)
    {
        Aircraft->ResetAircraft();
    }
}
