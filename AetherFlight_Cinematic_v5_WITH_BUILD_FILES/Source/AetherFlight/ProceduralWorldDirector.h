#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProceduralWorldDirector.generated.h"

class UDirectionalLightComponent;
class UExponentialHeightFogComponent;
class UHierarchicalInstancedStaticMeshComponent;
class UMaterialInstanceDynamic;
class UPostProcessComponent;
class UProceduralMeshComponent;
class USceneComponent;
class USkyAtmosphereComponent;
class USkyLightComponent;
class UStaticMeshComponent;
class UVolumetricCloudComponent;

UENUM(BlueprintType)
enum class EAetherWeather : uint8
{
    GoldenClear,
    BrokenClouds,
    StormFront,
    BlueHour
};

UCLASS()
class AETHERFLIGHT_API AProceduralWorldDirector : public AActor
{
    GENERATED_BODY()

public:
    AProceduralWorldDirector();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

    UFUNCTION(BlueprintCallable, Category = "World")
    void EnsureWorldGenerated();

    UFUNCTION(BlueprintCallable, Category = "Weather")
    void CycleWeather();

    UFUNCTION(BlueprintPure, Category = "World")
    FTransform GetFlightSpawnTransform() const;

    FVector GetTurbulenceForce(const FVector& WorldLocation, float TimeSeconds, float MassKg) const;
    float GetCondensationHumidity() const;

    static AProceduralWorldDirector* Find(UWorld* World);

protected:
    UPROPERTY(VisibleAnywhere, Category = "World")
    USceneComponent* Root;

    UPROPERTY(VisibleAnywhere, Category = "World")
    UProceduralMeshComponent* Terrain;

    UPROPERTY(VisibleAnywhere, Category = "World")
    UProceduralMeshComponent* Ocean;

    UPROPERTY(Transient)
    UMaterialInstanceDynamic* OceanMaterialInstance = nullptr;

    UPROPERTY(VisibleAnywhere, Category = "World")
    UStaticMeshComponent* Runway;

    UPROPERTY(VisibleAnywhere, Category = "World")
    UProceduralMeshComponent* RunwayMarkings;

    UPROPERTY(VisibleAnywhere, Category = "World")
    UHierarchicalInstancedStaticMeshComponent* ForestInstances;

    UPROPERTY(VisibleAnywhere, Category = "World")
    UHierarchicalInstancedStaticMeshComponent* RockInstances;

    UPROPERTY(VisibleAnywhere, Category = "Atmosphere")
    UDirectionalLightComponent* Sun;

    UPROPERTY(VisibleAnywhere, Category = "Atmosphere")
    USkyLightComponent* SkyLight;

    UPROPERTY(VisibleAnywhere, Category = "Atmosphere")
    USkyAtmosphereComponent* SkyAtmosphere;

    UPROPERTY(VisibleAnywhere, Category = "Atmosphere")
    UExponentialHeightFogComponent* HeightFog;

    UPROPERTY(VisibleAnywhere, Category = "Atmosphere")
    UVolumetricCloudComponent* VolumetricClouds;

    UPROPERTY(VisibleAnywhere, Category = "Atmosphere")
    UPostProcessComponent* PostProcess;

    UPROPERTY(EditAnywhere, Category = "World", meta = (ClampMin = "1"))
    int32 WorldSeed = 1847;

    UPROPERTY(EditAnywhere, Category = "World", meta = (ClampMin = "2", ClampMax = "16"))
    int32 TerrainTilesPerAxis = 8;

    UPROPERTY(EditAnywhere, Category = "World", meta = (ClampMin = "17", ClampMax = "129"))
    int32 TerrainTileResolution = 65;

    UPROPERTY(EditAnywhere, Category = "World")
    float TerrainSizeKilometers = 48.0f;

    UPROPERTY(EditAnywhere, Category = "Weather")
    EAetherWeather Weather = EAetherWeather::BrokenClouds;

    UPROPERTY(EditAnywhere, Category = "World|Detail", meta = (ClampMin = "0", ClampMax = "20000"))
    int32 ForestInstanceBudget = 6500;

    UPROPERTY(EditAnywhere, Category = "World|Detail", meta = (ClampMin = "0", ClampMax = "5000"))
    int32 RockInstanceBudget = 1800;

private:
    void GenerateTerrain();
    void GenerateOcean();
    void UpdateOceanSurface(float DeltaSeconds);
    void GenerateRunwayMarkings();
    void GenerateEnvironmentInstances();
    void ConfigureAtmosphere();
    void ApplyWeather(EAetherWeather NewWeather, bool bInstant);
    bool HasProductionLandscape() const;
    bool HasAuthoredWater() const;
    bool SampleGround(float XCentimeters, float YCentimeters, float& OutHeightMeters, FVector& OutNormal) const;
    float TerrainHeightMeters(float XCentimeters, float YCentimeters) const;
    float RawTerrainHeightMeters(float XMeters, float YMeters) const;
    float FractalNoise(float X, float Y, int32 Octaves, float Persistence) const;
    float ValueNoise(float X, float Y) const;
    float HashNoise(int32 X, int32 Y) const;
    FVector TerrainNormal(float XCentimeters, float YCentimeters, float SampleDistanceCentimeters) const;
    FLinearColor TerrainBiomeColor(float HeightMeters, float Slope, float XCentimeters, float YCentimeters) const;

    bool bGenerated = false;
    bool bUsingProductionLandscape = false;
    float CurrentStorminess = 0.0f;
    float TargetStorminess = 0.0f;
    float CurrentSeaState = 0.68f;
    float TargetSeaState = 0.68f;
    float CurrentOceanRoughness = 0.075f;
    float TargetOceanRoughness = 0.075f;
    float CurrentFoamAmount = 0.18f;
    float TargetFoamAmount = 0.18f;
    float TargetFogDensity = 0.002f;
    float TargetSunIntensity = 7.0f;
    FLinearColor TargetSunColor = FLinearColor::White;
    FRotator TargetSunRotation = FRotator(-25.0f, -35.0f, 0.0f);
    FVector AirbaseLocation = FVector(-650000.0f, -900000.0f, 0.0f);
    float AirbaseElevationMeters = 115.0f;
};
