#include "AetherWingVaporComponent.h"

#include "CinematicFlightPawn.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "ProceduralWorldDirector.h"

namespace AetherVapor
{
    constexpr int32 SpanSegments = 15;
    constexpr int32 ChordSegments = 9;
    constexpr int32 SheetLayers = 5;
    constexpr int32 TrailPlanes = 5;
    constexpr float TrailSampleInterval = 0.028f;
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
    const float ResponseSpeed = TargetIntensity > VaporIntensity ? 8.5f : 1.75f;
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
        const float LayerOffsetZ = (LayerT - 0.5f) * 118.0f;

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
                    * LayerEnvelope * DensityNoise * 0.31f;
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

void UAetherWingVaporComponent::AppendTrailRibbon(
    const bool bLeft,
    const float PlaneAngleRadians,
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
        const float AgeAlpha = 1.0f
            - FMath::Clamp(Sample.Age / TrailLifetimeSeconds, 0.0f, 1.0f);
        const float Expansion = 1.0f - AgeAlpha;
        const float Width = FMath::Lerp(24.0f, 155.0f, Expansion);
        const float DensityPulse = 0.84f
            + 0.16f * FMath::Sin(Index * 1.83f + Sample.Age * 6.7f);
        const float Alpha = Sample.Strength * FMath::Pow(AgeAlpha, 1.65f)
            * 0.30f * DensityPulse;
        const FVector Center = RolledUpCenter(Index);
        const FVector Axis = (
            Sample.UpWorld * FMath::Cos(PlaneAngleRadians)
            + Sample.RightAxisWorld * FMath::Sin(PlaneAngleRadians)).GetSafeNormal();

        const FVector PreviousCenter = RolledUpCenter(FMath::Max(0, Index - 1));
        const FVector NextCenter = RolledUpCenter(FMath::Min(TrailSamples.Num() - 1, Index + 1));
        const FVector TrailDirectionWorld = (NextCenter - PreviousCenter).GetSafeNormal();
        FVector SurfaceNormalWorld = FVector::CrossProduct(TrailDirectionWorld, Axis).GetSafeNormal();
        if (SurfaceNormalWorld.IsNearlyZero())
        {
            SurfaceNormalWorld = Sample.UpWorld;
        }

        Vertices.Add(OwnerTransform.InverseTransformPosition(Center - Axis * Width));
        Vertices.Add(OwnerTransform.InverseTransformPosition(Center + Axis * Width));
        const FVector LocalNormal = OwnerTransform.InverseTransformVectorNoScale(
            SurfaceNormalWorld).GetSafeNormal();
        Normals.Add(LocalNormal);
        Normals.Add(LocalNormal);
        const float U = static_cast<float>(Index)
            / static_cast<float>(FMath::Max(1, TrailSamples.Num() - 1)) * 4.5f;
        UVs.Add(FVector2D(U, 0.0f));
        UVs.Add(FVector2D(U, 1.0f));
        Colors.Add(FLinearColor(0.94f, 0.975f, 1.0f, Alpha));
        Colors.Add(FLinearColor(0.94f, 0.975f, 1.0f, Alpha));
        const FVector LocalTangent = OwnerTransform.InverseTransformVectorNoScale(
            TrailDirectionWorld).GetSafeNormal();
        Tangents.Add(FProcMeshTangent(LocalTangent, false));
        Tangents.Add(FProcMeshTangent(LocalTangent, false));

        if (Index > 0)
        {
            const int32 Current = StartVertex + Index * 2;
            const int32 Previous = Current - 2;
            Triangles.Append({
                Previous, Current, Previous + 1,
                Previous + 1, Current, Current + 1
            });
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
    const int32 EstimatedVertices = TrailSamples.Num() * 2
        * AetherVapor::TrailPlanes * 2;
    Vertices.Reserve(EstimatedVertices);
    Normals.Reserve(EstimatedVertices);
    UVs.Reserve(EstimatedVertices);
    Colors.Reserve(EstimatedVertices);
    Tangents.Reserve(EstimatedVertices);

    for (int32 Plane = 0; Plane < AetherVapor::TrailPlanes; ++Plane)
    {
        const float PlaneAngle = PI * static_cast<float>(Plane)
            / static_cast<float>(AetherVapor::TrailPlanes);
        AppendTrailRibbon(true, PlaneAngle, Vertices, Triangles, Normals, UVs, Colors, Tangents);
        AppendTrailRibbon(false, PlaneAngle, Vertices, Triangles, Normals, UVs, Colors, Tangents);
    }

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
