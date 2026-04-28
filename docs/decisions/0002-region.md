# 0002 — First study region: Austin, TX

**Date:** 2026-04-28
**Status:** accepted

## Context
Pick a region for the first end-to-end run. Needs to be (a) small enough that an OSM extract + tile build is fast, (b) interesting enough to show non-trivial anisotropy (highways, river, hills), (c) somewhere both collaborators have intuition for the ground truth.

## Decision
**Austin, TX metro.** Start from a BBBike/Geofabrik extract sized roughly to Travis County + adjacent.

## Alternatives
- Smaller (single neighborhood): too uniform, anisotropy will be boring.
- Whole Texas: tile build painful, more data than needed for v1.
- A non-US city: lose collaborator ground-truth.

## Consequences
- All projection work uses **UTM Zone 14N** (EPSG:32614).
- Once the pipeline works, swapping regions is just a different OSM extract + a different bbox. Not locked in long-term.
- Highway features (I-35, MoPac, 183) and the river will dominate the anisotropy field — useful for visual sanity-checking results.
