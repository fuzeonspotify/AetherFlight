#pragma once

#include "CoreMinimal.h"
#include "Components/SynthComponent.h"
#include "AetherJetAudioSynthComponent.generated.h"

/** Thread-safe flight parameters shared with the audio render generator. */
struct FAetherJetAudioSharedState
{
    FAetherJetAudioSharedState();

    TAtomic<float> Throttle;
    TAtomic<float> Mach;
    TAtomic<float> AirspeedKnots;
    TAtomic<float> LoadFactor;
    TAtomic<float> CockpitMix;
};

/**
 * Layered procedural jet engine: turbine harmonics, combustion rumble,
 * exhaust wash, afterburner crackle, aerodynamic wind, and cockpit filtering.
 */
UCLASS(ClassGroup = Audio, meta = (BlueprintSpawnableComponent))
class AETHERFLIGHT_API UAetherJetAudioSynthComponent : public USynthComponent
{
    GENERATED_BODY()

public:
    UAetherJetAudioSynthComponent(const FObjectInitializer& ObjectInitializer);

    void SetFlightState(
        float InThrottle,
        float InMach,
        float InAirspeedKnots,
        float InLoadFactor,
        bool bInCockpit);

protected:
    virtual ISoundGeneratorPtr CreateSoundGenerator(
        const FSoundGeneratorInitParams& InParams) override;

private:
    TSharedPtr<FAetherJetAudioSharedState, ESPMode::ThreadSafe> SharedState;
};
