#include "AetherFlightGameMode.h"

#include "AetherEnvironmentTestActor.h"
#include "AetherFlightHUD.h"
#include "AetherMapWideEnvironmentActor.h"
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

    const bool bRunLimitedTest =
        FParse::Param(FCommandLine::Get(), TEXT("AetherEnvironmentTest"));
    const bool bDisableEnvironment =
        FParse::Param(FCommandLine::Get(), TEXT("AetherNoEnvironment"));

    if (bRunLimitedTest)
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
    else if (!bDisableEnvironment)
    {
        AAetherMapWideEnvironmentActor* MapEnvironment = nullptr;
        for (TActorIterator<AAetherMapWideEnvironmentActor> It(GetWorld()); It; ++It)
        {
            MapEnvironment = *It;
            break;
        }
        if (!MapEnvironment)
        {
            MapEnvironment = GetWorld()->SpawnActor<AAetherMapWideEnvironmentActor>();
        }

        UE_LOG(LogTemp, Display,
            TEXT("[Aether Map Environment] Map-wide deterministic chunk streaming enabled."));
    }
    else
    {
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Map Environment] Disabled by -AetherNoEnvironment."));
    }

    // ACinematicFlightPawn::BeginPlay owns the normal streaming-source startup
    // and flight release. Environment actors wait for Mesh Terrain collision
    // before generating any instances.
}
