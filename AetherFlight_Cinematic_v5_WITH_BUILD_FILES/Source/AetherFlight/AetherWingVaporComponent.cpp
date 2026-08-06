#include "AetherWingVaporComponent.h"

#include "CinematicFlightPawn.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "ProceduralWorldDirector.h"

namespace AetherVapor
{
    constexpr int32 SpanSegments = 15;
    constexpr int32 ChordSegments = 9;
    constexpr int32 SheetLayers = 3;
    constexpr int32 TrailTubeSides = 8;
    constexpr float TrailSampleInterval = 0.034f;
}

UAetherWingVaporComponent::UAetherWingVaporComponent()
{
    PrimaryComponentTick.bCanEverTick = true;
    PrimaryComponentTick.TickGroup = TG_PostPhysics;
}

void UAetherWingVaporComponent::BeginPlay()
{
    Super::BeginPlay();
    FlightPawn = Cast<ACinematicFlightPawn>(GetOwner());
    if (!FlightPawn.IsValid())
    {
        SetComponentTickEnabled(false);
        return;
    }

    LeftWingSheet = CreateEffectMesh(TEXT("LeftWingCondensation"));
    RightWingSheet = CreateEffectMesh(TEXT("RightWingCondensation"));
    WingtipTrails = CreateEffectMesh(TEXT("WingtipVortexTrails"));

    VaporMaterial = LoadObject<UMaterialInterface>(
        nullptr, TEXT("/Game/Aether/Effects/M_WingCondensation.M_WingCondensation"));
    if (!VaporMaterial)
    {
        VaporMaterial = LoadObject<UMaterialInterface>(
            nullptr, TEXT("/Engine/EngineMaterials/DefaultParticle.DefaultParticle"));
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether Vapor] M_WingCondensation is missing. Run "
                 "Content/Python/InstallWingCondensationMaterial_UE58.py for the translucent material."));
    }

    for (UProceduralMeshComponent* Mesh : {LeftWingSheet, RightWingSheet, WingtipTrails})
    {
        if (Mesh && VaporMaterial)
        {
            Mesh->SetMaterial(0, VaporMaterial);
        }
    }
    UE_LOG(LogTemp, Display,
        TEXT("[Aether Vapor] Aerodynamic wing condensation is active (G-load, airspeed, AoA and humidity driven)."));
}

void UAetherWingVaporComponent::TickComponent(
    const float DeltaTime,
    const ELevelTick TickType,
    FActorComponentTickFunction* ThisTickFunction)
{
    Super::TickComponent(DeltaTime, TickType, ThisTickFunction);
    if (!bEnableWingCondensation || !FlightPawn.IsValid())
    {
        ClearVisuals();
        return;
    }

    const float TargetIntensity = CalculateTargetIntensity();
    const float ResponseSpeed = TargetIntensity > VaporIntensity ? 7.0f : 2.8f;
    VaporIntensity = FMath::FInterpTo(VaporIntensity, TargetIntensity, DeltaTime, ResponseSpeed);

    const float TimeSeconds = GetWorld() ? GetWorld()->GetTimeSeconds() : 0.0f;
    if (VaporIntensity > 0.012f)
    {
        BuildWingSheet(LeftWingSheet, -1.0f, VaporIntensity, TimeSeconds);
        BuildWingSheet(RightWingSheet, 1.0f, VaporIntensity, TimeSeconds);
    }
    else
    {
        if (LeftWingSheet) LeftWingSheet->SetVisibility(false);
        if (RightWingSheet) RightWingSheet->SetVisibility(false);
    }

    UpdateTrailSamples(DeltaTime, VaporIntensity);
    BuildWingtipTrails();
}

UProceduralMeshComponent* UAetherWingVaporComponent::CreateEffectMesh(const FName Name)
{
    AActor* Owner = GetOwner();
    if (!Owner || !Owner->GetRootComponent())
    {
        return nullptr;
    }

    UProceduralMeshComponent* Mesh = NewObject<UProceduralMeshComponent>(Owner, Name);
    Mesh->SetupAttachment(Owner->GetRootComponent());
    Mesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
    Mesh->SetCastShadow(false);
    Mesh->SetTranslucentSortPriority(12);
    Mesh->SetRelativeTransform(FTransform::Identity);
    Mesh->RegisterComponent();
    Mesh->SetVisibility(false);
    return Mesh;
}

