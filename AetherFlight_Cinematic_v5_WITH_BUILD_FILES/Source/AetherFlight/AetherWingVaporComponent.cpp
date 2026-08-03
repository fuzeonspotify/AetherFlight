#include "AetherWingVaporComponent.h"

#include "CinematicFlightPawn.h"
#include "Materials/MaterialInterface.h"
#include "ProceduralMeshComponent.h"
#include "ProceduralWorldDirector.h"

namespace AetherVapor
{
    constexpr int32 SpanSegments = 7;
    constexpr int32 ChordSegments = 5;
    constexpr int32 SheetLayers = 2;
    constexpr float TrailSampleInterval = 0.045f;
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

    const float LoadFactor = FMath::Abs(Pawn->GetGForce());
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
    const float HumidityGain = FMath::Lerp(0.48f, 1.18f, FMath::Clamp(Humidity, 0.0f, 1.0f));
    const float LiftDemand = FMath::Lerp(0.62f, 1.0f, AoAAlpha);
    return FMath::Clamp(GAlpha * SpeedAlpha * SupersonicFade * HumidityGain * LiftDemand, 0.0f, 1.0f);
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

    for (int32 Layer = 0; Layer < AetherVapor::SheetLayers; ++Layer)
    {
        const int32 LayerStart = Vertices.Num();
        for (int32 SpanIndex = 0; SpanIndex < AetherVapor::SpanSegments; ++SpanIndex)
        {
            const float Span = static_cast<float>(SpanIndex) / static_cast<float>(AetherVapor::SpanSegments - 1);
            const float LeadingX = FMath::Lerp(235.0f, -35.0f, Span);
            const float TrailingX = FMath::Lerp(-270.0f, -485.0f, Span);
            const float Y = SideSign * FMath::Lerp(145.0f, WingTipOffsetCentimeters, Span);
            const float SpanFade = FMath::Pow(FMath::Max(0.0f, FMath::Sin(Span * PI)), 0.38f);

            for (int32 ChordIndex = 0; ChordIndex < AetherVapor::ChordSegments; ++ChordIndex)
            {
                const float Chord = static_cast<float>(ChordIndex) / static_cast<float>(AetherVapor::ChordSegments - 1);
                const float EdgeFade = FMath::Pow(FMath::Max(0.0f, FMath::Sin(Chord * PI)), 0.5f);
                const float Noise = 0.72f + 0.28f * FMath::PerlinNoise2D(FVector2D(
                    Span * 4.7f + TimeSeconds * 0.19f,
                    Chord * 5.9f - TimeSeconds * 0.27f + SideSign * 7.0f));
                const float LayerGain = Layer == 0 ? 0.72f : 0.34f;
                const float Alpha = Intensity * SpanFade * EdgeFade * Noise * LayerGain;
                const float Z = 47.0f + Layer * 58.0f
                    + FMath::Sin(Chord * PI) * (18.0f + Intensity * 25.0f)
                    + FMath::Sin(Span * PI) * 9.0f;

                Vertices.Add(FVector(FMath::Lerp(LeadingX, TrailingX, Chord), Y, Z));
                Normals.Add(FVector::UpVector);
                UVs.Add(FVector2D(Span, Chord));
                Colors.Add(FLinearColor(0.72f, 0.86f, 1.0f, Alpha));
                Tangents.Add(FProcMeshTangent(FVector::ForwardVector, false));
            }
        }

        for (int32 SpanIndex = 0; SpanIndex < AetherVapor::SpanSegments - 1; ++SpanIndex)
        {
            for (int32 ChordIndex = 0; ChordIndex < AetherVapor::ChordSegments - 1; ++ChordIndex)
            {
                const int32 A = LayerStart + SpanIndex * AetherVapor::ChordSegments + ChordIndex;
                const int32 B = A + AetherVapor::ChordSegments;
                Triangles.Append({A, B, A + 1, A + 1, B, B + 1});
            }
        }
    }

    Mesh->CreateMeshSection_LinearColor(0, Vertices, Triangles, Normals, UVs, Colors, Tangents, false);
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
    if (Intensity < 0.10f || SampleAccumulator < AetherVapor::TrailSampleInterval || !FlightPawn.IsValid())
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
    const bool bVertical,
    TArray<FVector>& Vertices,
    TArray<int32>& Triangles,
    TArray<FVector>& Normals,
    TArray<FVector2D>& UVs,
    TArray<FLinearColor>& Colors,
    TArray<FProcMeshTangent>& Tangents) const
{
    if (!FlightPawn.IsValid())
    {
        return;
    }

    const FTransform OwnerTransform = FlightPawn->GetActorTransform();
    const int32 StartVertex = Vertices.Num();
    for (int32 Index = 0; Index < TrailSamples.Num(); ++Index)
    {
        const FAetherVaporTrailSample& Sample = TrailSamples[Index];
        const float AgeAlpha = 1.0f - FMath::Clamp(Sample.Age / TrailLifetimeSeconds, 0.0f, 1.0f);
        const float Width = FMath::Lerp(16.0f, 72.0f, 1.0f - AgeAlpha);
        const float Flicker = 0.82f + 0.18f * FMath::Sin(Index * 2.17f + Sample.Age * 7.1f);
        const float Alpha = Sample.Strength * AgeAlpha * AgeAlpha * 0.58f * Flicker;
        const FVector Center = bLeft ? Sample.LeftWorld : Sample.RightWorld;
        const FVector Axis = bVertical ? Sample.UpWorld : Sample.RightAxisWorld;

        Vertices.Add(OwnerTransform.InverseTransformPosition(Center - Axis * Width));
        Vertices.Add(OwnerTransform.InverseTransformPosition(Center + Axis * Width));
        Normals.Add(FVector::UpVector);
        Normals.Add(FVector::UpVector);
        UVs.Add(FVector2D(static_cast<float>(Index), 0.0f));
        UVs.Add(FVector2D(static_cast<float>(Index), 1.0f));
        Colors.Add(FLinearColor(0.70f, 0.84f, 1.0f, Alpha));
        Colors.Add(FLinearColor(0.70f, 0.84f, 1.0f, Alpha));
        Tangents.Add(FProcMeshTangent(FVector::ForwardVector, false));
        Tangents.Add(FProcMeshTangent(FVector::ForwardVector, false));

        if (Index > 0)
        {
            const int32 Current = StartVertex + Index * 2;
            const int32 Previous = Current - 2;
            Triangles.Append({Previous, Current, Previous + 1, Previous + 1, Current, Current + 1});
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
    AppendTrailRibbon(true, true, Vertices, Triangles, Normals, UVs, Colors, Tangents);
    AppendTrailRibbon(true, false, Vertices, Triangles, Normals, UVs, Colors, Tangents);
    AppendTrailRibbon(false, true, Vertices, Triangles, Normals, UVs, Colors, Tangents);
    AppendTrailRibbon(false, false, Vertices, Triangles, Normals, UVs, Colors, Tangents);
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
