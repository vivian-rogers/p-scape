# isochrone-metric

Treat travel-time as a Riemannian-ish metric on geographic space and study how it deviates from the Euclidean norm.

## Idea

For a routing function τ(x, y) = travel time from x to y on a real network:

1. **Sample isochrones** from many origin points x ∈ Ω.
2. At each x, fit the local *effective-time* tensor g(x) — a (possibly anisotropic) quadratic form on the tangent plane such that
   τ(x, x+v) ≈ √(vᵀ g(x) v)
   for small v. This is the differential-geometry reframing: g is a Riemannian metric, the isochrone level sets are its geodesic balls.
3. Aggregate to a global L^p norm of the deviation g(x) vs. a reference (Euclidean / great-circle) metric:
   ‖τ − d‖_p = (∫_Ω |τ(x, ·) − d(x, ·)|^p dx)^(1/p)
4. Map the resulting field. Look for where the network is "stretched" — bridges, freeways, transit corridors, mountains.

Naive pairwise comparison is O(N⁴). Tensor-fitting at each origin from a single isochrone call is O(N²) and is what we'll actually do.

## Status

Bootstrapping. No code yet beyond a stub.

## Layout

```
src/isochrone_metric/   # package
notebooks/              # exploration
data/                   # gitignored — raw OSM, cached isochrones
```

## Setup

```sh
uv sync
cp .env.example .env
```

For the routing backend, plan is local Valhalla in Docker on a regional OSM extract. TBD.
