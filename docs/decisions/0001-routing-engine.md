# 0001 — Routing engine: local Valhalla

**Date:** 2026-04-28
**Status:** accepted

## Context
The core experiment requires firing many isochrone calls per origin, for many origins (O(N²) origins ≈ thousands for an Austin grid). Hosted APIs (ORS, Mapbox, Google) impose rate limits, per-call cost, or both. Local routing is required for the project to be feasible at all.

## Decision
Run **Valhalla** locally in Docker (`gis-ops/docker-valhalla` image) against a regional OSM extract. Expose the HTTP `/isochrone` endpoint on localhost.

## Alternatives
- **OSRM** — fast routing, but no first-class isochrone endpoint; would need to roll our own from many `/route` or `/table` calls.
- **GraphHopper** — has isochrones, comparable feature set, but Valhalla's polygon output is a closer fit and the Docker story is more turnkey for our purposes.
- **OpenRouteService self-host** — heavier, Java-stack, more moving parts.
- **Hosted ORS / Mapbox** — fine for prototyping a single point but blocks the actual study; rejected as a primary path.

## Consequences
- Need Docker (OrbStack on macOS).
- One-time tile-build cost per OSM extract (minutes for a city, longer for a state).
- Locked into Valhalla's isochrone polygon shape/quality. If it turns out to be too coarse for tensor fitting, revisit (could compute isochrones ourselves from a `/route` or shortest-path tree, or switch engines).
- We avoid all per-call cost and all rate limits. This is the whole point.
