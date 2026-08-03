#include "CinematicFlightPawn.h"

#include "Camera/CameraComponent.h"
#include "Components/BoxComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Engine/Engine.h"
#include "Engine/StaticMesh.h"
#include "GameFramework/SpringArmComponent.h"
#include "KismetProceduralMeshLibrary.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "ProceduralWorldDirector.h"
#include "UObject/ConstructorHelpers.h"

ACinematicFlightPawn::ACinematicFlightPawn()
{
    PrimaryActorTick.bCanEverTick = true;

    PhysicsBody = CreateDefaultSubobject<UBoxComponent>(TEXT("PhysicsBody"));
    SetRootComponent(PhysicsBody);
    PhysicsBody->SetBoxExtent(FVector(610.0f, 430.0f, 90.0f));
    PhysicsBody->SetCollisionProfileName(TEXT("PhysicsActor"));
    PhysicsBody->SetSimulatePhysics(true);
    PhysicsBody->SetEnableGravity(true);
    PhysicsBody->SetLinearDamping(0.015f);
    PhysicsBody->SetAngularDamping(0.55f);
    PhysicsBody->SetHiddenInGame(true);

    AirframeMesh = CreateDefaultSubobject<UStaticMeshComponent>(TEXT("ImportedAirframe"));
    AirframeMesh->SetupAttachment(PhysicsBody);
    AirframeMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    AirframeMesh->SetRelativeScale3D(FVector(2.0f));

    FallbackAirframe = CreateDefaultSubobject<UProceduralMeshComponent>(TEXT("FallbackAirframe"));
    FallbackAirframe->SetupAttachment(PhysicsBody);
    FallbackAirframe->SetCollisionEnabled(ECollisionEnabled::NoCollision);

    CockpitAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("CockpitAnchor"));
    CockpitAnchor->SetupAttachment(PhysicsBody);
    CockpitAnchor->SetRelativeLocation(FVector(145.0f, 0.0f, 88.0f));

    CockpitCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("CockpitCamera"));
    CockpitCamera->SetupAttachment(CockpitAnchor);
    CockpitCamera->FieldOfView = 88.0f;
    CockpitCamera->bUsePawnControlRotation = false;

    ChaseArm = CreateDefaultSubobject<USpringArmComponent>(TEXT("ChaseArm"));
    ChaseArm->SetupAttachment(PhysicsBody);
    ChaseArm->TargetArmLength = 1450.0f;
    ChaseArm->SocketOffset = FVector(0.0f, 0.0f, 220.0f);
    ChaseArm->bEnableCameraLag = true;
    ChaseArm->CameraLagSpeed = 5.5f;
    ChaseArm->CameraLagMaxDistance = 380.0f;
    ChaseArm->bEnableCameraRotationLag = true;
    ChaseArm->CameraRotationLagSpeed = 6.0f;
    ChaseArm->bDoCollisionTest = true;

    ChaseCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("ChaseCamera"));
    ChaseCamera->SetupAttachment(ChaseArm, USpringArmComponent::SocketName);
    ChaseCamera->FieldOfView = 78.0f;
    ChaseCamera->PostProcessSettings.bOverride_MotionBlurAmount = true;
    ChaseCamera->PostProcessSettings.MotionBlurAmount = 0.35f;

    WingAnchor = CreateDefaultSubobject<USceneComponent>(TEXT("WingAnchor"));
    WingAnchor->SetupAttachment(PhysicsBody);
    WingAnchor->SetRelativeLocation(FVector(-160.0f, 560.0f, 80.0f));
    WingAnchor->SetRelativeRotation(FRotator(-5.0f, -5.0f, 0.0f));

    WingCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("WingCamera"));
    WingCamera->SetupAttachment(WingAnchor);
    WingCamera->FieldOfView = 92.0f;

    CinematicCamera = CreateDefaultSubobject<UCameraComponent>(TEXT("CinematicCamera"));
    CinematicCamera->SetupAttachment(PhysicsBody);
    CinematicCamera->FieldOfView = 58.0f;
    CinematicCamera->PostProcessSettings.bOverride_MotionBlurAmount = true;
    CinematicCamera->PostProcessSettings.MotionBlurAmount = 0.38f;
    CinematicCamera->PostProcessSettings.bOverride_DepthOfFieldFocalDistance = true;
    CinematicCamera->PostProcessSettings.DepthOfFieldFocalDistance = 1850.0f;
    CinematicCamera->PostProcessSettings.bOverride_DepthOfFieldFstop = true;
    CinematicCamera->PostProcessSettings.DepthOfFieldFstop = 4.0f;
    CinematicCamera->PostProcessSettings.bOverride_DepthOfFieldSensorWidth = true;
    CinematicCamera->PostProcessSettings.DepthOfFieldSensorWidth = 35.0f;
}

