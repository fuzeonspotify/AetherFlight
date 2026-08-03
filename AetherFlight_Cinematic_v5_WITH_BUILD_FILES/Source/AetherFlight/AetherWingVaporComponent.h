#pragma once

#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "AetherWingVaporComponent.generated.h"

class ACinematicFlightPawn;
class UMaterialInterface;
class UProceduralMeshComponent;
struct FProcMeshTangent;

struct FAetherVaporTrailSample
{
    FVector LeftWorld = FVector::ZeroVector;
    FVector RightWorld = FVector::ZeroVector;
    FVector UpWorld = FVector::UpVector;
    FVector RightAxisWorld = FVector::RightVector;
    float Age = 0.0f;
    float Strength = 0.0f;
};

/**
 * Aerodynamic condensation for high-load manoeuvres.
 * Builds a thin pressure-vapour envelope over the wings and world-space,
 * rolling wingtip vortex tubes. The trail history stays behind the aircraft
 * instead of appearing as camera-facing ribbons attached to it.
 */
UCLASS(ClassGroup = (Aether), meta = (BlueprintSpawnableComponent))
class AETHERFLIGHT_API UAetherWingVaporComponent : public UActorComponent
{
    GENERATED_BODY()

public:
    UAetherWingVaporComponent();

    virtual void BeginPlay() override;
    virtual void TickComponent(
        float DeltaTime,
        ELevelTick TickType,
        FActorComponentTickFunction* ThisTickFunction) override;

protected:
    UPROPERTY(EditAnywhere, Category = "Aether|Condensation")
    bool bEnableWingCondensation = true;

    UPROPERTY(EditAnywhere, Category = "Aether|Condensation", meta = (ClampMin = "1.0", ClampMax = "9.0"))
    float CondensationOnsetG = 2.25f;

    UPROPERTY(EditAnywhere, Category = "Aether|Condensation", meta = (ClampMin = "2.0", ClampMax = "12.0"))
    float FullCondensationG = 6.25f;

    UPROPERTY(EditAnywhere, Category = "Aether|Condensation", meta = (ClampMin = "60.0", ClampMax = "500.0"))
    float MinimumAirspeedKnots = 185.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Condensation", meta = (ClampMin = "200.0", ClampMax = "1400.0"))
    float WingTipOffsetCentimeters = 835.0f;

    UPROPERTY(EditAnywhere, Category = "Aether|Condensation", meta = (ClampMin = "0.5", ClampMax = "5.0"))
    float TrailLifetimeSeconds = 1.18f;

private:
    UProceduralMeshComponent* CreateEffectMesh(FName Name);
    void BuildWingSheet(UProceduralMeshComponent* Mesh, float SideSign, float Intensity, float TimeSeconds);
    void UpdateTrailSamples(float DeltaTime, float Intensity);
    void BuildWingtipTrails();
    void AppendTrailTube(
        bool bLeft,
        TArray<FVector>& Vertices,
        TArray<int32>& Triangles,
        TArray<FVector>& Normals,
        TArray<FVector2D>& UVs,
        TArray<FLinearColor>& Colors,
        TArray<FProcMeshTangent>& Tangents) const;
    float CalculateTargetIntensity() const;
    void ClearVisuals();

    UPROPERTY(Transient)
    UProceduralMeshComponent* LeftWingSheet = nullptr;

    UPROPERTY(Transient)
    UProceduralMeshComponent* RightWingSheet = nullptr;

    UPROPERTY(Transient)
    UProceduralMeshComponent* WingtipTrails = nullptr;

    UPROPERTY(Transient)
    UMaterialInterface* VaporMaterial = nullptr;

    TWeakObjectPtr<ACinematicFlightPawn> FlightPawn;
    TArray<FAetherVaporTrailSample> TrailSamples;
    float VaporIntensity = 0.0f;
    float SampleAccumulator = 0.0f;
};
