# Recorded jet audio

AetherFlight blends two recorded engine layers with its procedural synth. The recordings supply the real turbine/exhaust character; the synth supplies low-frequency body, wind, throttle response and G-load movement.

## Install once

1. Pull and build the current branch with Unreal Editor completely closed.
2. Open `AetherFlight.uproject`.
3. In Unreal Editor choose **Tools > Execute Python Script**.
4. Select `Content/Python/InstallRealJetAudio_UE58.py`.
5. Wait for the success dialog, click **Save All**, then press **Play**.

Output should contain:

```text
[Aether Audio] Recorded CC0 jet layers and procedural dynamics started.
```

The installer downloads public OGG preview encodes into `Saved/AetherAudioCache` and imports four Sound Waves into `/Game/Aether/Audio/Jet`. `Saved` is not committed.

## Optional full-quality upgrade

Download the original WAV/FLAC/OGG recordings and put them in `Content/AudioSource/Jet` with these names, then run the installer again:

| Local filename stem | Source |
|---|---|
| `Aether_JetLoop_CC0` | [Jet loop 01 by MickBoere](https://freesound.org/people/MickBoere/sounds/269064/) |
| `Aether_JetCore_CC0` | [Jet Engine by m_cel](https://freesound.org/people/m_cel/sounds/534856/) |
| `Aether_JetFlyby_CC0` | [Jet Plane Flyby by qubodup](https://freesound.org/people/qubodup/sounds/189446/) |
| `Aether_JetStartup_CC0` | [Jet engine startup by SamsterBirdies](https://freesound.org/people/SamsterBirdies/sounds/491407/) |

Accepted extensions are `.wav`, `.flac`, `.ogg`, `.aiff`, and `.aif`. Local files take priority over downloaded previews.

## Licensing

All four sources are marked **Creative Commons Zero (CC0)** on Freesound. They may be copied, modified, distributed and used commercially without required attribution. Source links are retained here for provenance and courtesy.

The audio files are not committed to Git. The installer makes every developer obtain the recordings from the original host and keeps the public repository lightweight.
