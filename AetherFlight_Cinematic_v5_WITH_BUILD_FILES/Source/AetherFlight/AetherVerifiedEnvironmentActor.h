#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherVerifiedEnvironmentActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;
struct FHitResult;

/**
 * Map-wide environment streamer using the exact static meshes found by the
 * project asset audit. Three persistent HISM components are reused for the
 * entire play session; no runtime renderer components are created or destroyed.
 */
UCLASS()
class AETHERFLIGHT_API AAetherVerifiedEnvironmentActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherVerifiedEnvironmentActor();

protected:
    virtual void BeginPlay() override;

private:
    UPROPERTY(VisibleAnywhere)
    USceneComponent* Root;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* TreePrimary;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* TreeSecondary;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* Rocks;

    UHierarchicalInstancedStaticMeshComponent* CreateScatterComponent(
        FName Name,
        int32 EndCullDistanceCm);

    void PrepareEnvironment();
    void UpdateEnvironment();
    void BeginLocalRing(const FIntPoint& CenterChunk);
    bool GenerateChunk(const FIntPoint& Chunk);
    void ClearInstances();

    bool LoadVerifiedMeshes();
    bool TraceTerrain(float X, float Y, FVector& OutLocation, FVector& OutNormal) const;
    bool IsTerrainReady(const FBox2D& Bounds) const;
    bool LooksLikeWater(const FHitResult& Hit) const;
    bool IsInsideWorld(const FIntPoint& Chunk) const;
    FBox2D ChunkBounds(const FIntPoint& Chunk) const;
    FVector FocusLocation() const;
    float ScaleForHeight(const UStaticMesh* Mesh, float DesiredHeightCm) const;
    bool ReserveCell(TSet<uint64>& Cells, float X, float Y, float CellSize) const;

    FTimerHandle PrepareTimer;
    FTimerHandle UpdateTimer;
    TArray<FIntPoint> PendingChunks;
    TSet<FIntPoint> GeneratedChunks;
    FIntPoint CurrentCenterChunk = FIntPoint(0, 0);

    int32 PrepareAttempts = 0;
    int32 TotalTrees = 0;
    int32 TotalRocks = 0;
    bool bMeshesReady = false;
    bool bHasCenterChunk = false;

    static constexpr float ChunkSizeCm = 160000.0f;
    static constexpr int32 ActiveRadiusChunks = 2;
    static constexpr int32 TreesPerChunk = 82;
    static constexpr int32 RocksPerChunk = 15;
};
