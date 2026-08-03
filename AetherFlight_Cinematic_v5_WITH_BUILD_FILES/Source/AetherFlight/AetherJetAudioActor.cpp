#include "AetherJetAudioActor.h"

#include "AetherJetAudioSynthComponent.h"
#include "CinematicFlightPawn.h"
#include "EngineUtils.h"

AAetherJetAudioActor::AAetherJetAudioActor()
{
    PrimaryActorTick.bCanEverTick = true;
    PrimaryActorTick.TickGroup = TG_PostPhysics;

    JetSynth = CreateDefaultSubobject<UAetherJetAudioSynthComponent>(TEXT("JetEngineSynth"));
    SetRootComponent(JetSynth);
}

void AAetherJetAudioActor::BeginPlay()
{
    Super::BeginPlay();
    FindFlightPawn();
    JetSynth->SetVolumeMultiplier(0.88f);
    JetSynth->Start();
    UE_LOG(LogTemp, Display, TEXT("[Aether Audio] Procedural jet engine started."));
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
    JetSynth->SetFlightState(
        Pawn->GetThrottle(),
        Pawn->GetMach(),
        Pawn->GetAirspeedKnots(),
        Pawn->GetGForce(),
        Pawn->GetCameraModeName().Equals(TEXT("COCKPIT"), ESearchCase::IgnoreCase));
}

void AAetherJetAudioActor::FindFlightPawn()
{
    for (TActorIterator<ACinematicFlightPawn> It(GetWorld()); It; ++It)
    {
        FlightPawn = *It;
        SetActorLocation(It->GetActorLocation());
        return;
    }
}
