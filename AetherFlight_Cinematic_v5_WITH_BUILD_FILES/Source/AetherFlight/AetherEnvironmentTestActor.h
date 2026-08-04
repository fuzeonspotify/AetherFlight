#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "TimerManager.h"
#include "AetherEnvironmentTestActor.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;

/**
 * Small, deterministic ecosystem test zone for the production Mesh Terrain.
 *
 * It uses HISM components, discovers the installed tree/rock packs at runtime,
 * accepts Mesh Terrain collision during line traces, and places only a limited
 * number of instances so density, scale and performance can be approved before
 * the ecosystem is expanded across the full 48 km world.
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

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "100000.0", ClampMax = "800000.0"))
    float TestAreaRadiusCm = 300000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "5000.0", ClampMax = "50000.0"))
    float SpawnAltitudeFeet = 20000.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0", ClampMax = "12000"))
    int32 TreeBudget = 3600;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0", ClampMax = "5000"))
    int32 ShrubBudget = 1000;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "0", ClampMax = "3000"))
    int32 RockBudget = 650;

    UPROPERTY(EditAnywhere, Category = "Aether|Environment Test", meta = (ClampMin = "1"))
    int32 EnvironmentSeed = 260804;

private:
    UHierarchicalInstancedStaticMeshComponent* CreateScatterComponent(
        FName Name, int32 StartCullDistance, int32 EndCullDistance);
    void PositionPlayerAboveTestArea();
    void BuildTestArea();
    bool SampleTerrain(float X, float Y, FVector& OutLocation, FVector& OutNormal) const;
    bool ReserveCell(TSet<uint64>& Cells, float X, float Y, float CellSize) const;
    TArray<UStaticMesh*> LoadLargestMeshes(const TArray<FName>& Paths, int32 MaxMeshes) const;
    UStaticMesh* LoadFirstKeywordMesh(const TArray<FName>& Paths, const TArray<FString>& Keywords) const;
    float ScaleForDesiredHeight(const UStaticMesh* Mesh, float DesiredHeightCm) const;
    void ReportResult(int32 TreesPlaced, int32 ShrubsPlaced, int32 RocksPlaced) const;

    FTimerHandle PositionTimer;
    FTimerHandle BuildTimer;
    int32 PositionAttempts = 0;
    int32 BuildAttempts = 0;
};
