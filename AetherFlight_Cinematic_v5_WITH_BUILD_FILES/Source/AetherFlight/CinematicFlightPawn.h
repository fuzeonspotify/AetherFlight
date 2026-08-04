#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Pawn.h"
#include "CinematicFlightPawn.generated.h"

class UAetherWingVaporComponent;
class UBoxComponent;
class UCameraComponent;
class UProceduralMeshComponent;
class USceneComponent;
class USpringArmComponent;
class UStaticMeshComponent;
class UWorldPartitionStreamingSourceComponent;

UENUM(BlueprintType)
enum class EFlightCameraMode : uint8
{
    Cockpit,
    Chase,
    Wing,
    Cinematic
};

UCLASS()
class AETHERFLIGHT_API ACinematicFlightPawn : public APawn
{
    GENERATED_BODY()

public:
    ACinematicFlightPawn();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;
    virtual void SetupPlayerInputComponent(UInputComponent* PlayerInputComponent) override;

    UFUNCTION(BlueprintCallable, Category = "Flight")
    void ResetAircraft();

    float GetAirspeedKnots() const;
    float GetAltitudeFeet() const;
    float GetMach() const;
    float GetThrottle() const { return Throttle; }
    float GetGForce() const { return SmoothedGForce; }
    float GetAngleOfAttackDegrees() const;
    FString GetCameraModeName() const;

protected:
    UPROPERTY(VisibleAnywhere, Category = "Aircraft|Effects")
    UAetherWingVaporComponent* WingVapor;

    UPROPERTY(VisibleAnywhere, Category = "Aircraft")
    UBoxComponent* PhysicsBody;

    UPROPERTY(VisibleAnywhere, Category = "Aircraft")
    UStaticMeshComponent* AirframeMesh;

    UPROPERTY(VisibleAnywhere, Category = "Aircraft")
    UProceduralMeshComponent* FallbackAirframe;

    UPROPERTY(VisibleAnywhere, Category = "World Partition")
    UWorldPartitionStreamingSourceComponent* FlightStreamingSource;

    UPROPERTY(EditAnywhere, Category = "World Partition", meta = (ClampMin = "0.0", ClampMax = "10.0"))
    float InitialStreamingMinimumWaitSeconds = 1.5f;

    UPROPERTY(EditAnywhere, Category = "World Partition", meta = (ClampMin = "1.0", ClampMax = "30.0"))
    float InitialStreamingMaximumWaitSeconds = 8.0f;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    USceneComponent* CockpitAnchor;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    UCameraComponent* CockpitCamera;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    USpringArmComponent* ChaseArm;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    UCameraComponent* ChaseCamera;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    USceneComponent* WingAnchor;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    UCameraComponent* WingCamera;

    UPROPERTY(VisibleAnywhere, Category = "Camera")
    UCameraComponent* CinematicCamera;

    UPROPERTY(EditAnywhere, Category = "Flight|Spawn", meta = (ClampMin = "1000.0", ClampMax = "50000.0"))
    float SpawnAltitudeFeet = 20000.0f;

    UPROPERTY(EditAnywhere, Category = "Flight|Airframe", meta = (ClampMin = "1000.0"))
    float AircraftMassKg = 8500.0f;

    UPROPERTY(EditAnywhere, Category = "Flight|Airframe")
    float WingAreaSquareMeters = 42.0f;

    UPROPERTY(EditAnywhere, Category = "Flight|Engine")
    float MaximumThrustNewtons = 128000.0f;

    UPROPERTY(EditAnywhere, Category = "Flight|Aero")
    float LiftSlopePerRadian = 4.4f;

    UPROPERTY(EditAnywhere, Category = "Flight|Aero")
    float ZeroLiftDrag = 0.024f;

    UPROPERTY(EditAnywhere, Category = "Flight|Aero")
    float InducedDragFactor = 0.11f;

    // Directional controls default to the player's preferred reversed layout.
    // These remain editable on derived pawn defaults without changing throttle or free-look.
    UPROPERTY(EditAnywhere, Category = "Flight|Controls")
    bool bInvertPitchControl = true;

    UPROPERTY(EditAnywhere, Category = "Flight|Controls")
    bool bInvertRollControl = true;

    UPROPERTY(EditAnywhere, Category = "Flight|Controls")
    bool bInvertYawControl = true;

private:
    void BuildFallbackAirframe();
    void LoadImportedAirframe();
    void ApplyAerodynamics(float DeltaSeconds);
    void UpdateCamera(float DeltaSeconds);
    void ActivateCamera(EFlightCameraMode NewMode);
    void ReleaseAircraftAfterStreaming();

    void InputThrottle(float Value);
    void InputPitch(float Value);
    void InputRoll(float Value);
    void InputYaw(float Value);
    void InputMouseX(float Value);
    void InputMouseY(float Value);
    void BeginFreeLook();
    void EndFreeLook();
    void CycleCamera();
    void ToggleCinematicCamera();
    void CycleWeather();

    float Throttle = 0.72f;
    float PitchInput = 0.0f;
    float RollInput = 0.0f;
    float YawInput = 0.0f;
    float MouseFlightX = 0.0f;
    float MouseFlightY = 0.0f;
    float LookYaw = 0.0f;
    float LookPitch = 0.0f;
    float SmoothedGForce = 1.0f;
    FVector PreviousVelocity = FVector::ZeroVector;
    bool bFreeLook = false;
    bool bHasImportedAirframe = false;
    bool bWaitingForInitialStreaming = false;
    float InitialStreamingWaitElapsed = 0.0f;
    float CinematicTime = 0.0f;
    EFlightCameraMode CameraMode = EFlightCameraMode::Chase;
};
