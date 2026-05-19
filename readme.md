# Dulo Runtime Extractor

Simple FastAPI backend for extracting runtime stream data from Dulo watch pages.

This project resolves the full chain and returns the final JSON with:

- `sources`
- `tracks`
- `encrypted`
- provider response details

It supports:

- Movies
- TV series
- Anime

## What This Project Does

You send one request to the API.

The backend then:

1. Opens the Dulo hash route in a real browser, for example `https://dulo.tv/#/movie/385687`
2. Waits for the client-side app to load
3. Clicks a visible play/watch control when one is present
4. Follows discovered player iframes
5. Captures source JSON, HLS/MP4 stream URLs, and subtitle tracks from runtime network traffic

The response includes captured playable links in `sources` when Dulo exposes them during runtime.

## Features

- Movie support
- TV support
- Anime support
- Dulo hash-route support for `https://dulo.tv/#/movie/<tmdb id>`
- Runtime stream source extraction
- Expiring HLS/source URL metadata and forced refresh endpoint
- Subtitle track extraction
- Clean docs page at `/`
- Backend-only flow

## Project Files

- `api.py` - FastAPI app and docs page
- `extractor.py` - main Dulo browser/runtime extraction logic
- `vrf_generator.py` - legacy standalone VRF generator

## Requirements

- Python 3.11+ recommended

Python packages:

- `fastapi`
- `uvicorn`
- `httpx`
- `beautifulsoup4`
- `cryptography`

## Install

```bash
pip install fastapi uvicorn httpx beautifulsoup4 cryptography
```

## Run

```bash
python api.py
```

Default server:

```text
http://127.0.0.1:5050
```

## API Endpoint

### `GET /extract`

Returns the extracted stream payload. When a source URL contains a signed expiry token, the response includes expiry and refresh metadata.

### `GET /refresh`

Uses the same query params as `/extract`, but bypasses the in-memory source cache and forces a fresh browser extraction. Use this endpoint when `refresh_after` is reached, when `refresh_required` is true, or when playback gets a 401/403 from an expiring HLS URL.

Query params:

- `id` - title ID
- `type` - `movie`, `tv`, or `anime`
- `season` - required for TV
- `episode` - required for TV and anime
- `lang` - anime language, usually `sub` or `dub`

## ID Rules

### Movies

Movies use the TMDb ID in the Dulo route:

Examples:

- `385687` -> `https://dulo.tv/#/movie/385687`
- `559969` -> `https://dulo.tv/#/movie/559969`

### TV Series

TV can use:

- TMDb ID
- IMDb ID

Examples:

- `60735`
- `1399`
- `tt0944947`

### Anime

Anime has two common ID styles here:

- AniList anime ID: use `ani` before the AniList number
- MAL ID: use the plain MAL number only

Examples:

- AniList: `ani178005`
- MAL: `52991`

Simple rule:

- AniList -> `ani<anilist_id>`
- MAL -> `<mal_id>`

## Example Requests

### Movie with TMDb ID

```text
/extract?id=385687&type=movie
```

### TV with TMDb ID

```text
/extract?id=60735&type=tv&season=1&episode=1
```

### TV with IMDb ID

```text
/extract?id=tt0944947&type=tv&season=1&episode=1
```

### Anime with AniList ID

```text
/extract?id=ani178005&type=anime&episode=1&lang=sub
```

### Anime with MAL ID

```text
/extract?id=52991&type=anime&episode=1&lang=sub
```

### Anime dub example

```text
/extract?id=21&type=anime&episode=1&lang=dub
```

## Example Response Shape

```json
{
  "sources": [
    {
      "file": "https://...m3u8",
      "type": "hls",
      "expires_at": 1779154217,
      "expires_in_seconds": 3600,
      "is_expiring": true,
      "refresh_url": "/refresh?id=385687&type=movie&lang=sub"
    }
  ],
  "tracks": [
    {
      "file": "https://...vtt",
      "label": "English",
      "kind": "captions",
      "default": true
    }
  ],
  "encrypted": false,
  "expires_at": 1779154217,
  "refresh_after": 1779154097,
  "refresh_required": false,
  "refresh": {
    "url": "/refresh?id=385687&type=movie&lang=sub",
    "method": "GET"
  }
}
```

