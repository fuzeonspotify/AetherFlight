#include "AetherBiomeWorldSubsystem.h"

#include "AetherBiomeScatterActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"

bool UAetherBiomeWorldSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    const UWorld* World = Cast<UWorld>(Outer);
    return World && (World->WorldType == EWorldType::Game || World->WorldType == EWorldType::PIE);
}

void UAetherBiomeWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);

    for (TActorIterator<AAetherBiomeScatterActor> It(&InWorld); It; ++It)
    {
        return;
    }

    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Name = TEXT("AetherBiomeScatter");
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    InWorld.SpawnActor<AAetherBiomeScatterActor>(
        FVector::ZeroVector, FRotator::ZeroRotator, SpawnParameters);
}
