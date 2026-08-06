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
        // MaterialCache/MaterialCacheVirtualTexture.h from Engine/Classes.
        // Launcher builds do not consistently expose that legacy Classes root
        // to external editor modules, so add the real Engine header location.
        PrivateIncludePaths.AddRange(new string[]
        {
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Classes"),
            Path.Combine(EngineDirectory, "Source", "Runtime", "Engine", "Private")
        });
    }
}
