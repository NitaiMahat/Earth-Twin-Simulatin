# Earth Twin Backend

FastAPI backend for global infrastructure planning and environmental impact simulation. Users describe infrastructure projects in natural language or via a map-driven form, and the backend runs a full environmental assessment against a live continent-scale world baseline.

**Production URL:** `https://earth-twin-simulatin.onrender.com`
**Docs (local):** `http://127.0.0.1:8000/docs`

---

## What It Does

1. **Builds a live global world** from 7 continent zones seeded with real public data (weather, air quality, land cover, population density).
2. **Accepts infrastructure proposals** via natural language chat or a structured form with map geometry.
3. **Runs an environmental simulation** — submitted plan vs. mitigated plan — and returns scorecards, risk level, sustainability score, and a verdict.
4. **Generates AI-written PDF reports** via Gemini, uploaded to Supabase Storage.
5. **Saves authenticated users' projects** to a Postgres-backed snapshot store.

---

## What Is Real

The backend pulls live or latest-available public data to seed baseline conditions:

| Source | What it provides |
|---|---|
| Open-Meteo Weather API | Current surface temperature |
| Open-Meteo Air Quality API | Current AQI (US standard) |
| World Bank Indicators API | Forest area %, population density by country |
| Nominatim (OpenStreetMap) | Reverse geocoding — country, state, city label |
| Nominatim (OpenStreetMap) | Forward geocoding — text address → lat/lon |

Provider responses are cached in memory (TTL: 1 hour by default) and optionally persisted to Postgres across restarts. If a provider is unavailable, the backend falls back to modeled baseline values so the API remains usable.

---

## What Is Modeled

These parts are not real-time — they are simulation rules or weighted derivations:

- Sustainability score (weighted formula across 6 environmental metrics)
- Project impact rules (traffic, pollution, tree cover, biodiversity, ecosystem health deltas)
- Long-term scenario projections
- Biodiversity and ecosystem health synthesis from observed baseline metrics

The product is a **planning simulator with source-backed baselines**, not a scientific digital twin.

---

## Zone IDs

The world is always seeded with these 7 continent zones:

| Zone ID | Name |
|---|---|
| `continent_africa` | Africa |
| `continent_antarctica` | Antarctica |
| `continent_asia` | Asia |
| `continent_europe` | Europe |
| `continent_north_america` | North America |
| `continent_oceania` | Oceania |
| `continent_south_america` | South America |

---

## Supported Infrastructure Types

The following types are accepted across all planning and text endpoints:

| Value | Description |
|---|---|
| `road` | Road segment, corridor, or logistics access road |
| `highway` | Motorway, freeway, or high-capacity inter-city corridor |
| `bridge` | Bridge, flyover, crossing, or elevated connector |
| `building` / `buildings` | Single building or building cluster — residential, commercial, civic |
| `airport` | Airport, runway upgrade, freight apron, or terminal expansion |
| `solar_farm` / `solar_panel` | Ground-mounted solar field, utility-scale PV, or solar-plus-storage |
| `dam` | Dam, weir, reservoir, or hydro-electric infrastructure |
| `industrial` | Factory, warehouse, logistics hub, or industrial zone |
| `general_area` | Broad land conversion or district-scale redevelopment (form-only, not text) |

---

## API Reference

### Health

```
GET /api/v1/health
```

### World

```
GET  /api/v1/world          → returns global world with 7 continent zones
POST /api/v1/world/reset    → refreshes world from current public baseline
```

### Zones

```
GET /api/v1/zones              → list all 7 continent zones
GET /api/v1/zones/{zone_id}    → zone detail with risk summary and top drivers
```

### Planning Metadata

```
GET /api/v1/planning/site           → planner site metadata, continent list, risk levels
GET /api/v1/planning/build-options  → full form schema for all supported infrastructure types
```

### Geometry Resolution

```
POST /api/v1/planning/geometry/resolve
```

