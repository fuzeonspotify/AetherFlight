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
 * Instances are deterministic, clustered, slope/altitude aware, and rendered
 * through HISM components so the flight world can contain thousands of trees
 * and rocks without creating thousands of Actors.
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
    UHierarchicalInstancedStaticMeshComponent* Shrubs;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* GroundCover;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderPrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment")
    UHierarchicalInstancedStaticMeshComponent* BoulderSecondary;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment")
    bool bEnableRuntimeScatter = true;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment", meta = (ClampMin = "1"))
    int32 EnvironmentSeed = 1847;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "0", ClampMax = "3000"))
    int32 ForestClusterBudget = 850;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "1", ClampMax = "80"))
    int32 TreesPerCluster = 34;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "0", ClampMax = "50000"))
    int32 ShrubInstanceBudget = 10000;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Forest", meta = (ClampMin = "0", ClampMax = "60000"))
    int32 GroundCoverInstanceBudget = 16000;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment|Rocks", meta = (ClampMin = "0", ClampMax = "20000"))
    int32 RockInstanceBudget = 4200;

private:
    UHierarchicalInstancedStaticMeshComponent* CreateScatterComponent(
        const FName Name, int32 StartCullDistance, int32 EndCullDistance);
    UStaticMesh* LoadFirstAvailable(const TArray<FSoftObjectPath>& CandidatePaths) const;
    TArray<UStaticMesh*> LoadLargestMeshesInPaths(
        const TArray<FName>& PackagePaths, int32 MaxMeshes) const;
    bool FindLandscapeBounds(FBox2D& OutBounds) const;
    bool SampleLandscape(float X, float Y, float& OutHeightMeters, FVector& OutNormal) const;
    bool IsInsideRunwayClearance(float X, float Y) const;
    bool ReserveCell(TSet<uint64>& OccupiedCells, float X, float Y, float CellSize) const;
    bool TryAddTree(float X, float Y, FRandomStream& Random, TSet<uint64>& OccupiedCells);
    void TryAddUnderstory(float X, float Y, FRandomStream& Random);
    void GenerateForest(const FBox2D& Bounds, FRandomStream& Random);
    void GenerateRocks(const FBox2D& Bounds, FRandomStream& Random);
    void DisableLegacyScatterIfReplaced();
    float ValueNoise(float X, float Y) const;
    float HashNoise(int32 X, int32 Y) const;

    FTimerHandle ScatterBuildTimer;
    int32 BuildAttempt = 0;
    bool bBuilt = false;
};
