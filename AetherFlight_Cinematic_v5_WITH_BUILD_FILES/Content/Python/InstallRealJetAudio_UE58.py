"""Install recorded CC0 jet layers into /Game/Aether/Audio/Jet.

Run from Unreal Editor: Tools > Execute Python Script, then select this file.
The script prefers full-quality local source files in Content/AudioSource/Jet
and otherwise downloads the public Freesound preview encodes.
"""

import os
import urllib.request

import unreal


LOG = "[Aether Real Jet Audio]"
DESTINATION = "/Game/Aether/Audio/Jet"
PROJECT_DIR = unreal.Paths.convert_relative_path_to_full(unreal.Paths.project_dir())
LOCAL_SOURCE_DIR = os.path.join(PROJECT_DIR, "Content", "AudioSource", "Jet")
CACHE_DIR = os.path.join(PROJECT_DIR, "Saved", "AetherAudioCache")

SOURCES = (
    {
        "stem": "Aether_JetLoop_CC0",
        "asset": "SW_JetLoop_CC0",
        "looping": True,
        "url": "https://cdn.freesound.org/previews/269/269064_3411936-lq.ogg",
        "source": "https://freesound.org/people/MickBoere/sounds/269064/",
    },
    {
        "stem": "Aether_JetCore_CC0",
        "asset": "SW_JetCore_CC0",
        "looping": True,
        "url": "https://cdn.freesound.org/previews/534/534856_7108357-lq.ogg",
        "source": "https://freesound.org/people/m_cel/sounds/534856/",
    },
    {
        "stem": "Aether_JetFlyby_CC0",
        "asset": "SW_JetFlyby_CC0",
        "looping": False,
        "url": "https://cdn.freesound.org/previews/189/189446_71257-lq.ogg",
        "source": "https://freesound.org/people/qubodup/sounds/189446/",
    },
    {
        "stem": "Aether_JetStartup_CC0",
        "asset": "SW_JetStartup_CC0",
        "looping": False,
        "url": "https://cdn.freesound.org/previews/491/491407_5487341-lq.ogg",
        "source": "https://freesound.org/people/SamsterBirdies/sounds/491407/",
    },
)


def log(message):
    unreal.log(f"{LOG} {message}")


def find_local_source(stem):
    for extension in (".wav", ".flac", ".ogg", ".aiff", ".aif"):
        candidate = os.path.join(LOCAL_SOURCE_DIR, stem + extension)
        if os.path.isfile(candidate):
            return candidate
    return None


def download_preview(source):
    os.makedirs(CACHE_DIR, exist_ok=True)
    destination = os.path.join(CACHE_DIR, source["stem"] + ".ogg")
    if os.path.isfile(destination) and os.path.getsize(destination) > 4096:
        return destination

    request = urllib.request.Request(
        source["url"],
        headers={"User-Agent": "AetherFlight-Unreal-Audio-Installer/1.0"},
    )
    log(f"Downloading CC0 preview for {source['asset']}...")
    with urllib.request.urlopen(request, timeout=90) as response:
        payload = response.read()
    if len(payload) < 4096 or not payload.startswith(b"OggS"):
        raise RuntimeError(f"Download for {source['asset']} was not a valid OGG file")
    with open(destination, "wb") as handle:
        handle.write(payload)
    return destination


def import_sound(source, filename):
    task = unreal.AssetImportTask()
    task.set_editor_property("filename", filename)
    task.set_editor_property("destination_path", DESTINATION)
    task.set_editor_property("destination_name", source["asset"])
    task.set_editor_property("replace_existing", True)
    task.set_editor_property("automated", True)
    task.set_editor_property("save", True)
    unreal.AssetToolsHelpers.get_asset_tools().import_asset_tasks([task])

    asset_path = f"{DESTINATION}/{source['asset']}"
    sound_wave = unreal.EditorAssetLibrary.load_asset(asset_path)
    if not sound_wave:
        raise RuntimeError(f"Unreal did not create {asset_path}")
    try:
        sound_wave.set_editor_property("looping", source["looping"])
    except Exception as error:
        unreal.log_warning(f"{LOG} Could not set looping on {asset_path}: {error}")
    unreal.EditorAssetLibrary.save_loaded_asset(sound_wave, only_if_is_dirty=False)
    return asset_path


def main():
    os.makedirs(LOCAL_SOURCE_DIR, exist_ok=True)
    imported = []
    failures = []

    for source in SOURCES:
        try:
            filename = find_local_source(source["stem"])
            if filename:
                log(f"Using full-quality local source: {filename}")
            else:
                filename = download_preview(source)
            imported.append(import_sound(source, filename))
        except Exception as error:
            failures.append(f"{source['asset']}: {error}")
            unreal.log_error(f"{LOG} {failures[-1]}")

    if failures:
        body = "Some layers could not be installed:\n\n" + "\n".join(failures)
        unreal.EditorDialog.show_message("Aether Real Jet Audio", body, unreal.AppMsgType.OK)
        raise RuntimeError(body)

    body = (
        "Installed four recorded CC0 jet Sound Waves.\n\n"
        "The runtime will now blend two real engine recordings with the procedural dynamics layer.\n"
        "Save All, stop Play if it is running, then press Play again.\n\n"
        "Expected Output: [Aether Audio] Recorded CC0 jet layers and procedural dynamics started."
    )
    log("Installed: " + ", ".join(imported))
    unreal.EditorDialog.show_message("Aether Real Jet Audio", body, unreal.AppMsgType.OK)


if __name__ == "__main__":
    main()
