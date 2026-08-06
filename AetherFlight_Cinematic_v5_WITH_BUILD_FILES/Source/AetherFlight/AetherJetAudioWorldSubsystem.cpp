#include "AetherJetAudioWorldSubsystem.h"

#include "AetherJetAudioActor.h"
#include "Engine/World.h"
#include "EngineUtils.h"

bool UAetherJetAudioWorldSubsystem::ShouldCreateSubsystem(UObject* Outer) const
{
    const UWorld* World = Cast<UWorld>(Outer);
    return World && (World->WorldType == EWorldType::Game || World->WorldType == EWorldType::PIE);
}

void UAetherJetAudioWorldSubsystem::OnWorldBeginPlay(UWorld& InWorld)
{
    Super::OnWorldBeginPlay(InWorld);

    for (TActorIterator<AAetherJetAudioActor> It(&InWorld); It; ++It)
    {
        return;
    }

    FActorSpawnParameters SpawnParameters;
    SpawnParameters.Name = TEXT("AetherJetAudio");
    SpawnParameters.SpawnCollisionHandlingOverride = ESpawnActorCollisionHandlingMethod::AlwaysSpawn;
    InWorld.SpawnActor<AAetherJetAudioActor>(
        FVector::ZeroVector,
        FRotator::ZeroRotator,
        SpawnParameters);
}
