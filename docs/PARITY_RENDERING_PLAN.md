# Resource rendering implementation and acceptance

Continue the full parity worklist from the tested 0.4 checkpoint. Original
implementation, Python standard library and platform APIs only; no Amulet code,
game assets or third-party Python runtime packages are bundled.

1. Decode bounded PNG textures independently: every standard color type and
   permitted bit depth, filters, palette/tRNS alpha, Adam7, CRC/truncation and
   decompression limits. Test against independently assembled fixtures.
2. Load Java resource pack folders/ZIPs/client JARs with explicit priority,
   bounded file reads and safe resource names. Resolve blockstates, weighted
   variants, multipart conditions, parent/texture indirection, element geometry,
   face UVs, element/block rotations, UV lock and animation frame metadata.
3. Integrate textured model geometry and correct occlusion into the bounded
   background geometry pipeline, retaining fallback visuals and diagnostics for
   unavailable assets. Preserve the document and all saved block data.
4. Render texture alpha, cutouts, translucent faces and perspective-correct UVs.
   Use system graphics APIs where available and a standard-library fallback.
   Keep graphics contexts off the Tk thread; discard stale frames and bound work.
5. Pick the displayed model surfaces, including texture holes. Connect resource
   stack/settings controls, preserve orbit/flight/selection/preview interactions,
   and show clear progress or actionable errors.
6. Test codecs, geometry, clipping/depth/alpha/picking, cache invalidation,
   cancellation, native Tk controls, malformed packs and package resources.
   Inspect actual screenshots, profile cold/warm paths and revise observed issues.

Do not equate a textured cube fallback with full model support. Record unsupported
procedural/entity/Bedrock models and native-platform evidence precisely. After
rendering, continue storage/translation/entity/interchange work in the main ledger.
