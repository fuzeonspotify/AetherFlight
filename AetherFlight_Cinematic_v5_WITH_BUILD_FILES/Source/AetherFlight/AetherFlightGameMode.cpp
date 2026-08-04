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
    const bool bRunMapEnvironment =
        FParse::Param(FCommandLine::Get(), TEXT("AetherMapEnvironment"));

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
            TEXT("[Aether Environment Test] Opt-in limited approval zone enabled."));
    }
    else if (bRunMapEnvironment)
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
            TEXT("[Aether Map Environment] Opt-in persistent map-wide streaming enabled."));
    }
    else
    {
        // After two Renderer crashes, ordinary editor and Play launches remain
        // terrain-only. The dedicated launcher supplies -AetherMapEnvironment
        // for the repaired persistent-HISM implementation.
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Map Environment] Stable terrain-only launch. Use the dedicated map-wide launcher to enable foliage."));
    }

    // ACinematicFlightPawn::BeginPlay owns the normal streaming-source startup
    // and flight release. Environment actors wait for Mesh Terrain collision
    // before generating any instances.
}