void ACinematicFlightPawn::BeginPlay()
{
    Super::BeginPlay();
    PhysicsBody->SetMassOverrideInKg(NAME_None, AircraftMassKg, true);
    LoadImportedAirframe();
    if (!bHasImportedAirframe)
    {
        BuildFallbackAirframe();
    }
    ActivateCamera(CameraMode);
    PreviousVelocity = PhysicsBody->GetPhysicsLinearVelocity();
}

void ACinematicFlightPawn::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    ApplyAerodynamics(FMath::Clamp(DeltaSeconds, 0.001f, 0.05f));
    UpdateCamera(DeltaSeconds);

    const FVector Velocity = PhysicsBody->GetPhysicsLinearVelocity();
    if (DeltaSeconds > SMALL_NUMBER)
    {
        const FVector Acceleration = (Velocity - PreviousVelocity) / DeltaSeconds;
        const float NormalG = FVector::DotProduct(Acceleration, GetActorUpVector()) / 980.665f + 1.0f;
        SmoothedGForce = FMath::FInterpTo(SmoothedGForce, NormalG, DeltaSeconds, 3.5f);
    }
    PreviousVelocity = Velocity;
}

void ACinematicFlightPawn::SetupPlayerInputComponent(UInputComponent* PlayerInputComponent)
{
    Super::SetupPlayerInputComponent(PlayerInputComponent);
    PlayerInputComponent->BindAxis(TEXT("Throttle"), this, &ACinematicFlightPawn::InputThrottle);
    PlayerInputComponent->BindAxis(TEXT("Pitch"), this, &ACinematicFlightPawn::InputPitch);
    PlayerInputComponent->BindAxis(TEXT("Roll"), this, &ACinematicFlightPawn::InputRoll);
    PlayerInputComponent->BindAxis(TEXT("Yaw"), this, &ACinematicFlightPawn::InputYaw);
    PlayerInputComponent->BindAxis(TEXT("MouseX"), this, &ACinematicFlightPawn::InputMouseX);
    PlayerInputComponent->BindAxis(TEXT("MouseY"), this, &ACinematicFlightPawn::InputMouseY);
    PlayerInputComponent->BindAction(TEXT("FreeLook"), IE_Pressed, this, &ACinematicFlightPawn::BeginFreeLook);
    PlayerInputComponent->BindAction(TEXT("FreeLook"), IE_Released, this, &ACinematicFlightPawn::EndFreeLook);
    PlayerInputComponent->BindAction(TEXT("CycleCamera"), IE_Pressed, this, &ACinematicFlightPawn::CycleCamera);
    PlayerInputComponent->BindAction(TEXT("CinematicCamera"), IE_Pressed, this, &ACinematicFlightPawn::ToggleCinematicCamera);
    PlayerInputComponent->BindAction(TEXT("CycleWeather"), IE_Pressed, this, &ACinematicFlightPawn::CycleWeather);
    PlayerInputComponent->BindAction(TEXT("ResetAircraft"), IE_Pressed, this, &ACinematicFlightPawn::ResetAircraft);
}

void ACinematicFlightPawn::ResetAircraft()
{
    FTransform SpawnTransform(FRotator(0.0f, 0.0f, 0.0f), FVector(-650000.0f, -900000.0f, 85000.0f));
    if (AProceduralWorldDirector* Director = AProceduralWorldDirector::Find(GetWorld()))
    {
        SpawnTransform = Director->GetFlightSpawnTransform();
    }

    PhysicsBody->SetPhysicsLinearVelocity(FVector::ZeroVector);
    PhysicsBody->SetPhysicsAngularVelocityInRadians(FVector::ZeroVector);
    SetActorTransform(SpawnTransform, false, nullptr, ETeleportType::TeleportPhysics);
    PhysicsBody->SetPhysicsLinearVelocity(GetActorForwardVector() * 15500.0f);
    Throttle = 0.72f;
}

