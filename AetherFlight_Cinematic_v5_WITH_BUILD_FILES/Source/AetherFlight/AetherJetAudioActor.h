#pragma once

#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "AetherJetAudioActor.generated.h"

class ACinematicFlightPawn;
class UAetherJetAudioSynthComponent;
class UAudioComponent;
class USoundBase;

/** Runtime controller that blends recorded CC0 jet layers with the responsive synthesizer. */
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
    void ConfigureRecordedLayers();
    void UpdateRecordedLayers(float DeltaSeconds, float Throttle, float Mach, bool bCockpit);
    USoundBase* LoadOptionalSound(const TCHAR* ObjectPath) const;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Audio")
    UAetherJetAudioSynthComponent* JetSynth;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Audio")
    UAudioComponent* RecordedEngineLoop;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Audio")
    UAudioComponent* RecordedCoreLoop;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Audio")
    UAudioComponent* RecordedStartup;

    UPROPERTY(VisibleAnywhere, Category = "Aether|Audio")
    UAudioComponent* RecordedFlyby;

    TWeakObjectPtr<ACinematicFlightPawn> FlightPawn;
    bool bHasRecordedLayers = false;
    bool bHasFlybyLayer = false;
    float SmoothedLoopVolume = 0.0f;
    float SmoothedCoreVolume = 0.0f;
    float PreviousMach = 0.0f;
};
