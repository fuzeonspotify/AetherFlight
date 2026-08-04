#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherMapWideEnvironmentActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;
struct FHitResult;

/**
 * Renderer-safe map-wide environment streaming for AetherWorld.
 *
 * Five persistent HISM components are created once with the actor and reused for
 * the entire play session. When the aircraft enters a new 1.6 km cell, the
 * local ring is cleared and repopulated one terrain chunk per timer update.
 * Runtime HISM creation/destruction is intentionally avoided because the first
 * map-wide version repeatedly recreated renderer state while Mesh Terrain cells
 * were also streaming.
 */
UCLASS()
class AETHERFLIGHT_API AAetherMapWideEnvironmentActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherMapWideEnvironmentActor();

protected:
    virtual void BeginPlay() override;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Map Environment")
    USceneComponent* Root;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Map Environment")
    UHierarchicalInstancedStaticMeshComponent* TreePrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Map Environment")
    UHierarchicalInstancedStaticMeshComponent* TreeSecondary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Map Environment")
    UHierarchicalInstancedStaticMeshComponent* Shrubs;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Map Environment")
    UHierarchicalInstancedStaticMeshComponent* RockPrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Map Environment")
    UHierarchicalInstancedStaticMeshComponent* RockSecondary;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment")
    bool bEnableMapWideEnvironment = true;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment", meta = (ClampMin = "1"))
    int32 EnvironmentSeed = 260804;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "100000.0", ClampMax = "300000.0"))
    float ChunkSizeCm = 160000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "1", ClampMax = "3"))
    int32 ActiveRadiusInChunks = 2;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "0.5", ClampMax = "3.0"))
    float StreamingUpdateSeconds = 1.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Density", meta = (ClampMin = "0", ClampMax = "160"))
    int32 TreesPerChunk = 58;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Density", meta = (ClampMin = "0", ClampMax = "80"))
    int32 ShrubsPerChunk = 14;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Density", meta = (ClampMin = "0", ClampMax = "50"))
    int32 RocksPerChunk = 9;

private:
    UHierarchicalInstancedStaticMeshComponent* CreatePersistentScatterComponent(
        FName Name,
        int32 EndCullDistanceCm);
    void DisableLegacyEnvironment();
    void PrepareEnvironment();
    void UpdateStreaming();
    void StartLocalRing(const FIntPoint& CenterChunk);
    bool BuildChunk(const FIntPoint& Chunk);
    void ClearLocalRing();
    FVector GetFocusLocation() const;

    bool LoadEnvironmentAssets();
    TArray<UStaticMesh*> LoadSuitableMeshes(
        const TArray<FName>& Paths,
        const TArray<FString>& RequiredKeywords,
        int32 MaxMeshes,
        float DesiredHeightCm,
        float MinimumHeightCm,
        float MaximumHeightCm,
        float MaximumWidthToHeight) const;
    UStaticMesh* LoadFirstKeywordMesh(
        const TArray<FName>& Paths,
        const TArray<FString>& Keywords,
        float MinimumHeightCm,
        float MaximumHeightCm) const;
    bool IsUnsafeAggregateMeshName(const FString& Name) const;
    bool IsInsideWorldBounds(const FIntPoint& Chunk) const;
    FBox2D GetChunkBounds(const FIntPoint& Chunk) const;
    bool IsChunkTerrainReady(const FBox2D& Bounds) const;
    bool SampleTerrain(float X, float Y, FVector& OutLocation, FVector& OutNormal) const;
    bool LooksLikeWater(const FHitResult& Hit) const;
    bool ReserveCell(TSet<uint64>& Cells, float X, float Y, float CellSize) const;
    float ScaleForDesiredHeight(const UStaticMesh* Mesh, float DesiredHeightCm) const;

    FTimerHandle PrepareTimer;
    FTimerHandle StreamingTimer;
    TArray<FIntPoint> PendingChunks;
    TSet<FIntPoint> GeneratedChunks;
    FIntPoint CurrentCenterChunk = FIntPoint(0, 0);
    int32 PrepareAttempts = 0;
    int32 TotalTrees = 0;
    int32 TotalShrubs = 0;
    int32 TotalRocks = 0;
    bool bAssetsReady = false;
    bool bHasCenterChunk = false;
};