Send `location`, `infrastructure_type`, `geometry_points`, and `infrastructure_details`.
Returns resolved continent, reverse-geocoded country/state, geometry summary, and auto-derived values (road length, runway length, site area, etc.).

### Proposal Assessment

```
POST /api/v1/planning/proposals/assess
```

Runs the full simulation pipeline. Returns submitted plan scorecard, mitigated plan scorecard, recommended option, and comparison summary.

**Request:**
```json
{
  "location": { "latitude": 35.6762, "longitude": 139.6503, "label": "Tokyo" },
  "infrastructure_type": "road",
  "geometry_points": [
    { "latitude": 35.670, "longitude": 139.640 },
    { "latitude": 35.680, "longitude": 139.660 }
  ],
  "infrastructure_details": { "lane_count": 4, "daily_vehicle_trips": 8000 },
  "mitigation_commitment": "medium"
}
```

**Response includes:**
```json
{
  "submitted_plan": {
    "plan_score": 42.0,
    "sustainability_score": 42.0,
    "verdict": "conditional",
    "overall_outlook": "WORSENING",
    "top_risks": ["..."],
    "required_mitigations": ["..."],
    "summary_text": "..."
  },
  "mitigated_plan": { "sustainability_score": 61.0, ... },
  "recommended_option": "conditional",
  "comparison_summary": "..."
}
```

> Note: `sustainability_score` and `plan_score` are the same value. Both fields are present for compatibility.

---

### AI Plan Builder — Text-To-Plan (RAG + Gemini)

The AI Plan Builder lets a user type a natural language prompt. No map interaction required.

#### How It Works

```
User types: "build a 4-lane highway from Shibuya to Narita Airport, Tokyo"
    ↓
RAG checks: is the infrastructure type supported?
    ↓
Gemini extracts:
  - infrastructure_type: "highway"
  - infrastructure_details: { lane_count: 4, ... }
  - location_mentions: ["Shibuya, Tokyo", "Narita Airport, Tokyo"]
  - location_query: "Tokyo, Japan"
    ↓
Nominatim geocodes each location_mention → lat/lon points
Nominatim geocodes location_query → resolves to continent_asia
    ↓
Returns suggested_geometry_points for auto-drawing on Cesium map
Returns resolved_zone_id for auto-selecting the simulation zone
```

#### Draft

```
POST /api/v1/planning/text/draft
```

**Request:**
```json
{
  "prompt": "build a 4-lane highway from Shibuya to Narita Airport",
  "geometry_points": []
}
```

- `prompt` — required (5–4000 chars)
- `geometry_points` — optional, send `[]` if user hasn't drawn on the map
- `location` — optional `{ latitude, longitude, label }`, omit to extract from text

**Response:**
```json
{
  "infrastructure_type": "highway",
  "project_type": "roadway_logistics_expansion",
  "planner_summary": "4-lane highway from Shibuya to Narita Airport",
  "confidence": 0.91,
  "simulation_ready": false,
  "missing_fields": ["daily_vehicle_trips"],
  "assumptions": ["Assumed urban zone based on Tokyo mention"],
  "infrastructure_details": { "lane_count": 4 },
  "resolved_zone_id": "continent_asia",
  "resolved_location_label": "Shibuya",
  "suggested_geometry_points": [
    { "latitude": 35.6580, "longitude": 139.7016, "label": "Shibuya" },
    { "latitude": 35.7720, "longitude": 140.3929, "label": "Narita Airport" }
  ],
  "location_context": {
    "label": "Shibuya",
    "latitude": 35.6580,
    "longitude": 139.7016,
    "continent_id": "asia",
    "baseline_zone_id": "continent_asia",
    "country_name": "Japan"
  }
}
```

**Key response fields:**

| Field | Purpose |
|---|---|
| `resolved_zone_id` | Auto-select this zone on the globe |
| `resolved_location_label` | Human-readable location name to display |
| `suggested_geometry_points` | Auto-draw these points on the Cesium map |
| `simulation_ready` | If `true`, go straight to `/text/run` |
| `missing_fields` | Show these as required form inputs |
| `confidence` | Below 0.65 → show warning, ask user to confirm type |

