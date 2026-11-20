# Arena artwork

Generated using the built-in image-generation tool for this project. These are reusable
art assets, not screenshots of a completed game. The renderer composites each structure,
unit, connection and label from the current replay state. Medieval retains its original
SVG pack. All production images must live in this directory, not an external temp path.

## Prompt set

`theme-atlas.png`: transparent 6-column, 4-row sprite atlas. Rows: Cyber Warfare,
Galactic Dominion, Wasteland Survival, Championship. Columns: large headquarters,
defense tower, small bastion, relic, infantry, environment decoration. Premium painted
isometric strategy-game art, clear silhouettes, metal bevels, luminous windows, shadows,
blue team accents for runtime recoloring, no text or UI. Cyber uses server fortresses,
robots and reactors; Galactic uses planetary cities, orbital stations and cosmic crystals;
Wasteland uses weathered steel fortresses and generators; Championship uses blue/gold
castles, banners and trophies. Objects are isolated so game ownership, positions, and
capture state remain dynamic. Source boundaries are defined in `arena_themes.js`.

`unit-atlas.png`: transparent equal 4x4 atlas. Same four theme rows; columns are Guard,
Raider, Siege, Scout. Detailed painted isometric units with blue accents and transparent
padding: cyber shield/assault robots, hover artillery and drone; space marine/interceptor,
heavy spacecraft and satellite; wasteland shield soldier, dual-pistol raider, tank and
gyrocopter; championship shield knight, duelist, cannon and mechanical eagle.

`terrain-atlas.png`: equal 2x2 texture atlas: cyber, galactic, wasteland, championship.
Empty terrain plates with a spacious clear central 75% for independently drawn gameplay.
No nodes, units, connections, roads or UI. Cyber: dark navy grid, circuits, cyan frame and
magenta corner accents. Galactic: stars, nebula edges, distant galaxy and planet horizon.
Wasteland: cracked amber desert with wreckage and scrub restricted to the outer edges.
Championship: dark tiled floor, gold perimeter walls, team banners, torches and spectator
tiers along the edges. These plates provide scenery only; the entire game stays interactive.

The reference images guided palette, silhouette and composition. The artwork is an
approximation rather than a pixel-identical reproduction. 3D uses real procedural meshes,
not a screenshot, a flat sprite plane, or the 2D terrain as a substitute for geometry.