float UAetherWingVaporComponent::CalculateTargetIntensity() const
{
    const ACinematicFlightPawn* Pawn = FlightPawn.Get();
    if (!Pawn)
    {
        return 0.0f;
    }

    // Positive lift creates the low-pressure region over the upper wing. Negative-G
    // manoeuvres would condense beneath the wing and are intentionally not mirrored here.
    const float LoadFactor = FMath::Max(0.0f, Pawn->GetGForce());
    const float GAlpha = FMath::SmoothStep(CondensationOnsetG, FullCondensationG, LoadFactor);
    if (GAlpha <= 0.0f)
    {
        return 0.0f;
    }

    const float SpeedAlpha = FMath::SmoothStep(
        MinimumAirspeedKnots, MinimumAirspeedKnots + 170.0f, Pawn->GetAirspeedKnots());
    const float AoAAlpha = FMath::SmoothStep(2.5f, 12.0f, FMath::Abs(Pawn->GetAngleOfAttackDegrees()));
    const float SupersonicFade = 1.0f - FMath::SmoothStep(1.12f, 1.55f, Pawn->GetMach());

    float Humidity = 0.68f;
    if (const AProceduralWorldDirector* Director = AProceduralWorldDirector::Find(GetWorld()))
    {
        Humidity = Director->GetCondensationHumidity();
    }
    const float HumidityAlpha = FMath::SmoothStep(0.18f, 0.92f, FMath::Clamp(Humidity, 0.0f, 1.0f));
    const float HumidityGain = FMath::Lerp(0.32f, 1.28f, HumidityAlpha);
    const float LiftDemand = FMath::Lerp(0.58f, 1.0f, AoAAlpha);
    const float PressureDrop = FMath::SmoothStep(
        CondensationOnsetG, FullCondensationG, LoadFactor * FMath::Lerp(0.82f, 1.18f, AoAAlpha));
    return FMath::Clamp(
        FMath::Max(GAlpha, PressureDrop) * SpeedAlpha * SupersonicFade * HumidityGain * LiftDemand,
        0.0f, 1.0f);
}

