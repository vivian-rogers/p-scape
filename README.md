# isochrone-metric

A research project: derive an effective L^p exponent at every location in
a city by routing destinations on a Euclidean ring around each origin and
inverting the resulting circuity ratio against a closed-form integral.
`p ≈ 1` ↔ Manhattan grid, `p ≈ 2` ↔ Euclidean, `p < 1` ↔ cul-de-sac sprawl.

The whole project lives under [`pnorm/`](pnorm/). Start there:

- [`pnorm/AGENTS.md`](pnorm/AGENTS.md) — operational handoff, repo
  layout, end-to-end recipe, gotchas.
- [`pnorm/docs/methodology.pdf`](pnorm/docs/methodology.pdf) — math write-up
  and 6-city findings.
- [`pnorm/data/explorer.html`](pnorm/data/explorer.html) — single-page
  interactive viewer (city / mode / radius / opacity dropdowns).

> **Note on history.** Earlier commits in this repo's `main` branch
> contained a parallel "Riemannian ellipse fit" track under `src/`,
> `scripts/`, `docs/`, and a Valhalla `docker-compose.yml`. That track
> has been removed; the OSRM-based pnorm pipeline is the only live
> work. The earlier commits remain accessible in git history.
