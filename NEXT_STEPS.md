# NOSTALGIA Chart Preview Next Steps

## Current Direction

Build the online viewer as a static-image based site:

- Render all chart preview images ahead of time.
- Store generated images in a static location or object storage.
- Deploy the Vercel site as a search/index frontend only.
- The frontend should load `library_index.json`, let users search songs, select difficulty, and display the matching image.

This is similar to sdvx.in: each chart page displays pre-rendered image layers/assets instead of rendering the chart dynamically on request.

## Current Local State

- Hidden notes are ignored by the parser and preview renderer.
- Default note style should remain the original texture style.
- Rounded-note experiments should not be used as the default.
- A local FastAPI prototype exists for search and render job testing.
- `library_index.json` has been generated from the local NOSTALGIA contents.
- Several sample Real charts have already been generated for visual comparison.
- Full PNG export is running in tmux session `nostalgia_export`.
- The static viewer now reads `public/chart_index.json` and displays pre-rendered `/charts/...` images directly.
- `public/index.html` plus `public/static/` is the deployable static frontend.
- `vercel.json` points Vercel at `public/` and sets cache headers for index/static/chart assets.
- `batch_export.py` can now export either PNG or WebP. Use `run_full_export_webp.sh` after the current PNG export finishes.

## Recommended Work Order

1. Optimize preview quality on individual charts first.
   - Confirm note texture/style.
   - Confirm vertical spacing and density.
   - Confirm image width and scaling.
   - Confirm background/bar meaning and visibility.
   - Confirm output format, likely WebP for production.

2. Add a batch export command.
   - Iterate all songs and available difficulties from `library_index.json`.
   - Render each chart to a stable path such as `public/charts/<basename>/<difficulty>.webp`.
   - Skip existing files unless a force option is provided.
   - Produce a frontend-ready index with image URLs.

3. Build the Vercel frontend around pre-rendered assets.
   - Search songs by title, artist, basename.
   - Select difficulty.
   - Display metadata and preview image.
   - Avoid server-side rendering of charts on Vercel.
   - Initial static frontend is in place; next polish pass should focus on mobile layout, image loading state, and empty/error states.

4. Decide storage after estimating generated image size.
   - Small enough: keep images in Vercel `public/`.
   - Larger set: use object storage such as Vercel Blob, Cloudflare R2, or S3.
   - For storage pressure, prefer WebP and possibly split very tall charts into tiles.
   - Current PNG projection is over 2 GB, so WebP and/or object storage should be treated as the production path.

## Immediate Next Commands

Check PNG export:

```bash
./export_status.sh
```

Estimate current/final asset size:

```bash
./estimate_export_size.py
```

After PNG export finishes, run WebP export:

```bash
./run_full_export_webp.sh
```

Check WebP export:

```bash
./export_webp_status.sh
```

## Deferred Ideas

- Dynamic rendering with custom parameters should be a separate worker service, not a Vercel serverless function.
- Temporary image cleanup only matters for dynamic rendering. It is not needed for the static pre-rendered path.
- A cache key based on renderer version and render parameters can be reused if dynamic rendering returns later.
