#include "AetherJetAudioActor.h"

#include "AetherJetAudioSynthComponent.h"
#include "CinematicFlightPawn.h"
#include "Components/AudioComponent.h"
#include "EngineUtils.h"
#include "Sound/SoundBase.h"

namespace AetherJetAudioAssets
{
    static constexpr const TCHAR* EngineLoop =
        TEXT("/Game/Aether/Audio/Jet/SW_JetLoop_CC0.SW_JetLoop_CC0");
    static constexpr const TCHAR* CoreLoop =
        TEXT("/Game/Aether/Audio/Jet/SW_JetCore_CC0.SW_JetCore_CC0");
    static constexpr const TCHAR* Startup =
        TEXT("/Game/Aether/Audio/Jet/SW_JetStartup_CC0.SW_JetStartup_CC0");
    static constexpr const TCHAR* Flyby =
        TEXT("/Game/Aether/Audio/Jet/SW_JetFlyby_CC0.SW_JetFlyby_CC0");
}

AAetherJetAudioActor::AAetherJetAudioActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;

    JetSynth = CreateDefaultSubobject<UAetherJetAudioSynthComponent>(TEXT("JetEngineSynth"));
    SetRootComponent(JetSynth);

    RecordedEngineLoop = CreateDefaultSubobject<UAudioComponent>(TEXT("RecordedEngineLoop"));
    RecordedEngineLoop->SetupAttachment(JetSynth);
    RecordedEngineLoop->SetAutoActivate(false);

    RecordedCoreLoop = CreateDefaultSubobject<UAudioComponent>(TEXT("RecordedCoreLoop"));
    RecordedCoreLoop->SetupAttachment(JetSynth);
    RecordedCoreLoop->SetAutoActivate(false);

    RecordedStartup = CreateDefaultSubobject<UAudioComponent>(TEXT("RecordedStartup"));
    RecordedStartup->SetupAttachment(JetSynth);
    RecordedStartup->SetAutoActivate(false);

    RecordedFlyby = CreateDefaultSubobject<UAudioComponent>(TEXT("RecordedFlyby"));
    RecordedFlyby->SetupAttachment(JetSynth);
    RecordedFlyby->SetAutoActivate(false);
}

void AAetherJetAudioActor::BeginPlay()
{
    Super::BeginPlay();
    FindFlightPawn();
    ConfigureRecordedLayers();

    JetSynth->SetVolumeMultiplier(bHasRecordedLayers ? 0.34f : 0.88f);
    JetSynth->Start();

    if (bHasRecordedLayers)
    {
        UE_LOG(LogTemp, Display,
            TEXT("[Aether Audio] Recorded CC0 jet layers and procedural dynamics started."));
    }
    else
    {
        UE_LOG(LogTemp, Warning,
            TEXT("[Aether Audio] Recorded layers are not installed; using procedural fallback. "
                 "Run Content/Python/InstallRealJetAudio_UE58.py in the Unreal Editor."));
    }
}

void AAetherJetAudioActor::Tick(const float DeltaSeconds)
{
    Super::Tick(DeltaSeconds);
    if (!FlightPawn.IsValid())
    {
        FindFlightPawn();
    }
    if (!FlightPawn.IsValid())
    {
        return;
    }

    ACinematicFlightPawn* Pawn = FlightPawn.Get();
    SetActorLocation(Pawn->GetActorLocation());

    const float Throttle = Pawn->GetThrottle();
    const float Mach = Pawn->GetMach();
    const bool bCockpit = Pawn->GetCameraModeName().Equals(TEXT("COCKPIT"), ESearchCase::IgnoreCase);

    JetSynth->SetFlightState(
        Throttle,
        Mach,
        Pawn->GetAirspeedKnots(),
        Pawn->GetGForce(),
        bCockpit);

    if (bHasRecordedLayers)
    {
        UpdateRecordedLayers(DeltaSeconds, Throttle, Mach, bCockpit);
    }
    PreviousMach = Mach;
}

