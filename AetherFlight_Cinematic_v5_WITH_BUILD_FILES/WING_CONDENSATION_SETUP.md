# Aerodynamic wing condensation

This effect represents pressure-induced condensation, not engine smoke.

- Vapour requires sufficient airspeed and approximately **2.25 G or more**.
- Density rises progressively toward full strength around **6.25 G**.
- Angle of attack changes the density instead of acting as an on/off trigger.
- Broken-cloud and storm weather increase condensation; dry golden weather reduces it.
- Two thin wing sheets form above the lifting surfaces.
- Crossed wingtip ribbons expand and disappear within roughly two seconds.
- The meshes have no collision, no shadows, and a small fixed vertex budget.

## Install the translucent material once

1. Build with Unreal Editor completely closed.
2. Open the project.
3. Choose **Tools > Execute Python Script**.
4. Select `Content/Python/InstallWingCondensationMaterial_UE58.py`.
5. Click **Save All**, then press **Play**.

Output should contain:

```text
[Aether Vapor] Aerodynamic wing condensation is active (G-load, airspeed, AoA and humidity driven).
```

Test it above 185 knots with a sustained hard pull. A gentle turn should not generate a continuous trail.