**Error — unsupported type:**
```json
{ "detail": "That infrastructure type is not supported. Supported types: road, highway, bridge, building, airport, solar farm, dam, industrial." }
```

#### Run

```
POST /api/v1/planning/text/run
```

**Request:**
```json
{
  "prompt": "build a 4-lane highway from Shibuya to Narita Airport",
  "geometry_points": [
    { "latitude": 35.6580, "longitude": 139.7016 },
    { "latitude": 35.7720, "longitude": 140.3929 }
  ],
  "mitigation_commitment": "medium",
  "confirmed_overrides": {
    "infrastructure_type": "highway",
    "infrastructure_details": { "lane_count": 4, "daily_vehicle_trips": 12000 }
  }
}
```

- Use `suggested_geometry_points` from the draft response if user hasn't drawn manually
- `mitigation_commitment` — `"low"` | `"medium"` | `"high"`, required
- `confirmed_overrides` — use to fill in `missing_fields` from draft

**Response:**
```json
{
  "extraction": { "...same shape as draft response..." },
  "assessment": {
    "submitted_plan": { "sustainability_score": 38.0, "verdict": "not_recommended", ... },
    "mitigated_plan": { "sustainability_score": 57.0, "verdict": "conditional", ... },
    "recommended_option": "conditional",
    "comparison_summary": "..."
  }
}
```

**Decision flow:**
```
POST /text/draft
    ↓
resolved_zone_id → auto-select zone on globe
suggested_geometry_points → auto-draw on Cesium map
    ↓
simulation_ready = true?  →  POST /text/run immediately
simulation_ready = false? →  show missing_fields form, wait for input
confidence < 0.65?        →  show warning, confirm infrastructure_type
    ↓
POST /text/run → show assessment scorecard
```

---

### Raw Simulation

```
POST /api/v1/simulation/apply    → apply one action to a zone, returns before/after deltas
POST /api/v1/simulation/project  → project multiple actions over N years (max 50)
POST /api/v1/simulation/compare  → compare named scenarios side by side
POST /api/v1/simulation/report   → generate Gemini-written analysis + stream as PDF
```

### Scenario Templates

```
GET  /api/v1/scenarios/templates                    → list available scenario templates
GET  /api/v1/scenarios/templates/{template_id}      → template detail
POST /api/v1/scenarios/templates/{template_id}/run  → run a template scenario
```

### AI Endpoints

All 3 endpoints accept an optional `location_label` field. When provided, AI responses use the specific city or address ("Tokyo, Japan") instead of the continent name ("Asia").

```
POST /api/v1/ai/explain
```
```json
{
  "zone_id": "continent_asia",
  "question": "Why is biodiversity declining here?",
  "mode": "planning",
  "location_label": "Tokyo, Japan"
}
```

```
POST /api/v1/ai/goal-to-actions
```
```json
{
  "goal": "Reduce pollution by 30% in 5 years",
  "zone_id": "continent_asia",
  "location_label": "Tokyo, Japan"
}
```

```
POST /api/v1/ai/suggest-improvements
```
```json
{
  "goal": "Reduce pollution",
  "zone_id": "continent_asia",
  "zone_name": "Asia",
  "location_label": "Tokyo, Japan",
  "actions": [...],
  "initial_metrics": {...},
  "final_metrics": {...},
  "projection_years": 10,
  "sustainability_score": 58.0,
  "overall_outlook": "IMPROVING"
}
```

---

## Auth and My Projects

Supabase handles authentication on the frontend. The frontend sends the Supabase access token to the backend on protected routes:

```http
Authorization: Bearer <supabase_access_token>
```

The backend verifies the JWT against the Supabase JWKS endpoint (modern ES256/RS256 tokens) or via `SUPABASE_JWT_SECRET` (legacy HS256 projects only).