float ACinematicFlightPawn::GetAirspeedKnots() const
{
    return PhysicsBody->GetPhysicsLinearVelocity().Size() * 0.0194384f;
}

float ACinematicFlightPawn::GetAltitudeFeet() const
{
    return GetActorLocation().Z * 0.0328084f;
}

float ACinematicFlightPawn::GetMach() const
{
    return (PhysicsBody->GetPhysicsLinearVelocity().Size() * 0.01f) / 343.0f;
}

FString ACinematicFlightPawn::GetCameraModeName() const
{
    switch (CameraMode)
    {
    case EFlightCameraMode::Cockpit: return TEXT("COCKPIT");
    case EFlightCameraMode::Chase: return TEXT("CHASE");
    case EFlightCameraMode::Wing: return TEXT("WING");
    case EFlightCameraMode::Cinematic: return TEXT("CINEMATIC");
    default: return TEXT("UNKNOWN");
    }
}

void ACinematicFlightPawn::ApplyAerodynamics(const float DeltaSeconds)
{
    const FVector VelocityCm = PhysicsBody->GetPhysicsLinearVelocity();
    const float SpeedMps = VelocityCm.Size() * 0.01f;
    if (SpeedMps < 0.5f)
    {
        return;
    }

    const FVector LocalVelocityMps = GetActorTransform().InverseTransformVectorNoScale(VelocityCm) * 0.01f;
    const float AltitudeMeters = FMath::Max(0.0f, GetActorLocation().Z * 0.01f);
    const float AirDensity = 1.225f * FMath::Exp(-AltitudeMeters / 8500.0f);
    const float DynamicPressure = 0.5f * AirDensity * FMath::Square(SpeedMps);
    const float AngleOfAttack = FMath::Atan2(-LocalVelocityMps.Z, FMath::Max(1.0f, LocalVelocityMps.X));
    const float SideSlip = FMath::Atan2(LocalVelocityMps.Y, FMath::Max(1.0f, LocalVelocityMps.X));

    float LiftCoefficient = LiftSlopePerRadian * AngleOfAttack + 0.18f;
    const float AbsAoADegrees = FMath::Abs(FMath::RadiansToDegrees(AngleOfAttack));
    if (AbsAoADegrees > 17.0f)
    {
        const float StallBlend = FMath::Clamp((AbsAoADegrees - 17.0f) / 18.0f, 0.0f, 1.0f);
        LiftCoefficient *= FMath::Lerp(1.0f, 0.28f, StallBlend);
    }
    LiftCoefficient = FMath::Clamp(LiftCoefficient, -1.35f, 1.65f);

    const float DragCoefficient = ZeroLiftDrag + InducedDragFactor * FMath::Square(LiftCoefficient)
        + FMath::Square(SideSlip) * 0.65f;
    const float LiftNewtons = DynamicPressure * WingAreaSquareMeters * LiftCoefficient;
    const float DragNewtons = DynamicPressure * WingAreaSquareMeters * DragCoefficient;
    const float ThrustNewtons = MaximumThrustNewtons * Throttle * FMath::Lerp(1.0f, 0.72f, FMath::Clamp(AltitudeMeters / 16000.0f, 0.0f, 1.0f));
    const float SideForceNewtons = -DynamicPressure * WingAreaSquareMeters * SideSlip * 0.85f;

    FVector Force = GetActorUpVector() * LiftNewtons;
    Force += -VelocityCm.GetSafeNormal() * DragNewtons;
    Force += GetActorForwardVector() * ThrustNewtons;
    Force += GetActorRightVector() * SideForceNewtons;

    if (const AProceduralWorldDirector* Director = AProceduralWorldDirector::Find(GetWorld()))
    {
        Force += Director->GetTurbulenceForce(GetActorLocation(), GetWorld()->GetTimeSeconds(), AircraftMassKg);
    }
    PhysicsBody->AddForce(Force * 100.0f);

    const float Authority = FMath::Clamp(DynamicPressure / 4500.0f, 0.12f, 2.2f);
    const FVector AngularVelocityLocal = GetActorTransform().InverseTransformVectorNoScale(PhysicsBody->GetPhysicsAngularVelocityInRadians());
    FVector LocalTorque;
    LocalTorque.X = (RollInput + MouseFlightX) * 560000.0f * Authority - AngularVelocityLocal.X * 190000.0f;
    LocalTorque.Y = -(PitchInput + MouseFlightY) * 720000.0f * Authority - AngularVelocityLocal.Y * 250000.0f;
    LocalTorque.Z = YawInput * 320000.0f * Authority - AngularVelocityLocal.Z * 150000.0f;
    PhysicsBody->AddTorqueInRadians(GetActorTransform().TransformVectorNoScale(LocalTorque) * 10000.0f);
}

