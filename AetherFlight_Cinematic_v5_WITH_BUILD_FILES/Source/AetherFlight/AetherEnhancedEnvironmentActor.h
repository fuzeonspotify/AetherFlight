#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherEnhancedEnvironmentActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;
struct FAssetData;
struct FHitResult;

/**
 * Dense local-detail streamer layered over the stable cinematic environment.
 *
 * Uses the individual Nanite sample trees, shrub, and grasses plus every static
 * mesh discovered in Environment - Rock Collection 04. All renderer components
 * are persistent default subobjects and are reused while flying.
 */
UCLASS()
class AETHERFLIGHT_API AAetherEnhancedEnvironmentActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherEnhancedEnvironmentActor();

protected:
    virtual void BeginPlay() override;

private:
    UPROPERTY(VisibleAnywhere)
    USceneComponent* Root;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* NaniteTreeA;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* NaniteTreeB;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* AbeliaShrubs;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* LoliumGrass;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* OphiopogonGroundCover;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant01;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant02;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant03;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant04;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant05;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant06;

    UPROPERTY(VisibleAnywhere)
    UHierarchicalInstancedStaticMeshComponent* RockVariant07;

    UHierarchicalInstancedStaticMeshComponent* CreateScatterComponent(
        FName Name,
        int32 EndCullDistanceCm);

    TArray<UHierarchicalInstancedStaticMeshComponent*> RockComponents() const;

    void PrepareEnvironment();
    void UpdateEnvironment();
    void BeginLocalRing(const FIntPoint& CenterChunk);
    bool GenerateChunk(const FIntPoint& Chunk);
    void ClearInstances();

    bool LoadPlantAssets();
    int32 DiscoverAndAssignRockCollection();
    bool TraceTerrain(float X, float Y, FVector& OutLocation, FVector& OutNormal) const;
    bool IsTerrainReady(const FBox2D& Bounds) const;
    bool LooksLikeWater(const FHitResult& Hit) const;
    bool IsInsideWorld(const FIntPoint& Chunk) const;
    FBox2D ChunkBounds(const FIntPoint& Chunk) const;
    FVector FocusLocation() const;
    float ScaleForHeight(const UStaticMesh* Mesh, float DesiredHeightCm) const;
    bool ReserveCell(TSet<uint64>& Cells, float X, float Y, float CellSizeCm) const;

    int32 ScatterPlants(
        UHierarchicalInstancedStaticMeshComponent* Component,
        FRandomStream& Random,
        const FBox2D& Bounds,
        int32 CandidateCount,
        float MinimumNormalZ,
        float MinimumHeightMeters,
        float MaximumHeightMeters,
        float MinimumDesiredHeightCm,
        float MaximumDesiredHeightCm,
        float CellSizeCm,
        TSet<uint64>& ReservedCells,
        bool bAlignToSurface);

    int32 ScatterRocks(
        FRandomStream& Random,
        const FBox2D& Bounds,
        int32 CandidateCount,
        TSet<uint64>& ReservedCells);

    FTimerHandle PrepareTimer;
    FTimerHandle UpdateTimer;
    TArray<FIntPoint> PendingChunks;
    TSet<FIntPoint> GeneratedChunks;
    FIntPoint CurrentCenterChunk = FIntPoint(0, 0);

    int32 PrepareAttempts = 0;
    int32 TotalNaniteTrees = 0;
    int32 TotalShrubs = 0;
    int32 TotalGrass = 0;
    int32 TotalGroundCover = 0;
    int32 TotalRocks = 0;
    int32 LoadedRockVariants = 0;
    bool bAssetsReady = false;
    bool bHasCenterChunk = false;

    static constexpr float ChunkSizeCm = 80000.0f;
    static constexpr int32 ActiveRadiusChunks = 1;
    static constexpr int32 NaniteTreesPerChunk = 36;
    static constexpr int32 ShrubsPerChunk = 180;
    static constexpr int32 LoliumPerChunk = 300;
    static constexpr int32 OphiopogonPerChunk = 260;
    static constexpr int32 RocksPerChunk = 35;
};
