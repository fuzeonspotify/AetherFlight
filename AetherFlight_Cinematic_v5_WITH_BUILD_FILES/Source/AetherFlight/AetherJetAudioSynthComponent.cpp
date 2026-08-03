#include "AetherJetAudioSynthComponent.h"

#include "Sound/SoundGenerator.h"

namespace AetherJetAudio
{
    constexpr float TwoPi = 2.0f * PI;

    class FJetSoundGenerator final : public ISoundGenerator
    {
    public:
        FJetSoundGenerator(
            const float InSampleRate,
            TSharedPtr<FAetherJetAudioSharedState, ESPMode::ThreadSafe> InState)
            : SampleRate(FMath::Max(8000.0f, InSampleRate))
            , State(MoveTemp(InState))
        {
        }

        virtual int32 GetNumChannels() override
        {
            return 2;
        }

        virtual bool IsFinished() override
        {
            return false;
        }

        virtual int32 OnGenerateAudio(float* OutAudio, const int32 NumSamples) override
        {
            if (!State.IsValid() || NumSamples < 2)
            {
                FMemory::Memzero(OutAudio, NumSamples * sizeof(float));
                return NumSamples;
            }

            const float TargetThrottle = FMath::Clamp(State->Throttle.Load(), 0.0f, 1.0f);
            const float TargetMach = FMath::Clamp(State->Mach.Load(), 0.0f, 2.5f);
            const float TargetKnots = FMath::Max(0.0f, State->AirspeedKnots.Load());
            const float TargetLoad = FMath::Clamp(FMath::Abs(State->LoadFactor.Load()), 0.0f, 9.0f);
            const float TargetCockpit = FMath::Clamp(State->CockpitMix.Load(), 0.0f, 1.0f);

            const float SpoolSmoothing = 1.0f - FMath::Exp(-1.0f / (SampleRate * 0.48f));
            const float StateSmoothing = 1.0f - FMath::Exp(-1.0f / (SampleRate * 0.16f));
            const int32 NumFrames = NumSamples / 2;
            for (int32 Frame = 0; Frame < NumFrames; ++Frame)
            {
                Spool += (TargetThrottle - Spool) * SpoolSmoothing;
                Mach += (TargetMach - Mach) * StateSmoothing;
                AirspeedKnots += (TargetKnots - AirspeedKnots) * StateSmoothing;
                LoadFactor += (TargetLoad - LoadFactor) * StateSmoothing;
                CockpitMix += (TargetCockpit - CockpitMix) * StateSmoothing;

                const float SpoolCurve = FMath::Pow(FMath::Max(Spool, 0.0f), 1.32f);
                const float Flutter = 1.0f + 0.007f * FMath::Sin(ModulationPhase)
                    + 0.003f * FMath::Sin(ModulationPhase * 2.31f);
                const float FanHz = (72.0f + 355.0f * SpoolCurve + 24.0f * Mach) * Flutter;
                const float CompressorHz = (390.0f + 1260.0f * SpoolCurve + 48.0f * LoadFactor) * Flutter;

                AdvancePhase(FanPhase, FanHz);
                AdvancePhase(FanHarmonicPhase, FanHz * 2.015f);
                AdvancePhase(CompressorPhase, CompressorHz);
                AdvancePhase(CompressorHarmonicPhase, CompressorHz * 1.985f);
                AdvancePhase(ModulationPhase, 0.63f + 0.22f * Spool);

                const float Turbine =
                    FMath::Sin(FanPhase) * 0.26f
                    + FMath::Sin(FanHarmonicPhase) * 0.12f
                    + FMath::Sin(CompressorPhase) * (0.045f + 0.10f * SpoolCurve)
                    + FMath::Sin(CompressorHarmonicPhase) * (0.025f + 0.055f * SpoolCurve);

                const float White = NextNoise();
                const float NoiseLowpassAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * (95.0f + 150.0f * Spool) / SampleRate);
                RumbleState += (White - RumbleState) * NoiseLowpassAlpha;

                const float ExhaustLowpassAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * (1100.0f + 4200.0f * Spool) / SampleRate);
                ExhaustState += (White - ExhaustState) * ExhaustLowpassAlpha;
                const float ExhaustWash = (White * 0.52f + ExhaustState * 0.48f)
                    * (0.16f + 0.38f * SpoolCurve);

                CrackleEnvelope *= FMath::Exp(-1.0f / (SampleRate * 0.022f));
                if (Spool > 0.84f && (NextRandom() & 2047u) < static_cast<uint32>(2.0f + 12.0f * SpoolCurve))
                {
                    const float CrackleStrength = 0.35f
                        + static_cast<float>(NextRandom() & 0xFFFFu) / 65535.0f * 0.60f;
                    CrackleEnvelope = FMath::Max(CrackleEnvelope, CrackleStrength);
                }
                const float Afterburner = White * CrackleEnvelope * FMath::Square(
                    FMath::Clamp((Spool - 0.82f) / 0.18f, 0.0f, 1.0f));

