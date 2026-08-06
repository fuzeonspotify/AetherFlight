#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherEnvironmentTestActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;

/**
 * Small opt-in ecosystem approval zone for the production Mesh Terrain.
 *
 * The test deliberately adds only a few instances per timer tick, uses
 * conservative no-shadow HISM components, and rejects cluster/billboard meshes.
 * This keeps terrain streaming and renderer work bounded while tree and rock
 * scale, placement, and asset compatibility are evaluated.
 */
UCLASS()
class AETHERFLIGHT_API AAetherEnvironmentTestActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherEnvironmentTestActor();

protected:
    virtual void BeginPlay() override;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment Test")
    USceneComponent* Root;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment Test")
    UHierarchicalInstancedStaticMeshComponent* TreePrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment Test")
    UHierarchicalInstancedStaticMeshComponent* TreeSecondary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment Test")
    UHierarchicalInstancedStaticMeshComponent* Shrubs;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment Test")
    UHierarchicalInstancedStaticMeshComponent* RockPrimary;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Environment Test")
    UHierarchicalInstancedStaticMeshComponent* RockSecondary;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test")
    bool bEnableEnvironmentTest = true;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test")
    FVector2D TestAreaCenter = FVector2D(-400000.0f, 400000.0f);

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "50000.0", ClampMax = "300000.0"))
    float TestAreaRadiusCm = 120000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "8000.0", ClampMax = "30000.0"))
    float SpawnAltitudeFeet = 12000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0", ClampMax = "1000"))
    int32 TreeBudget = 220;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0", ClampMax = "500"))
    int32 ShrubBudget = 70;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0", ClampMax = "300"))
    int32 RockBudget = 55;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "1"))
    int32 EnvironmentSeed = 260804;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0.05", ClampMax = "1.0"))
    float BuildBatchIntervalSeconds = 0.12f;

private:
    enum class EBuildPhase : uint8
    {
        Trees,
        Shrubs,
        Rocks,
        Complete
    };

    UHierarchicalInstancedStaticMeshComponent* CreateScatterComponent(
        FName Name, int32 StartCullDistance, int32 EndCullDistance);
    void PositionPlayerAboveTestArea();
    void PrepareTestArea();
    void ProcessBuildBatch();
    void AdvanceBuildPhase();
    bool CurrentPhaseFinished() const;
    int32 CurrentPhaseMaximumAttempts() const;
    bool TryPlaceTree();
    bool TryPlaceShrub();
    bool TryPlaceRock();
    FVector2D RandomPointInTestArea();
    bool SampleTerrain(float X, float Y, FVector& OutLocation, FVector& OutNormal) const;
    bool ReserveCell(TSet<uint64>& Cells, float X, float Y, float CellSize) const;
    TArray<UStaticMesh*> LoadSuitableMeshes(
        const TArray<FName>& Paths,
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
    float ScaleForDesiredHeight(const UStaticMesh* Mesh, float DesiredHeightCm) const;
    void ReportResult() const;

    FTimerHandle PositionTimer;
    FTimerHandle PrepareTimer;
    FTimerHandle BuildBatchTimer;
    FRandomStream Random;
    TSet<uint64> TreeCells;
    TSet<uint64> ShrubCells;
    TSet<uint64> RockCells;
    EBuildPhase BuildPhase = EBuildPhase::Trees;
    int32 PositionAttempts = 0;
    int32 PrepareAttempts = 0;
    int32 AttemptsInPhase = 0;
    int32 TreesPlaced = 0;
    int32 ShrubsPlaced = 0;
    int32 RocksPlaced = 0;
    bool bAssetsPrepared = false;
    bool bBuildStarted = false;
};
