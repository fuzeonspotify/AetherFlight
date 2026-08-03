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

        virtual int32 GetNumChannels() const override
        {
            return 2;
        }

        virtual bool IsFinished() const override
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
                const float Flutter = 1.0f + 0.006f * FMath::Sin(ModulationPhase)
                    + 0.0025f * FMath::Sin(ModulationPhase * 2.31f);

                // Keep a restrained mechanical turbine layer beneath the exhaust.
                const float FanHz = (48.0f + 195.0f * SpoolCurve + 12.0f * Mach) * Flutter;
                const float CompressorHz = (280.0f + 780.0f * SpoolCurve + 24.0f * LoadFactor) * Flutter;
                const float CombustionHz = 27.0f + 43.0f * SpoolCurve;

                AdvancePhase(FanPhase, FanHz);
                AdvancePhase(FanHarmonicPhase, FanHz * 2.015f);
                AdvancePhase(CompressorPhase, CompressorHz);
                AdvancePhase(CompressorHarmonicPhase, CompressorHz * 1.985f);
                AdvancePhase(CombustionPhase, CombustionHz);
                AdvancePhase(ModulationPhase, 0.63f + 0.22f * Spool);

                const float Turbine =
                    FMath::Sin(FanPhase) * 0.14f
                    + FMath::Sin(FanHarmonicPhase) * 0.035f
                    + FMath::Sin(CompressorPhase) * (0.012f + 0.025f * SpoolCurve)
                    + FMath::Sin(CompressorHarmonicPhase) * (0.006f + 0.012f * SpoolCurve);
                const float CombustionThrob =
                    (FMath::Sin(CombustionPhase)
                        + 0.32f * FMath::Sin(CombustionPhase * 2.0f)
                        + 0.14f * FMath::Sin(CombustionPhase * 3.0f))
                    * (0.055f + 0.18f * SpoolCurve);

                // Two differently filtered noise streams form the broad, throaty jet-exhaust roar.
                const float RumbleWhite = NextNoise();
                const float RumbleLowpassAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * (82.0f + 135.0f * Spool) / SampleRate);
                RumbleState += (RumbleWhite - RumbleState) * RumbleLowpassAlpha;

                const float RoarWhite = NextNoise();
                const float ExhaustLowpassAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * (720.0f + 1750.0f * Spool) / SampleRate);
                const float RoarBassLowpassAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * (62.0f + 105.0f * Spool) / SampleRate);
                ExhaustState += (RoarWhite - ExhaustState) * ExhaustLowpassAlpha;
                RoarBassState += (RoarWhite - RoarBassState) * RoarBassLowpassAlpha;

                const float RoarBand = ExhaustState - RoarBassState;
                const float ExhaustBreath = 0.90f + 0.10f * FMath::Sin(ModulationPhase * 0.53f);
                const float ExhaustRoar =
                    (RoarBand * (0.40f + 0.78f * SpoolCurve)
                        + RumbleState * (0.44f + 0.46f * Spool))
                    * ExhaustBreath;

                CrackleEnvelope *= FMath::Exp(-1.0f / (SampleRate * 0.022f));
                if (Spool > 0.84f && (NextRandom() & 2047u) < static_cast<uint32>(2.0f + 12.0f * SpoolCurve))
                {
                    const float CrackleStrength = 0.35f
                        + static_cast<float>(NextRandom() & 0xFFFFu) / 65535.0f * 0.60f;
                    CrackleEnvelope = FMath::Max(CrackleEnvelope, CrackleStrength);
                }
                const float Afterburner = NextNoise() * CrackleEnvelope * FMath::Square(
                    FMath::Clamp((Spool - 0.82f) / 0.18f, 0.0f, 1.0f));

                const float WindAmount = FMath::Clamp(
                    (AirspeedKnots - 110.0f) / 720.0f, 0.0f, 1.25f);
                const float WindWhite = NextNoise();
                WindState += (WindWhite - WindState) * 0.055f;
                const float Wind = (WindWhite - WindState) * WindAmount * 0.21f;

                float Sample = Turbine * (0.22f + 0.32f * SpoolCurve)
                    + CombustionThrob
                    + ExhaustRoar
                    + Afterburner * 0.34f
                    + Wind * 0.78f;

                const float CockpitCutoff = FMath::Lerp(9000.0f, 1150.0f, CockpitMix);
                const float CockpitAlpha = 1.0f - FMath::Exp(
                    -AetherJetAudio::TwoPi * CockpitCutoff / SampleRate);
                CockpitFilterState += (Sample - CockpitFilterState) * CockpitAlpha;
                Sample = FMath::Lerp(Sample, CockpitFilterState, CockpitMix * 0.88f);
                Sample *= FMath::Lerp(0.72f, 0.43f, CockpitMix);
                Sample = FMath::Clamp(Sample, -0.96f, 0.96f);

                const float StereoMotion = 0.014f * FMath::Sin(ModulationPhase * 0.47f);
                OutAudio[Frame * 2] = FMath::Clamp(Sample - StereoMotion * ExhaustRoar, -1.0f, 1.0f);
                OutAudio[Frame * 2 + 1] = FMath::Clamp(Sample + StereoMotion * ExhaustRoar, -1.0f, 1.0f);
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
        float CombustionPhase = 0.0f;
        float ModulationPhase = 0.0f;
        float RumbleState = 0.0f;
        float ExhaustState = 0.0f;
        float RoarBassState = 0.0f;
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