**Protected routes:**
```
GET    /api/v1/auth/me
GET    /api/v1/my-projects
POST   /api/v1/my-projects
GET    /api/v1/my-projects/{project_id}
PATCH  /api/v1/my-projects/{project_id}/report
POST   /api/v1/my-projects/{project_id}/report/generate
```

**What My Projects stores:**
- Full planning assessment snapshot (JSONB)
- Recommendation and comparison output
- Optional text-planning extraction metadata (prompt, confidence, inferred type)
- Optional AI analysis text and PDF metadata (storage path, signed URL)

**PDF report flow:**
1. `POST /my-projects` → saves the project, returns `project_id`
2. `POST /my-projects/{project_id}/report/generate` → backend generates PDF, uploads to Supabase Storage, saves metadata
3. `GET /my-projects/{project_id}` → returns fresh signed URL for the PDF (valid 1 hour, auto-refreshed)

---

## Recommended Frontend Flows

### Form-Driven Flow

1. `GET /api/v1/planning/site` — load planner metadata
2. `GET /api/v1/planning/build-options` — load form schema for selected infrastructure type
3. User picks location on map + draws geometry
4. `POST /api/v1/planning/geometry/resolve` — get derived values and resolved continent
5. `POST /api/v1/planning/proposals/assess` — run simulation, display scorecards
6. `POST /api/v1/my-projects` (authenticated) — save project
7. `POST /api/v1/my-projects/{id}/report/generate` — generate and upload PDF report

### AI Chat Flow (Text-To-Plan)

1. User types a natural language prompt
2. `POST /api/v1/planning/text/draft`
   - Auto-select zone from `resolved_zone_id`
   - Auto-draw map points from `suggested_geometry_points`
   - Show missing fields if `simulation_ready: false`
3. User fills any missing fields
4. `POST /api/v1/planning/text/run` — run simulation, display scorecards
5. Optionally save to My Projects

### Goal-to-Simulation Flow

1. User types a sustainability goal
2. `POST /api/v1/ai/goal-to-actions` — Gemini returns 2–4 recommended actions
3. `POST /api/v1/simulation/project` — project those actions over N years
4. `POST /api/v1/simulation/report` — generate Gemini analysis PDF

---

## Frontend Responsibilities

- Map rendering (Cesium)
- Point/polygon/line drawing on the map
- Location search UI (Nominatim geocoding called directly from browser — no backend proxy needed)
- Auto-placing `suggested_geometry_points` on the map from text/draft response
- Auto-selecting zone from `resolved_zone_id`
- Rendering scorecards, charts, and reports
- Supabase login/session management
- Passing `Authorization: Bearer <token>` on protected routes
- Passing `location_label` to AI endpoints for city-level context

## Backend Responsibilities

- Continent world generation and live baseline seeding
- Location-to-continent resolution (coordinate-based bounding boxes + distance fallback)
- Forward geocoding — text address/zip/landmark → lat/lon (Nominatim)
- Reverse geocoding — lat/lon → country, state, city (Nominatim)
- Public data ingestion (Open-Meteo, World Bank)
- Provider cache with optional Postgres persistence
- RAG-based infrastructure type detection and template retrieval
- Gemini integration — location extraction, infrastructure field extraction, goal-to-actions, analysis reports
- Geometry resolution and auto-derived field calculation
- Infrastructure normalization and validation
- Environmental simulation rules (traffic, pollution, tree cover, biodiversity, ecosystem health)
- Sustainability and risk scoring
- Submitted vs. mitigated plan comparison
- Supabase JWT verification for protected routes
- Project snapshot persistence and PDF upload to Supabase Storage

---

## Environment Variables

**Required for core features:**

| Variable | Purpose |
|---|---|
| `GEMINI_API_KEY` | Required for all AI features (text planning, reports, goal-to-actions) |
| `DATABASE_URL` | Postgres connection string (Supabase direct connection, port 5432) |
| `SUPABASE_URL` | Supabase project URL — used for JWT verification and storage |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key — used for PDF upload to storage |
| `CORS_ORIGINS` | Frontend URL(s), comma-separated. Example: `https://yourapp.vercel.app` |