void ACinematicFlightPawn::UpdateCamera(const float DeltaSeconds)
{
    const float SpeedAlpha = FMath::Clamp((GetAirspeedKnots() - 180.0f) / 650.0f, 0.0f, 1.0f);
    ChaseCamera->SetFieldOfView(FMath::FInterpTo(ChaseCamera->FieldOfView, FMath::Lerp(76.0f, 92.0f, SpeedAlpha), DeltaSeconds, 2.2f));

    if (bFreeLook)
    {
        CockpitAnchor->SetRelativeRotation(FRotator(LookPitch, LookYaw, 0.0f));
    }
    else
    {
        LookYaw = FMath::FInterpTo(LookYaw, 0.0f, DeltaSeconds, 4.0f);
        LookPitch = FMath::FInterpTo(LookPitch, 0.0f, DeltaSeconds, 4.0f);
        CockpitAnchor->SetRelativeRotation(FRotator(LookPitch, LookYaw, 0.0f));
    }

    if (CameraMode == EFlightCameraMode::Cinematic)
    {
        CinematicTime += DeltaSeconds;
        const float Orbit = CinematicTime * 0.24f;
        const FVector LocalOffset(-500.0f + FMath::Cos(Orbit) * 1650.0f, FMath::Sin(Orbit) * 1800.0f,
            420.0f + FMath::Sin(Orbit * 0.55f) * 260.0f);
        const FVector CameraLocation = GetActorTransform().TransformPosition(LocalOffset);
        CinematicCamera->SetWorldLocation(CameraLocation);
        CinematicCamera->SetWorldRotation((GetActorLocation() - CameraLocation).Rotation());
        CinematicCamera->PostProcessSettings.DepthOfFieldFocalDistance =
            FMath::FInterpTo(CinematicCamera->PostProcessSettings.DepthOfFieldFocalDistance,
                FVector::Distance(CameraLocation, GetActorLocation()), DeltaSeconds, 3.0f);
    }
}

void ACinematicFlightPawn::ActivateCamera(const EFlightCameraMode NewMode)
{
    CameraMode = NewMode;
    CockpitCamera->SetActive(NewMode == EFlightCameraMode::Cockpit);
    ChaseCamera->SetActive(NewMode == EFlightCameraMode::Chase);
    WingCamera->SetActive(NewMode == EFlightCameraMode::Wing);
    CinematicCamera->SetActive(NewMode == EFlightCameraMode::Cinematic);
}

void ACinematicFlightPawn::InputThrottle(const float Value)
{
    Throttle = FMath::Clamp(Throttle + Value * GetWorld()->GetDeltaSeconds() * 0.36f, 0.0f, 1.0f);
}

void ACinematicFlightPawn::InputPitch(const float Value)
{
    const float Direction = bInvertPitchControl ? -1.0f : 1.0f;
    PitchInput = FMath::Clamp(Value * Direction, -1.0f, 1.0f);
}

void ACinematicFlightPawn::InputRoll(const float Value)
{
    const float Direction = bInvertRollControl ? -1.0f : 1.0f;
    RollInput = FMath::Clamp(Value * Direction, -1.0f, 1.0f);
}

void ACinematicFlightPawn::InputYaw(const float Value)
{
    const float Direction = bInvertYawControl ? -1.0f : 1.0f;
    YawInput = FMath::Clamp(Value * Direction, -1.0f, 1.0f);
}

