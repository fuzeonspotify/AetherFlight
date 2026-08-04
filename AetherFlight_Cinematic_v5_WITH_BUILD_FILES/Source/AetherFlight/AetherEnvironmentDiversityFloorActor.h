#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherEnvironmentDiversityFloorActor.generated.h"

class AAetherVerifiedEnvironmentActor;
class UHierarchicalInstancedStaticMeshComponent;
struct FHitResult;

/**
 * Maintains a small local minimum of each cinematic vegetation type around the
 * aircraft. The main streamer still controls the dominant biome distribution;
 * this actor only prevents a valid local ring from becoming a pine monoculture.
 * It reuses the streamer's existing HISM components and creates no renderers.
 */
UCLASS()
class AETHERFLIGHT_API AAetherEnvironmentDiversityFloorActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherEnvironmentDiversityFloorActor();

protected:
    virtual void BeginPlay() override;

private:
    void ApplyDiversityFloor();

    AAetherVerifiedEnvironmentActor* FindEnvironmentActor() const;
    UHierarchicalInstancedStaticMeshComponent* FindComponent(
        AAetherVerifiedEnvironmentActor* Environment,
        FName ComponentName) const;

    bool TraceTerrain(float X, float Y, FVector& OutLocation, FVector& OutNormal) const;
    bool LooksLikeWater(const FHitResult& Hit) const;
    FVector FocusLocation() const;
    float ScaleForHeight(const UHierarchicalInstancedStaticMeshComponent* Component,
        float DesiredHeightCm) const;

    int32 EnsureMinimumInstances(
        UHierarchicalInstancedStaticMeshComponent* Component,
        const TCHAR* Label,
        int32 MinimumCount,
        float MinimumRadiusCm,
        float MaximumRadiusCm,
        float DesiredHeightMinCm,
        float DesiredHeightMaxCm,
        float MinimumNormalZ,
        int32 SeedOffset);

    FTimerHandle DiversityTimer;
    int32 PassNumber = 0;
};
