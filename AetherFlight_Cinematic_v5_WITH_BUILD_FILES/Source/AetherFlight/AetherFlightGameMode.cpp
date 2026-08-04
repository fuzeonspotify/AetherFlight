#include "AetherFlightGameMode.h"

#include "AetherEnhancedEnvironmentActor.h"
#include "AetherEnvironmentDiversityFloorActor.h"
#include "AetherEnvironmentTestActor.h"
#include "AetherFlightHUD.h"
#include "AetherVerifiedEnvironmentActor.h"
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
        AAetherVerifiedEnvironmentActor* VerifiedEnvironment = nullptr;
        for (TActorIterator<AAetherVerifiedEnvironmentActor> It(GetWorld()); It; ++It)
        {
            VerifiedEnvironment = *It;
            break;
        }
        if (!VerifiedEnvironment)
        {
            VerifiedEnvironment = GetWorld()->SpawnActor<AAetherVerifiedEnvironmentActor>();
        }

        AAetherEnvironmentDiversityFloorActor* DiversityFloor = nullptr;
        for (TActorIterator<AAetherEnvironmentDiversityFloorActor> It(GetWorld()); It; ++It)
        {
            DiversityFloor = *It;
            break;
        }
        if (!DiversityFloor)
        {
            DiversityFloor = GetWorld()->SpawnActor<AAetherEnvironmentDiversityFloorActor>();
        }

        AAetherEnhancedEnvironmentActor* EnhancedEnvironment = nullptr;
        for (TActorIterator<AAetherEnhancedEnvironmentActor> It(GetWorld()); It; ++It)
        {
            EnhancedEnvironment = *It;
            break;
        }
        if (!EnhancedEnvironment)
        {
            EnhancedEnvironment = GetWorld()->SpawnActor<AAetherEnhancedEnvironmentActor>();
        }

        UE_LOG(LogTemp, Display,
            TEXT("[Aether Cinematic Environment] Base biomes, species diversity, dense Nanite plants, and all Rock Collection 04 variants enabled."));
    }
    else
    {
        // Ordinary editor and Play launches remain terrain-only. The dedicated
        // launcher supplies -AetherMapEnvironment for the cinematic environment.
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Cinematic Environment] Stable terrain-only launch. Use the map-wide launcher to enable vegetation."));
    }

    // ACinematicFlightPawn::BeginPlay owns the normal streaming-source startup
    // and flight release. Environment actors wait for Mesh Terrain collision
    // before generating any instances.
}