                const float WindAmount = FMath::Clamp(
                    (AirspeedKnots - 110.0f) / 720.0f, 0.0f, 1.25f);
                const float WindWhite = NextNoise();
                WindState += (WindWhite - WindState) * 0.055f;
                const float Wind = (WindWhite - WindState) * WindAmount * 0.21f;

                float Sample = Turbine * (0.38f + 0.58f * SpoolCurve)
                    + RumbleState * (0.42f + 0.30f * Spool)
                    + ExhaustWash
                    + Afterburner * 0.42f
                    + Wind;

                const float CockpitCutoff = FMath::Lerp(9000.0f, 1150.0f, CockpitMix);
                const float CockpitAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * CockpitCutoff / SampleRate);
                CockpitFilterState += (Sample - CockpitFilterState) * CockpitAlpha;
                Sample = FMath::Lerp(Sample, CockpitFilterState, CockpitMix * 0.88f);
                Sample *= FMath::Lerp(0.72f, 0.43f, CockpitMix);
                Sample = FMath::Clamp(Sample, -0.96f, 0.96f);

                const float StereoMotion = 0.018f * FMath::Sin(ModulationPhase * 0.47f);
                OutAudio[Frame * 2] = FMath::Clamp(Sample - StereoMotion * ExhaustWash, -1.0f, 1.0f);
                OutAudio[Frame * 2 + 1] = FMath::Clamp(Sample + StereoMotion * ExhaustWash, -1.0f, 1.0f);
            }

            if ((NumSamples & 1) != 0)
            {
                OutAudio[NumSamples - 1] = 0.0f;
            }
            return NumSamples;
        }

    private:
        void AdvancePhase(float& Phase, const float FrequencyHz) const
        {
            Phase += AetherJetAudio::TwoPi * FrequencyHz / SampleRate;
            if (Phase >= AetherJetAudio::TwoPi)
            {
                Phase -= AetherJetAudio::TwoPi;
            }
        }

        uint32 NextRandom()
        {
            RandomState ^= RandomState << 13u;
            RandomState ^= RandomState >> 17u;
            RandomState ^= RandomState << 5u;
            return RandomState;
        }

        float NextNoise()
        {
            return static_cast<float>(NextRandom() & 0x00FFFFFFu) / 8388607.5f - 1.0f;
        }

        float SampleRate = 48000.0f;
        TSharedPtr<FAetherJetAudioSharedState, ESPMode::ThreadSafe> State;
        uint32 RandomState = 0xA37E4D91u;
        float Spool = 0.25f;
        float Mach = 0.0f;
        float AirspeedKnots = 0.0f;
        float LoadFactor = 1.0f;
        float CockpitMix = 0.0f;
        float FanPhase = 0.0f;
        float FanHarmonicPhase = 0.0f;
        float CompressorPhase = 0.0f;
        float CompressorHarmonicPhase = 0.0f;
        float ModulationPhase = 0.0f;
        float RumbleState = 0.0f;
        float ExhaustState = 0.0f;
        float WindState = 0.0f;
        float CockpitFilterState = 0.0f;
        float CrackleEnvelope = 0.0f;
    };
}

FAetherJetAudioSharedState::FAetherJetAudioSharedState()
    : Throttle(0.72f)
    , Mach(0.0f)
    , AirspeedKnots(0.0f)
    , LoadFactor(1.0f)
    , CockpitMix(0.0f)
{
}

UAetherJetAudioSynthComponent::UAetherJetAudioSynthComponent(
    const FObjectInitializer& ObjectInitializer)
    : Super(ObjectInitializer)
    , SharedState(MakeShared<FAetherJetAudioSharedState, ESPMode::ThreadSafe>())
{
    bAutoActivate = false;
}

void UAetherJetAudioSynthComponent::SetFlightState(
    const float InThrottle,
    const float InMach,
    const float InAirspeedKnots,
    const float InLoadFactor,
    const bool bInCockpit)
{
    SharedState->Throttle.Store(FMath::Clamp(InThrottle, 0.0f, 1.0f));
    SharedState->Mach.Store(FMath::Max(0.0f, InMach));
    SharedState->AirspeedKnots.Store(FMath::Max(0.0f, InAirspeedKnots));
    SharedState->LoadFactor.Store(InLoadFactor);
    SharedState->CockpitMix.Store(bInCockpit ? 1.0f : 0.0f);
}

ISoundGeneratorPtr UAetherJetAudioSynthComponent::CreateSoundGenerator(
    const FSoundGeneratorInitParams& InParams)
{
    return MakeShared<AetherJetAudio::FJetSoundGenerator, ESPMode::ThreadSafe>(
        InParams.SampleRate,
        SharedState);
}
