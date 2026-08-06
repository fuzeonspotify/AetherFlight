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

        // UE 5.8.1's public MeshPartitionCompiledSection.h includes
        // MaterialCache/MaterialCacheVirtualTexture.h, which currently lives
        // under the Engine module's Private tree. MeshPartitionEditor can see
        // that path internally, but an external editor module including
        // MeshPartitionEditorComponent.h cannot unless it is added explicitly.
        // Keep this workaround editor-only and scoped to this private module.
        PrivateIncludePaths.Add(
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Private")
        );
    }
}
