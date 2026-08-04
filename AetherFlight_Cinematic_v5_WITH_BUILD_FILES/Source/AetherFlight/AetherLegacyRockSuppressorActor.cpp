#include "AetherLegacyRockSuppressorActor.h"

#include "AetherVerifiedEnvironmentActor.h"
#include "Components/HierarchicalInstancedStaticMeshComponent.h"
#include "Engine/World.h"
#include "EngineUtils.h"

AAetherLegacyRockSuppressorActor::AAetherLegacyRockSuppressorActor()
{
    PrimaryActorTick.bCanEverTick = false;
    SetActorEnableCollision(false);
}

void AAetherLegacyRockSuppressorActor::BeginPlay()
{
    Super::BeginPlay();
    if (!GetWorld())
    {
        return;
    }

    SuppressLegacyRocks();
    GetWorldTimerManager().SetTimer(
        SuppressTimer,
        this,
        &AAetherLegacyRockSuppressorActor::SuppressLegacyRocks,
        4.0f,
        true,
        4.0f);
}

void AAetherLegacyRockSuppressorActor::SuppressLegacyRocks()
{
    if (!GetWorld())
    {
        return;
    }

    for (TActorIterator<AAetherVerifiedEnvironmentActor> It(GetWorld()); It; ++It)
    {
        TArray<UHierarchicalInstancedStaticMeshComponent*> Components;
        It->GetComponents<UHierarchicalInstancedStaticMeshComponent>(Components);
        for (UHierarchicalInstancedStaticMeshComponent* Component : Components)
        {
            if (!Component || Component->GetFName() != TEXT("CinematicRocks"))
            {
                continue;
            }

            const int32 Removed = Component->GetInstanceCount();
            Component->ClearInstances();
            Component->SetVisibility(false, true);
            Component->SetHiddenInGame(true, true);
            UE_LOG(
                LogTemp,
                Display,
                TEXT("[Aether Rock Collection 04] Temporary PCG boulder component suppressed; removed %d instances."),
                Removed);
            return;
        }
    }
}
