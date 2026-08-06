using System.IO;
using UnrealBuildTool;

public class AetherFlightEditor : ModuleRules
{
    public AetherFlightEditor(ReadOnlyTargetRules Target) : base(Target)
    {
        PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

        PublicDependencyModuleNames.AddRange(new string[]
        {
            "Core",
            "CoreUObject",
            "Engine"
        });

        PrivateDependencyModuleNames.AddRange(new string[]
        {
            "UnrealEd",
            "MeshPartition",
            "MeshPartitionEditor"
        });

        // UE 5.8.1's public MeshPartitionCompiledSection.h includes the
        // Engine-internal MaterialCache/MaterialCacheVirtualTexture.h path.
        // Launcher builds do not expose that path consistently to external
        // editor modules, so resolve the editor-only compatibility declaration
        // from this module before falling back to the Engine private tree.
        PrivateIncludePaths.AddRange(new string[]
        {
            Path.Combine(ModuleDirectory, "Private"),
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Private")
        });
    }
}
