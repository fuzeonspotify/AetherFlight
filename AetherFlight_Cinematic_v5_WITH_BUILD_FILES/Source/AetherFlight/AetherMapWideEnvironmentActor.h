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
 * Deterministic map-wide vegetation and rock streaming for AetherWorld.
 *
 * The world is divided into reusable runtime chunks around the aircraft. Chunks
 * outside the active radius are destroyed, so the environment can cover the
 * entire 48 km map without retaining every tree and rock visited during a long
 * flight. Mesh Terrain collision is sampled directly and only individual meshes
 * with safe bounds are selected from the installed environment packs.
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

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment")
    bool bEnableMapWideEnvironment = true;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment", meta = (ClampMin = "1"))
    int32 EnvironmentSeed = 260804;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "80000.0", ClampMax = "300000.0"))
    float ChunkSizeCm = 160000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "1", ClampMax = "4"))
    int32 ActiveRadiusInChunks = 2;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "1", ClampMax = "3"))
    int32 MaxNewChunksPerUpdate = 1;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Streaming", meta = (ClampMin = "0.25", ClampMax = "3.0"))
    float StreamingUpdateSeconds = 0.75f;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Density", meta = (ClampMin = "0", ClampMax = "300"))
    int32 TreesPerChunk = 92;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Density", meta = (ClampMin = "0", ClampMax = "120"))
    int32 ShrubsPerChunk = 24;

    UPROPERTY(EditAnywhere, Category = "Aether|Map Environment|Density", meta = (ClampMin = "0", ClampMax = "80"))
    int32 RocksPerChunk = 14;

private:
    struct FRuntimeChunk
    {
        TArray<UHierarchicalInstancedStaticMeshComponent*> Components;
        int32 TreeCount = 0;
        int32 ShrubCount = 0;
        int32 RockCount = 0;
    };

    void PrepareEnvironment();
    void UpdateStreaming();
    void DisableLegacyEnvironment();
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
    UHierarchicalInstancedStaticMeshComponent* CreateChunkComponent(
        const FIntPoint& Chunk,
        const TCHAR* Label,
        UStaticMesh* Mesh,
        int32 EndCullDistanceCm);
    bool BuildChunk(const FIntPoint& Chunk);
    void RemoveChunk(const FIntPoint& Chunk);
    void RemoveAllChunks();
    FVector GetFocusLocation() const;

    UPROPERTY()
    TArray<TObjectPtr<UStaticMesh>> TreeMeshes;

    UPROPERTY()
    TObjectPtr<UStaticMesh> ShrubMesh;

    UPROPERTY()
    TArray<TObjectPtr<UStaticMesh>> RockMeshes;

    TMap<FIntPoint, FRuntimeChunk> ActiveChunks;
    FTimerHandle PrepareTimer;
    FTimerHandle StreamingTimer;
    int32 PrepareAttempts = 0;
    bool bAssetsReady = false;
};