**Auth tuning (optional):**

| Variable | Default | Purpose |
|---|---|---|
| `SUPABASE_JWT_AUDIENCE` | `authenticated` | Expected JWT audience claim |
| `SUPABASE_JWT_ISSUER` | derived from `SUPABASE_URL` | Expected JWT issuer |
| `SUPABASE_JWT_SECRET` | — | Only needed for legacy HS256 projects |

**Storage (optional):**

| Variable | Default | Purpose |
|---|---|---|
| `SUPABASE_STORAGE_BUCKET` | `project-reports` | Bucket name for PDF uploads |
| `SUPABASE_STORAGE_PUBLIC` | `false` | Set `true` for public bucket, `false` for signed URLs |
| `SUPABASE_STORAGE_SIGNED_URL_TTL_SECONDS` | `3600` | Signed URL expiry |

**Provider / cache tuning (optional):**

| Variable | Default | Purpose |
|---|---|---|
| `PROVIDER_CACHE_TTL_SECONDS` | `3600` | In-memory cache TTL |
| `PROVIDER_CACHE_TABLE_NAME` | `provider_cache_entries` | Postgres cache table name |
| `PROVIDER_CACHE_CONNECT_TIMEOUT_SECONDS` | `3` | DB connection timeout |
| `PUBLIC_DATA_TIMEOUT_SECONDS` | `2.5` | Timeout for public API calls |
| `PUBLIC_DATA_USER_AGENT` | `EarthTwinBackend/0.1 ...` | User-Agent sent to Nominatim and others |
| `OPEN_METEO_WEATHER_URL` | `https://api.open-meteo.com/v1/forecast` | Override for weather API |
| `OPEN_METEO_AIR_QUALITY_URL` | `https://air-quality-api.open-meteo.com/...` | Override for AQ API |
| `NOMINATIM_REVERSE_URL` | `https://nominatim.openstreetmap.org/reverse` | Override for reverse geocoding |
| `NOMINATIM_SEARCH_URL` | `https://nominatim.openstreetmap.org/search` | Override for forward geocoding |

**Postgres component vars (alternative to DATABASE_URL):**

| Variable | Default |
|---|---|
| `POSTGRES_HOST` | — |
| `POSTGRES_PORT` | `5432` |
| `POSTGRES_DB` | `earth_twin` |
| `POSTGRES_USER` | `earth_twin` |
| `POSTGRES_PASSWORD` | `earth_twin` |

---

## Deployment (Render)

**Build command:** `pip install -r requirements.txt`
**Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
**Health check path:** `/api/v1/health`

**Minimum required env vars on Render:**
- `GEMINI_API_KEY`
- `DATABASE_URL` (use the Supabase direct connection URL, port **5432** not 6543)
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `CORS_ORIGINS` (your frontend domain, no trailing slash)

---

## Local Development

```bash
cd earth-twin-backend
docker compose up -d postgres        # optional — for persistent provider cache
python -m venv .venv
.venv\Scripts\activate               # Windows
source .venv/bin/activate            # Mac/Linux
pip install -r requirements.txt
cp .env.example .env                 # fill in your keys
uvicorn app.main:app --reload
```

- Base URL: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

The app works without Postgres — it falls back to in-memory provider cache automatically.

---

## Limitations

- Public-data fetches depend on upstream availability. If a provider is down, the backend uses modeled fallback values.
- Not all metrics are truly real-time — some use latest-available indicators or modeled derivatives.
- The simulation is rule-based, not a scientific forecasting engine.
- The world state is held in memory — it resets on restart unless `POST /world/reset` is called.
- My Projects stores assessment snapshots, not the full mutable world-state timeline.
- Text planning currently supports up to 4 geometry points from location extraction. Complex multi-waypoint routes are not yet supported.
- Signed PDF URLs expire after 1 hour. Calling `GET /my-projects/{id}` regenerates a fresh URL automatically.

---

## Test Status

`110 passed, 7 deselected`
