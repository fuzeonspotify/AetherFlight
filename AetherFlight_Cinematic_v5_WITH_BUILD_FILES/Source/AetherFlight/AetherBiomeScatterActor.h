#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherBiomeScatterActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;

/**
 * Runtime ecosystem pass for the production Landscape.
 *
 * Instances are deterministic, biome-driven, slope/altitude aware, and streamed
 * in HISM chunks around the aircraft so the full flight world stays populated
 * without creating thousands of Actors or a large startup hitch.
 */
UCLASS(Blueprintable)
class AETHERFLIGHT_API AAetherBiomeScatterActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherBiomeScatterActor();

    UFUNCTION(BlueprintCallable, Category = "Aether|Environment")
    void BuildEnvironment();

    UFUNCTION(BlueprintCallable, Category = "Aether|Environment")
    void ClearEnvironment();

protected:
    virtual void BeginPlay() override;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    USceneComponent* Root;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* ConiferPrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* ConiferSecondary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BroadleafTrees;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* CorkOakTrees;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* WindmillPalms;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* CoconutPalms;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* Shrubs;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* GroundCover;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderPrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderSecondary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderVariant3;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderVariant4;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderVariant5;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderVariant6;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderVariant7;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment")
    bool bEnableRuntimeScatter = true;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment", meta = (ClampMin = "1"))
    int32 EnvironmentSeed = 1847;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "0", ClampMax = "120000"))
    int32 TreeInstanceBudget = 62000;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "0", ClampMax = "50000"))
    int32 ShrubInstanceBudget = 12000;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "0", ClampMax = "60000"))
    int32 GroundCoverInstanceBudget = 18000;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Rocks", meta = (ClampMin = "0", ClampMax = "20000"))
    int32 RockInstanceBudget = 2400;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Streaming", meta = (ClampMin = "100000.0", ClampMax = "500000.0"))
    float EcosystemChunkSizeCm = 240000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Streaming", meta = (ClampMin = "1", ClampMax = "6"))
    int32 StreamingRadiusInChunks = 4;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Streaming", meta = (ClampMin = "1", ClampMax = "20"))
    int32 MaxNewChunksPerUpdate = 6;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Streaming", meta = (ClampMin = "0.25", ClampMax = "5.0"))
    float StreamingUpdateSeconds = 1.0f;

private:
    UHierarchicalInstancedStaticMeshComponent* CreateScatterComponent(
        const FName Name, int32 StartCullDistance, int32 EndCullDistance);
    UStaticMesh* LoadFirstAvailable(const TArray<FSoftObjectPath>& CandidatePaths) const;
    TArray<UStaticMesh*> LoadLargestMeshesInPaths(
        const TArray<FName>& PackagePaths, int32 MaxMeshes) const;
    UStaticMesh* LoadFirstMeshMatchingKeywords(
        const TArray<FName>& PackagePaths, const TArray<FString>& Keywords) const;
    TArray<UHierarchicalInstancedStaticMeshComponent*> GetTreeComponents() const;
    int32 GetTreeInstanceCount() const;
    TArray<UHierarchicalInstancedStaticMeshComponent*> GetRockComponents() const;
    int32 GetRockInstanceCount() const;
    bool FindLandscapeBounds(FBox2D& OutBounds) const;
    bool SampleLandscape(float X, float Y, float& OutHeightMeters, FVector& OutNormal) const;
    bool IsInsideRunwayClearance(float X, float Y) const;
    bool IsInsideGeneratedWater(float X, float Y) const;
    float HydrologyMoisture(float X, float Y) const;
    bool ReserveCell(TSet<uint64>& OccupiedCells, float X, float Y, float CellSize) const;
    bool TryAddTree(float X, float Y, FRandomStream& Random, TSet<uint64>& OccupiedCells);
    void TryAddUnderstory(float X, float Y, FRandomStream& Random);
    void GenerateForest(const FBox2D& Bounds, FRandomStream& Random);
    void GenerateRocks(const FBox2D& Bounds, FRandomStream& Random);
    void StreamEnvironmentAroundPlayer();
    bool IsChunkLandscapeReady(const FBox2D& Bounds) const;
    void DisableLegacyScatterIfReplaced();
    float ValueNoise(float X, float Y) const;
    float HashNoise(int32 X, int32 Y) const;

    FTimerHandle ScatterBuildTimer;
    FTimerHandle ScatterStreamTimer;
    FBox2D CachedLandscapeBounds;
    TSet<FIntPoint> GeneratedChunks;
    TSet<uint64> OccupiedTreeCells;
    TSet<uint64> OccupiedSoloRockCells;
    TSet<uint64> OccupiedFormationRockCells;
    int32 BuildAttempt = 0;
    int32 StreamUpdateCount = 0;
    bool bLandscapeBoundsReady = false;
    bool bBuilt = false;
};
