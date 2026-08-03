#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AetherJetAudioActor.generated.h"

class ACinematicFlightPawn;
class UAetherJetAudioSynthComponent;

/** Runtime controller that connects aircraft telemetry to the jet synthesizer. */
UCLASS()
class AETHERFLIGHT_API AAetherJetAudioActor : public AActor
{
    GENERATED_BODY()

public:
    AAetherJetAudioActor();

    virtual void BeginPlay() override;
    virtual void Tick(float DeltaSeconds) override;

private:
    void FindFlightPawn();

    UPROPERTY(VisibleAnywhere, Category = "Aether|Audio")
    UAetherJetAudioSynthComponent* JetSynth;

    TWeakObjectPtr<ACinematicFlightPawn> FlightPawn;
};