void ACinematicFlightPawn::InputMouseX(const float Value)
{
    if (bFreeLook)
    {
        LookYaw = FMath::Clamp(LookYaw + Value * 1.8f, -145.0f, 145.0f);
        MouseFlightX = 0.0f;
    }
    else
    {
        const float Direction = bInvertRollControl ? -1.0f : 1.0f;
        MouseFlightX = FMath::Clamp(Value * 0.09f * Direction, -0.75f, 0.75f);
    }
}

void ACinematicFlightPawn::InputMouseY(const float Value)
{
    if (bFreeLook)
    {
        LookPitch = FMath::Clamp(LookPitch + Value * 1.5f, -75.0f, 75.0f);
        MouseFlightY = 0.0f;
    }
    else
    {
        const float Direction = bInvertPitchControl ? -1.0f : 1.0f;
        MouseFlightY = FMath::Clamp(-Value * 0.08f * Direction, -0.7f, 0.7f);
    }
}

void ACinematicFlightPawn::BeginFreeLook() { bFreeLook = true; }
void ACinematicFlightPawn::EndFreeLook() { bFreeLook = false; }

void ACinematicFlightPawn::CycleCamera()
{
    if (CameraMode == EFlightCameraMode::Cinematic)
    {
        ActivateCamera(EFlightCameraMode::Chase);
        return;
    }
    const uint8 Next = (static_cast<uint8>(CameraMode) + 1) % 3;
    ActivateCamera(static_cast<EFlightCameraMode>(Next));
}

void ACinematicFlightPawn::ToggleCinematicCamera()
{
    ActivateCamera(CameraMode == EFlightCameraMode::Cinematic ? EFlightCameraMode::Chase : EFlightCameraMode::Cinematic);
}

void ACinematicFlightPawn::CycleWeather()
{
    if (AProceduralWorldDirector* Director = AProceduralWorldDirector::Find(GetWorld()))
    {
        Director->CycleWeather();
    }
}

void ACinematicFlightPawn::BuildFallbackAirframe()
{
    TArray<FVector> V = {
        FVector(620, 0, 0), FVector(80, -455, -5), FVector(-500, -250, -15), FVector(-610, -90, 5),
        FVector(-610, 90, 5), FVector(-500, 250, -15), FVector(80, 455, -5), FVector(180, 0, 115),
        FVector(-260, 0, 85), FVector(110, 0, -70)
    };
    TArray<int32> T = {
        0,1,7, 0,7,6, 1,2,8, 1,8,7, 7,8,6, 6,8,5, 2,3,8, 3,4,8, 4,5,8,
        0,9,1, 0,6,9, 1,9,2, 2,9,3, 3,9,4, 4,9,5, 5,9,6
    };
    TArray<FVector> Normals;
    TArray<FVector2D> UV;
    TArray<FProcMeshTangent> Tangents;
    TArray<FLinearColor> Colors;
    UV.Init(FVector2D::ZeroVector, V.Num());
    Colors.Init(FLinearColor(0.055f, 0.075f, 0.085f, 1.0f), V.Num());
    UKismetProceduralMeshLibrary::CalculateTangentsForMesh(V, T, UV, Normals, Tangents);
    FallbackAirframe->CreateMeshSection_LinearColor(0, V, T, Normals, UV, Colors, Tangents, false);

    if (UMaterialInterface* Material = LoadObject<UMaterialInterface>(nullptr,
        TEXT("/Engine/EngineMaterials/DefaultMaterial.DefaultMaterial")))
    {
        FallbackAirframe->SetMaterial(0, Material);
    }
}

void ACinematicFlightPawn::LoadImportedAirframe()
{
    UStaticMesh* ImportedMesh = LoadObject<UStaticMesh>(nullptr,
        TEXT("/Game/Aircraft/StealthDrone/SM_StealthDrone.SM_StealthDrone"));
    if (ImportedMesh)
    {
        AirframeMesh->SetStaticMesh(ImportedMesh);
        AirframeMesh->SetVisibility(true);
        FallbackAirframe->SetVisibility(false);
        bHasImportedAirframe = true;
    }
    else
    {
        AirframeMesh->SetVisibility(false);
        FallbackAirframe->SetVisibility(true);
        if (GEngine)
        {
            GEngine->AddOnScreenDebugMessage(-1, 12.0f, FColor(120, 220, 255),
                TEXT("AETHER: run Content/Python/ImportStealthDrone.py once to install the supplied high-detail airframe."));
        }
    }
}