void UAetherWingVaporComponent::BuildWingSheet(
    UProceduralMeshComponent* Mesh,
    const float SideSign,
    const float Intensity,
    const float TimeSeconds)
{
    if (!Mesh)
    {
        return;
    }

    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FLinearColor> Colors;
    TArray<FProcMeshTangent> Tangents;
    const int32 VerticesPerLayer = AetherVapor::SpanSegments * AetherVapor::ChordSegments;
    Vertices.Reserve(VerticesPerLayer * AetherVapor::SheetLayers);
    Normals.Reserve(VerticesPerLayer * AetherVapor::SheetLayers);
    UVs.Reserve(VerticesPerLayer * AetherVapor::SheetLayers);
    Colors.Reserve(VerticesPerLayer * AetherVapor::SheetLayers);
    Tangents.Reserve(VerticesPerLayer * AetherVapor::SheetLayers);
    Triangles.Reserve(
        (AetherVapor::SpanSegments - 1) * (AetherVapor::ChordSegments - 1)
        * AetherVapor::SheetLayers * 6);

    for (int32 Layer = 0; Layer < AetherVapor::SheetLayers; ++Layer)
    {
        const int32 LayerStart = Vertices.Num();
        const float LayerT = static_cast<float>(Layer)
            / static_cast<float>(AetherVapor::SheetLayers - 1);
        const float LayerDistance = FMath::Abs(LayerT * 2.0f - 1.0f);
        const float LayerEnvelope = FMath::Lerp(0.56f, 1.0f, 1.0f - LayerDistance);
        // Keep the pressure cloud close to the lifting surface. The previous
        // 118 cm stack separated into obvious white lines when viewed edge-on.
        const float LayerOffsetZ = (LayerT - 0.5f) * 46.0f;

        for (int32 SpanIndex = 0; SpanIndex < AetherVapor::SpanSegments; ++SpanIndex)
        {
            const float Span = static_cast<float>(SpanIndex)
                / static_cast<float>(AetherVapor::SpanSegments - 1);
            const float LeadingX = FMath::Lerp(245.0f, -40.0f, Span);
            const float TrailingX = FMath::Lerp(-285.0f, -500.0f, Span);
            const float BaseY = SideSign * FMath::Lerp(135.0f, WingTipOffsetCentimeters, Span);
            const float SpanFade = FMath::Pow(
                FMath::Max(0.0f, FMath::Sin(Span * PI)), 0.30f);

            for (int32 ChordIndex = 0; ChordIndex < AetherVapor::ChordSegments; ++ChordIndex)
            {
                const float Chord = static_cast<float>(ChordIndex)
                    / static_cast<float>(AetherVapor::ChordSegments - 1);
                const float ChordEnvelope = FMath::Pow(
                    FMath::Max(0.0f, FMath::Sin(Chord * PI)), 0.42f);
                const float Turbulence = FMath::PerlinNoise2D(FVector2D(
                    Span * 5.3f + TimeSeconds * 0.31f + Layer * 0.71f,
                    Chord * 6.7f - TimeSeconds * 0.43f + SideSign * 11.0f));
                const float DensityNoise = FMath::Lerp(0.70f, 1.0f, Turbulence * 0.5f + 0.5f);
                const float Alpha = Intensity * SpanFade * ChordEnvelope
                    * LayerEnvelope * DensityNoise * 0.135f;
                const float Camber = FMath::Sin(Chord * PI)
                    * (24.0f + Intensity * 38.0f) + FMath::Sin(Span * PI) * 12.0f;
                const float Z = 64.0f + LayerOffsetZ + Camber
                    + Turbulence * (7.0f + Intensity * 11.0f);
                const float Y = BaseY + SideSign * Turbulence * 9.0f;
                const float X = FMath::Lerp(LeadingX, TrailingX, Chord)
                    + Turbulence * 8.0f;

                Vertices.Add(FVector(X, Y, Z));
                Normals.Add(FVector::UpVector);
                UVs.Add(FVector2D(Span * 2.4f + Layer * 0.17f, Chord));
                Colors.Add(FLinearColor(0.94f, 0.975f, 1.0f, Alpha));
                Tangents.Add(FProcMeshTangent(FVector::ForwardVector, false));
            }
        }

        for (int32 SpanIndex = 0; SpanIndex < AetherVapor::SpanSegments - 1; ++SpanIndex)
        {
            for (int32 ChordIndex = 0; ChordIndex < AetherVapor::ChordSegments - 1; ++ChordIndex)
            {
                const int32 A = LayerStart
                    + SpanIndex * AetherVapor::ChordSegments + ChordIndex;
                const int32 B = A + AetherVapor::ChordSegments;
                Triangles.Append({A, B, A + 1, A + 1, B, B + 1});
            }
        }
    }

    Mesh->CreateMeshSection_LinearColor(
        0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
    Mesh->SetVisibility(true);
}

void UAetherWingVaporComponent::UpdateTrailSamples(const float DeltaTime, const float Intensity)
{
    for (FAetherVaporTrailSample& Sample : TrailSamples)
    {
        Sample.Age += DeltaTime;
    }
    int32 ExpiredCount = 0;
    while (ExpiredCount < TrailSamples.Num() && TrailSamples[ExpiredCount].Age >= TrailLifetimeSeconds)
    {
        ++ExpiredCount;
    }
    if (ExpiredCount > 0)
    {
        TrailSamples.RemoveAt(0, ExpiredCount, EAllowShrinking::No);
    }

    SampleAccumulator += DeltaTime;
    if (Intensity < 0.055f || SampleAccumulator < AetherVapor::TrailSampleInterval || !FlightPawn.IsValid())
    {
        return;
    }
    SampleAccumulator = 0.0f;

    const FTransform Transform = FlightPawn->GetActorTransform();
    FAetherVaporTrailSample NewSample;
    NewSample.LeftWorld = Transform.TransformPosition(FVector(-65.0f, -WingTipOffsetCentimeters, 52.0f));
    NewSample.RightWorld = Transform.TransformPosition(FVector(-65.0f, WingTipOffsetCentimeters, 52.0f));
    NewSample.UpWorld = Transform.TransformVectorNoScale(FVector::UpVector).GetSafeNormal();
    NewSample.RightAxisWorld = Transform.TransformVectorNoScale(FVector::RightVector).GetSafeNormal();
    NewSample.Strength = Intensity;

    if (TrailSamples.Num() > 0
        && FVector::Distance(TrailSamples.Last().LeftWorld, NewSample.LeftWorld) > 50000.0f)
    {
        TrailSamples.Reset();
    }
    TrailSamples.Add(NewSample);
}

void UAetherWingVaporComponent::AppendTrailTube(
    const bool bLeft,
    TArray<FVector>& Vertices,
    TArray<int32>& Triangles,
    TArray<FVector>& Normals,
    TArray<FVector2D>& UVs,
    TArray<FLinearColor>& Colors,
    TArray<FProcMeshTangent>& Tangents) const
{
    if (!FlightPawn.IsValid() || TrailSamples.Num() < 2)
    {
        return;
    }

    const FTransform OwnerTransform = FlightPawn->GetActorTransform();
    const float VortexDirection = bLeft ? -1.0f : 1.0f;
    auto RolledUpCenter = [&](const int32 Index)
    {
        const FAetherVaporTrailSample& Sample = TrailSamples[Index];
        FVector Center = bLeft ? Sample.LeftWorld : Sample.RightWorld;
        const float AgeAlpha = FMath::Clamp(Sample.Age / TrailLifetimeSeconds, 0.0f, 1.0f);
        const float Rollup = FMath::SmoothStep(0.0f, 0.42f, Sample.Age);
        const float SpiralPhase = VortexDirection * Sample.Age * 5.4f + Index * 0.22f;
        const float SpiralRadius = Rollup * FMath::Lerp(8.0f, 92.0f, AgeAlpha);
        Center += Sample.UpWorld * FMath::Cos(SpiralPhase) * SpiralRadius;
        Center += Sample.RightAxisWorld * FMath::Sin(SpiralPhase) * SpiralRadius;
        return Center;
    };

    const int32 StartVertex = Vertices.Num();
    for (int32 Index = 0; Index < TrailSamples.Num(); ++Index)
    {
        const FAetherVaporTrailSample& Sample = TrailSamples[Index];
        const float NormalizedAge = FMath::Clamp(
            Sample.Age / TrailLifetimeSeconds, 0.0f, 1.0f);
        const float BirthFade = FMath::SmoothStep(0.0f, 0.075f, Sample.Age);
        const float DeathFade = FMath::Pow(1.0f - NormalizedAge, 1.9f);
        const float Expansion = FMath::SmoothStep(0.0f, 0.72f, NormalizedAge);
        const float HorizontalRadius = FMath::Lerp(18.0f, 118.0f, Expansion);
        const float VerticalRadius = FMath::Lerp(12.0f, 78.0f, Expansion);
        const float DensityPulse = 0.72f
            + 0.18f * FMath::Sin(Index * 1.71f + Sample.Age * 7.1f)
            + 0.10f * FMath::Sin(Index * 0.43f - Sample.Age * 13.7f);
        const float Alpha = Sample.Strength * BirthFade * DeathFade
            * FMath::Clamp(DensityPulse, 0.42f, 1.0f) * 0.19f;
        const FVector Center = RolledUpCenter(Index);

        const FVector PreviousCenter = RolledUpCenter(FMath::Max(0, Index - 1));
        const FVector NextCenter = RolledUpCenter(FMath::Min(TrailSamples.Num() - 1, Index + 1));
        FVector TrailDirectionWorld = (NextCenter - PreviousCenter).GetSafeNormal();
        if (TrailDirectionWorld.IsNearlyZero())
        {
            TrailDirectionWorld = -FlightPawn->GetActorForwardVector();
        }

        // Construct a stable cross-section perpendicular to the trail, then
        // rotate it as the vortex ages. A closed tube has real parallax and
        // lighting from every view angle; crossed ribbons produced the bands
        // visible in the user's screenshot.
        FVector AxisUp = FVector::VectorPlaneProject(Sample.UpWorld, TrailDirectionWorld).GetSafeNormal();
        if (AxisUp.IsNearlyZero())
        {
            AxisUp = FVector::UpVector;
        }
        FVector AxisSide = FVector::CrossProduct(TrailDirectionWorld, AxisUp).GetSafeNormal();
        AxisUp = FVector::CrossProduct(AxisSide, TrailDirectionWorld).GetSafeNormal();
        const float RollDirection = bLeft ? -1.0f : 1.0f;
        const float CrossSectionRoll = RollDirection * Sample.Age * 4.6f;

        const float U = static_cast<float>(Index)
            / static_cast<float>(FMath::Max(1, TrailSamples.Num() - 1)) * 3.8f;
        const FVector LocalTangent = OwnerTransform.InverseTransformVectorNoScale(
            TrailDirectionWorld).GetSafeNormal();

        for (int32 Side = 0; Side < AetherVapor::TrailTubeSides; ++Side)
        {
            const float Angle = TWO_PI * static_cast<float>(Side)
                / static_cast<float>(AetherVapor::TrailTubeSides) + CrossSectionRoll;
            const FVector Offset = AxisSide * FMath::Cos(Angle) * HorizontalRadius
                + AxisUp * FMath::Sin(Angle) * VerticalRadius;
            const FVector SurfaceNormalWorld = (
                AxisSide * FMath::Cos(Angle) / FMath::Max(HorizontalRadius, 1.0f)
                + AxisUp * FMath::Sin(Angle) / FMath::Max(VerticalRadius, 1.0f)).GetSafeNormal();

            Vertices.Add(OwnerTransform.InverseTransformPosition(Center + Offset));
            Normals.Add(OwnerTransform.InverseTransformVectorNoScale(
                SurfaceNormalWorld).GetSafeNormal());
            UVs.Add(FVector2D(U, static_cast<float>(Side)
                / static_cast<float>(AetherVapor::TrailTubeSides)));
            Colors.Add(FLinearColor(0.86f, 0.91f, 0.94f, Alpha));
            Tangents.Add(FProcMeshTangent(LocalTangent, false));
        }

        if (Index > 0)
        {
            const int32 CurrentRing = StartVertex + Index * AetherVapor::TrailTubeSides;
            const int32 PreviousRing = CurrentRing - AetherVapor::TrailTubeSides;
            for (int32 Side = 0; Side < AetherVapor::TrailTubeSides; ++Side)
            {
                const int32 NextSide = (Side + 1) % AetherVapor::TrailTubeSides;
                const int32 A = PreviousRing + Side;
                const int32 B = CurrentRing + Side;
                const int32 C = PreviousRing + NextSide;
                const int32 D = CurrentRing + NextSide;
                Triangles.Append({A, B, C, C, B, D});
            }
        }
    }
}

void UAetherWingVaporComponent::BuildWingtipTrails()
{
    if (!WingtipTrails)
    {
        return;
    }
    if (TrailSamples.Num() < 2)
    {
        WingtipTrails->SetVisibility(false);
        return;
    }

    TArray<FVector> Vertices;
    TArray<int32> Triangles;
    TArray<FVector> Normals;
    TArray<FVector2D> UVs;
    TArray<FLinearColor> Colors;
    TArray<FProcMeshTangent> Tangents;
    const int32 EstimatedVertices = TrailSamples.Num()
        * AetherVapor::TrailTubeSides * 2;
    Vertices.Reserve(EstimatedVertices);
    Normals.Reserve(EstimatedVertices);
    UVs.Reserve(EstimatedVertices);
    Colors.Reserve(EstimatedVertices);
    Tangents.Reserve(EstimatedVertices);

    AppendTrailTube(true, Vertices, Triangles, Normals, UVs, Colors, Tangents);
    AppendTrailTube(false, Vertices, Triangles, Normals, UVs, Colors, Tangents);

    WingtipTrails->CreateMeshSection_LinearColor(
        0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
    WingtipTrails->SetVisibility(true);
}

void UAetherWingVaporComponent::ClearVisuals()
{
    VaporIntensity = 0.0f;
    TrailSamples.Reset();
    for (UProceduralMeshComponent* Mesh : {LeftWingSheet, RightWingSheet, WingtipTrails})
    {
        if (Mesh)
        {
            Mesh->ClearAllMeshSections();
            Mesh->SetVisibility(false);
        }
    }
}