void AAetherJetAudioActor::FindFlightPawn()
{
    for (TActorIterator<ACinematicFlightPawn> It(GetWorld()); It; ++It)
    {
        FlightPawn = *It;
        SetActorLocation(It->GetActorLocation());
        PreviousMach = It->GetMach();
        return;
    }
}

void AAetherJetAudioActor::ConfigureRecordedLayers()
{
    USoundBase* EngineSound = LoadOptionalSound(AetherJetAudioAssets::EngineLoop);
    USoundBase* CoreSound = LoadOptionalSound(AetherJetAudioAssets::CoreLoop);
    USoundBase* StartupSound = LoadOptionalSound(AetherJetAudioAssets::Startup);
    USoundBase* FlybySound = LoadOptionalSound(AetherJetAudioAssets::Flyby);

    bHasRecordedLayers = EngineSound != nullptr && CoreSound != nullptr;
    if (!bHasRecordedLayers)
    {
        return;
    }

    RecordedEngineLoop->SetSound(EngineSound);
    RecordedEngineLoop->SetVolumeMultiplier(0.01f);
    RecordedEngineLoop->Play();

    RecordedCoreLoop->SetSound(CoreSound);
    RecordedCoreLoop->SetVolumeMultiplier(0.01f);
    RecordedCoreLoop->Play(0.7f);

    if (StartupSound)
    {
        RecordedStartup->SetSound(StartupSound);
        if (FlightPawn.IsValid() && FlightPawn->GetThrottle() < 0.12f)
        {
            RecordedStartup->SetVolumeMultiplier(0.55f);
            RecordedStartup->Play();
        }
    }

    if (FlybySound)
    {
        RecordedFlyby->SetSound(FlybySound);
        bHasFlybyLayer = true;
    }
}

void AAetherJetAudioActor::UpdateRecordedLayers(
    const float DeltaSeconds,
    const float Throttle,
    const float Mach,
    const bool bCockpit)
{
    const float ThrottleCurve = FMath::Pow(FMath::Clamp(Throttle, 0.0f, 1.0f), 0.72f);
    const float ExteriorMix = bCockpit ? 0.38f : 1.0f;
    const float LoopTarget = FMath::Lerp(0.16f, 0.82f, ThrottleCurve) * ExteriorMix;
    const float CoreTarget = FMath::SmoothStep(0.22f, 1.0f, Throttle) * 0.58f * ExteriorMix;

    SmoothedLoopVolume = FMath::FInterpTo(SmoothedLoopVolume, LoopTarget, DeltaSeconds, 2.4f);
    SmoothedCoreVolume = FMath::FInterpTo(SmoothedCoreVolume, CoreTarget, DeltaSeconds, 3.2f);

    RecordedEngineLoop->SetVolumeMultiplier(SmoothedLoopVolume);
    RecordedCoreLoop->SetVolumeMultiplier(SmoothedCoreVolume);

    const float MachPitch = FMath::Clamp(Mach, 0.0f, 1.4f) * 0.045f;
    RecordedEngineLoop->SetPitchMultiplier(FMath::Lerp(0.82f, 1.13f, ThrottleCurve) + MachPitch);
    RecordedCoreLoop->SetPitchMultiplier(FMath::Lerp(0.76f, 1.08f, ThrottleCurve) + MachPitch * 0.6f);

    // Keep the synth as the low-frequency body, wind and G-load layer rather than the main timbre.
    JetSynth->SetVolumeMultiplier(bCockpit ? 0.25f : 0.34f);

    // A single exterior transient gives transonic passes cinematic weight without looping a flyby sample.
    if (!bCockpit && bHasFlybyLayer && PreviousMach < 0.94f && Mach >= 0.94f)
    {
        RecordedFlyby->SetVolumeMultiplier(0.42f);
        RecordedFlyby->SetPitchMultiplier(0.96f + FMath::FRandRange(-0.025f, 0.025f));
        RecordedFlyby->Play();
    }
}

USoundBase* AAetherJetAudioActor::LoadOptionalSound(const TCHAR* ObjectPath) const
{
    return LoadObject<USoundBase>(nullptr, ObjectPath);
}
