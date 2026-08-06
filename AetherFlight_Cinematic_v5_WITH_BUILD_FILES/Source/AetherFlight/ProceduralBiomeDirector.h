#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "ProceduralBiomeDirector.generated.h"

class UHierarchicalInstancedStaticMeshComponent;
class USceneComponent;
class UStaticMesh;

USTRUCT(BlueprintType)
struct FProceduralBiomeMesh
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    TObjectPtr<UStaticMesh> Mesh = nullptr;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0"))
    float Weight = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    FVector2D UniformScaleRange = FVector2D(0.85f, 1.25f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    float ZOffsetCentimeters = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    bool bAlignToSurface = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    bool bRandomYaw = true;
};

USTRUCT(BlueprintType)
struct FProceduralBiomeDefinition
{
    GENERATED_BODY()

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    FName BiomeName = NAME_None;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    bool bEnabled = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    float MinElevationMeters = -1000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    float MaxElevationMeters = 5000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float MinMoisture = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float MaxMoisture = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float MinTemperature = 0.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float MaxTemperature = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float MinGroundNormalZ = 0.65f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float Density = 0.35f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float Patchiness = 0.45f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome", meta = (ClampMin = "0.01"))
    float Priority = 1.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Biome")
    TArray<FProceduralBiomeMesh> Meshes;
};

UCLASS()
class AETHERFLIGHT_API AProceduralBiomeDirector : public AActor
{
    GENERATED_BODY()

public:
    AProceduralBiomeDirector();

    virtual void BeginPlay() override;

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Aether|Biomes")
    void BuildBiomes();

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Aether|Biomes")
    void ClearBiomes();

    UFUNCTION(BlueprintCallable, CallInEditor, Category = "Aether|Biomes")
    void ResetDefaultBiomes();

protected:
    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Aether|Biomes")
    TObjectPtr<USceneComponent> Root;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    int32 Seed = 1847;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    FVector2D WorldCenterCentimeters = FVector2D::ZeroVector;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    FVector2D WorldHalfExtentCentimeters = FVector2D(2400000.0f, 2400000.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation", meta = (ClampMin = "0", ClampMax = "250000"))
    int32 SampleCount = 32000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    float TraceTopZ = 1000000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    float TraceBottomZ = -300000.0f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    bool bRequireLandscapeHitWhenLandscapeExists = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Generation")
    bool bBuildOnBeginPlay = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Compatibility")
    bool bDisableLegacyForestAndRocks = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Exclusion")
    bool bProtectAirbase = true;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Exclusion")
    FVector2D AirbaseCenterCentimeters = FVector2D(-650000.0f, -900000.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Exclusion")
    FVector2D AirbaseExclusionHalfExtentCentimeters = FVector2D(175000.0f, 22000.0f);

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Noise", meta = (ClampMin = "0.00000001"))
    float MoistureNoiseScale = 0.0000018f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Noise", meta = (ClampMin = "0.00000001"))
    float TemperatureNoiseScale = 0.0000012f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Noise", meta = (ClampMin = "0.00000001"))
    float PatchNoiseScale = 0.0000060f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Noise", meta = (ClampMin = "0.0", ClampMax = "1.0"))
    float ElevationCoolingPerKilometer = 0.18f;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Rendering", meta = (ClampMin = "0"))
    int32 StartCullDistance = 180000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes|Rendering", meta = (ClampMin = "0"))
    int32 EndCullDistance = 2200000;

    UPROPERTY(EditAnywhere, BlueprintReadWrite, Category = "Aether|Biomes")
    TArray<FProceduralBiomeDefinition> Biomes;

    UPROPERTY(VisibleAnywhere, BlueprintReadOnly, Category = "Aether|Biomes|Status")
    int32 LastGeneratedInstanceCount = 0;

private:
    void BuildRuntimeBiomes();
    void DisableLegacyEnvironment();
    bool HasLandscape() const;
    bool TraceGround(float X, float Y, bool bLandscapeExists, FVector& OutLocation, FVector& OutNormal) const;
    float BiomeScore(
        const FProceduralBiomeDefinition& Biome,
        float ElevationMeters,
        float Moisture,
        float Temperature,
        float GroundNormalZ) const;
    const FProceduralBiomeMesh* ChooseMesh(
        const FProceduralBiomeDefinition& Biome,
        FRandomStream& Random) const;
    UHierarchicalInstancedStaticMeshComponent* GetOrCreateMeshComponent(
        UStaticMesh* Mesh,
        TMap<UStaticMesh*, UHierarchicalInstancedStaticMeshComponent*>& ComponentsByMesh);
    float FractalNoise(float X, float Y, int32 Octaves, float Persistence, int32 SeedOffset) const;
    float ValueNoise(float X, float Y, int32 SeedOffset) const;
    float HashNoise(int32 X, int32 Y, int32 SeedOffset) const;
    static FName GeneratedComponentTag();
};
