# Resource packs and graphics

Open **View → Resource packs and graphics**, or the resource button in Studio
preferences. Add a Java resource pack folder containing `assets`, a resource ZIP,
or a Minecraft client JAR. The panel offers discovered default-launcher client
JARs when available; custom launcher installations can be selected manually.
Nothing is downloaded. Your selected files are read without modifying them.

Place the base client assets first. Add overrides below them; the last pack
containing a requested file wins. Apply/reload rebuilds the model and texture
caches, including after you edit a folder pack. Remove or reorder packs with the
list controls. Preferences remember up to 16 paths outside world folders.
Disable the stack to return to solid colors. A missing pack produces an error
and retains the currently loaded stack.

The **auto** backend uses system OpenGL with an offscreen framebuffer on a graphics
worker thread. Linux uses EGL; Windows and macOS have WGL/CGL adapters. If context
creation or rendering fails, the app uses its independent Python rasterizer.
Only Linux native graphics has been executed in this environment. Selecting
**software** explicitly bypasses native graphics. The fallback reduces resolution
with nearest-neighbor enlargement to keep CPU work bounded. It is visibly less
sharp. Renderer identity, frame time and resource diagnostics are available in
the panel. Python/Tk remain required; no third-party Python packages are needed.

Both renderers support perspective-correct textures, alpha cutouts, depth testing,
translucent face sorting, near-plane clipping, model-surface picking and selection/
paste outlines. Picking uses the actual displayed camera snapshot and texture
alpha, so a transparent hole can reveal the block behind it. Camera requests
coalesce without continuously cancelling an unfinished frame. Changing geometry,
packs or worlds cancels obsolete work. Image transfer crops empty borders.

Java JSON support includes parent inheritance, texture references, element bounds
(including inverted interior faces), element rotations/rescaling, face UVs and
rotations, blockstate rotations/UV locking, deterministic weighted variants and
multipart AND/OR conditions. Partial stored block states display the first variant
consistent with supplied properties; this does not add or translate saved states.
Texture-only packs can replace named cubes. Missing, malformed or procedural
models use a colored marker with a diagnostic instead of disappearing.

PNG supports all standard color types/permitted bit depths, filters, palettes,
tRNS, Adam7 and checksums. Texture `.mcmeta` supports frame grids, frame order,
timing and interpolation. Animation is off by default; enabling it causes idle
rendering for animated scenes. Interpolation is quantized to twentieths of a frame
interval to limit work. Texture sampling is nearest-neighbor without mipmaps.

Water/lava surfaces use stored Java levels or Bedrock liquid depth, shared corner
heights, adjacent fluid/solid culling and still/flow textures. Waterlogging and
secondary Bedrock water are visible, including cells whose primary layer is air.
These are static surfaces, not a fluid simulation. Biome grass/foliage colormaps,
explicit water/grass/foliage overrides and common leaf/redstone tints use selected
client `data/<namespace>/worldgen/biome` definitions when available. Missing biome
definitions use a plains/default display color. Stored biome data is unchanged.

## Limits still open

- Dedicated chest/bed/banner/skull/sign-text/entity geometry; moving-entity drawing.
  Some blocks combine a JSON model with additional procedural details that are
  not represented by the JSON model alone.
- Native Bedrock resource/model definitions and complete edition/version state
  translation. Java assets can illustrate matching Bedrock names, but that is
  not universal compatibility or exact game rendering.
- Exact Minecraft weighted-model random selection, biome-edge blending, altitude/
  spatial noise and game lighting/ambient occlusion. Swamp grass uses one static
  representative color; dark-forest modification is supported.
- Exact transparency for intersecting faces, flow/overlay effects and every
  specialized tint. Face sorting is an approximation for intersections.
- Full-world streaming. Display remains bounded to the selected local radius.

Limits include 32 MiB per PNG file, 4,194,304 decoded pixels, 1 MiB per JSON file,
100,000 ZIP entries, 4,096 faces/64 MiB textures per composed model, 128 MiB unique
textures per scene, 150,000 visible model faces and 2,000,000 picking references.
There are bounded JSON/model/texture caches, two geometry cache entries, one active
frame and one replaceable pending frame. These are data budgets, not RSS guarantees;
Python objects, platform buffers and two cached scenes add memory overhead.
