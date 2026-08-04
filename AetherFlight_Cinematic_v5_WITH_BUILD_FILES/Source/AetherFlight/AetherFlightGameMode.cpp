#include "AetherFlightGameMode.h"

#include "AetherEnvironmentTestActor.h"
#include "AetherFlightHUD.h"
#include "CinematicFlightPawn.h"
#include "EngineUtils.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
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

    // Keep normal editor and gameplay launches on the stable terrain-only path.
    // The deliberately limited ecosystem approval zone is enabled only by the
    // dedicated launcher using -AetherEnvironmentTest.
    if (FParse::Param(FCommandLine::Get(), TEXT("AetherEnvironmentTest")))
    {
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

        UE_LOG(LogTemp, Display,
            TEXT("[Aether Environment Test] Opt-in crash-safe approval zone enabled."));
    }

    // ACinematicFlightPawn::BeginPlay owns the normal streaming-source startup
    // and flight release. The opt-in test actor performs one later, intentional
    // teleport into the small approval zone.
}