## Response Fields

- `sources` - playable stream URLs
- `tracks` - subtitle files
- `type` - stream type, usually `hls`
- `encrypted` - whether the final payload is still encrypted
- `expires_at` / `expires_in_seconds` - earliest detected signed source expiry
- `refresh_after` / `refresh_after_seconds` - when clients should proactively refresh, currently two minutes before expiry
- `refresh_required` - true when the detected source expiry has already passed
- `refresh.url` - relative API URL that forces a fresh source extraction

## Notes

- Anime may return different paths depending on `lang=sub` or `lang=dub`
- TV requires both `season` and `episode`
- Movies only need a TMDb `id` and `type=movie`; the extractor opens `https://dulo.tv/#/movie/<id>` internally
- Some providers return signed HLS URLs that expire; use the returned `refresh.url` instead of persisting old source URLs
- Some providers change behavior over time, so extraction logic may need updates later

## VRF

This repo includes a working VRF generator in:

- `vrf_generator.py`

That script is useful if you want to test the Vidsrc request flow separately from the API.

## Local Docs UI

After starting the server, open:

```text
http://127.0.0.1:5050/
```

The homepage includes:

- quick test buttons
- movie examples
- TV examples
- anime examples
- ID rules

## GitHub

Repository:

```text
https://github.com/walterwhite-69/Vidsrc.cc-Decryptor
```

## Developer

Walter


## Railway Deployment

1. Push this repo to GitHub.
2. In Railway, create a **New Project** -> **Deploy from GitHub repo**.
3. Railway uses Nixpacks via `nixpacks.toml` to install:
   - Python + required system libraries
   - Python dependencies from `requirements.txt`
   - Playwright Chromium binaries (`playwright install --with-deps chromium`)
4. Start command is provided via `Procfile`:

```text
web: ./scripts/bootstrap_playwright.sh uvicorn api:app --host 0.0.0.0 --port ${PORT:-5050}
```

Railway sets the `PORT` environment variable automatically.

### Why this fixes the common Railway Playwright crash

If Railway logs include missing paths like:

```text
...chrome-headless-shell-linux64...
```

that means Chromium was not present in runtime. This repo now handles that in two layers:

1. **Build-time install** in `nixpacks.toml` (`playwright install --with-deps chromium`)
2. **Runtime guard** in `scripts/bootstrap_playwright.sh` that verifies Chromium exists and installs it if missing

This makes deployments resilient even when runtime storage is ephemeral or build cache changes.

### Optional Railway Variables

You usually do not need extra variables for this project, but you can add:

- `PYTHONUNBUFFERED=1`

### Railway Query Examples

Replace `<your-railway-domain>` with your live URL, for example `vidsrc-api-production.up.railway.app`.

```bash
# Health / docs page
curl "https://<your-railway-domain>/"

# Movie (TMDb ID)
curl "https://<your-railway-domain>/extract?id=385687&type=movie"

# Movie (IMDb ID)
curl "https://<your-railway-domain>/extract?id=tt9243946&type=movie"

# TV
curl "https://<your-railway-domain>/extract?id=60735&type=tv&season=1&episode=1"

# Anime (AniList ID)
curl "https://<your-railway-domain>/extract?id=ani178005&type=anime&episode=1&lang=sub"

# Anime (MAL ID)
curl "https://<your-railway-domain>/extract?id=52991&type=anime&episode=1&lang=dub"
```

### Railway Dashboard Query Tests

You can also test directly in a browser using these paths on your deployed domain:

- `/extract?id=385687&type=movie`
- `/extract?id=tt0944947&type=tv&season=1&episode=1`
- `/extract?id=ani178005&type=anime&episode=1&lang=sub`
