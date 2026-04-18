# Earth Twin Backend

Earth Twin Backend is a FastAPI service for global infrastructure planning and environmental simulation.

The backend no longer boots from a fixed Illinois demo world. It now builds a dynamic global baseline around the 7 continents and supports a location-first planner flow:
- the world view is continent-based
- planning starts from latitude/longitude, not a predefined demo parcel
- current baseline conditions are pulled from public data providers where possible
- simulations run from that current baseline instead of from hardcoded demo zones
- authenticated users can save planning snapshots in `My Projects`

Important: this is now more realistic than the original demo, but it is still a planning simulator, not a scientific digital twin of Earth.

## What Is Real Now

The backend currently uses public data to build live or latest-available baseline conditions:
- Open-Meteo weather for current temperature
- Open-Meteo air-quality for current AQI
- World Bank public indicators where available for land-cover and density context
- Nominatim reverse geocoding for country and state enrichment
- optional Postgres-backed provider cache for persistent snapshot reuse across restarts

The world is generated as 7 continent records:
- `continent_africa`
- `continent_antarctica`
- `continent_asia`
- `continent_europe`
- `continent_north_america`
- `continent_oceania`
- `continent_south_america`

Each continent is returned through the existing world and zone APIs, but the records now represent continent-scale regions instead of demo parcels.

## What Is Still Modeled

Not every environmental signal can be truly real-time.

These parts are still modeled or inferred:
- sustainability score weighting
- long-term scenario deltas after a build proposal
- project impact rules like roadway, industrial, restoration, and tree-loss effects
- biodiversity and ecosystem-health synthesis from the observed baseline metrics

So the product should now be described like this:
- baseline conditions are source-backed
- future project impact is modeled
- recommendations are scenario estimates, not guarantees

## Core Product Flows

### 1. Global World Baseline

`GET /api/v1/world`

Returns the dynamic global baseline world with 7 continent entries.

`POST /api/v1/world/reset`

Refreshes the world from the current public baseline sources.

### 2. Continent Views

`GET /api/v1/zones`

Returns the 7 continent records.

`GET /api/v1/zones/{zone_id}`

Returns a continent detail view with:
- risk summary
- top drivers
- recommended focus

### 3. Global Planning Metadata

`GET /api/v1/planning/site`

Returns planner metadata for the global location-first flow:
- `site_id` = `global_location_planner`
- continent list
- current continent risk levels
- supported infrastructure sections

`GET /api/v1/planning/build-options`

Returns the infrastructure form schema for:
- road
- bridge
- buildings
- airport
- general_area
- solar_panel

### 4. Geometry Resolution

`POST /api/v1/planning/geometry/resolve`

Frontend sends:
- `location`
- `infrastructure_type`
- `geometry_points`
- `infrastructure_details`

Backend returns:
- resolved location context
- resolved continent context
- reverse-geocoded country and state when available
- geometry summary
- derived infrastructure values

### 5. Proposal Assessment

`POST /api/v1/planning/proposals/assess`

Frontend sends:
- `location`
- infrastructure details or project type details
- mitigation commitment

Backend:
1. resolves the continent from the submitted coordinates
2. reverse-geocodes the point for country and state context when available
3. builds a live/current location baseline
4. reuses cached provider snapshots when possible
5. inserts that baseline into the global world copy
6. runs submitted and mitigated scenarios
7. returns scorecards and recommendation

### 6. Text-To-Plan Draft And Run

`POST /api/v1/planning/text/draft`

Frontend sends:
- `location`
- mapped `geometry_points`
- `user_prompt`

Backend:
1. retrieves the relevant internal planner schema for airport vs road
2. asks Gemini to extract the likely planning fields
3. merges geometry-derived values from the mapped line
4. returns a reviewable draft with missing fields, assumptions, confidence, and readiness

`POST /api/v1/planning/text/run`

Frontend sends the same input plus:
- `mitigation_commitment`
- optional `confirmed_overrides`

Backend:
1. repeats the grounded extraction flow
2. applies user-confirmed overrides
3. validates required fields
4. runs the existing proposal assessment pipeline
5. returns both the extraction summary and the final simulation result

## Current Planner Contract

Location is now explicit.

Example `location` object:

```json
{
  "latitude": 41.8781,
  "longitude": -87.6298,
  "label": "Chicago Test Location",
  "country_code": "USA"
}
```

Example geometry resolve request:

```json
{
  "location": {
    "latitude": 41.8781,
    "longitude": -87.6298,
    "label": "Chicago Test Location",
    "country_code": "USA"
  },
  "infrastructure_type": "road",
  "geometry_points": [
    { "latitude": 41.6401, "longitude": -87.5601 },
    { "latitude": 41.6501, "longitude": -87.5401 }
  ],
  "infrastructure_details": {
    "lane_count": 4,
    "daily_vehicle_trips": 1800,
    "construction_years": 3
  }
}
```

Example proposal assessment request:

```json
{
  "location": {
    "latitude": 41.8781,
    "longitude": -87.6298,
    "label": "Chicago Freight Corridor",
    "country_code": "USA"
  },
  "infrastructure_type": "airport",
  "geometry_points": [
    { "latitude": 41.6400, "longitude": -87.5700 },
    { "latitude": 41.6540, "longitude": -87.5450 }
  ],
  "infrastructure_details": {
    "runway_width_m": 45,
    "terminal_area_sq_m": 18000,
    "apron_area_sq_m": 42000,
    "daily_vehicle_trips": 3200,
    "construction_years": 5
  },
  "mitigation_commitment": "medium",
  "planner_notes": "Regional cargo airport expansion."
}
```

## Frontend Responsibilities

Frontend should handle:
- map rendering
- point selection
- polygon/line drawing
- location picker UX
- account/session UX if added later
- rendering scorecards, charts, and reports

Frontend should not hardcode:
- geometry math
- continent resolution
- infrastructure field rules
- scorecard generation
- mitigation comparison logic

## Backend Responsibilities

Backend now owns:
- continent world generation
- location-to-continent resolution
- reverse geocoding and country normalization
- public baseline ingestion
- cached provider snapshots, with optional Postgres persistence
- geometry resolution
- infrastructure normalization
- project simulation
- sustainability/risk scoring
- comparison between submitted and mitigated plans
- Supabase token verification for protected routes
- user-owned project snapshot persistence and report metadata

## Auth And My Projects

Supabase should handle sign-in on the frontend. The frontend then sends the Supabase access token to the backend as:

```http
Authorization: Bearer <supabase_access_token>
```

Protected backend routes:
- `GET /api/v1/auth/me`
- `GET /api/v1/my-projects`
- `POST /api/v1/my-projects`
- `GET /api/v1/my-projects/{project_id}`
- `PATCH /api/v1/my-projects/{project_id}/report`

`My Projects` stores:
- the saved planning assessment snapshot
- the recommendation and comparison output
- optional text-planning extraction metadata from the prompt flow
- later AI analysis text or PDF metadata

It does not store the whole mutable simulation world state.

## Recommended Frontend Flow

1. Call `GET /api/v1/planning/site`
2. Call `GET /api/v1/planning/build-options`
3. Let user choose infrastructure type
4. Let user pick a real location on the map
5. Let user draw geometry
6. Call `POST /api/v1/planning/geometry/resolve`
7. Show derived values and resolved continent
8. Call `POST /api/v1/planning/proposals/assess`
9. Render:
   - `location_context`
   - `submitted_plan`
   - `mitigated_plan`
   - `recommended_option`
   - `comparison_summary`
10. If the user is signed in, call `POST /api/v1/my-projects`
11. When a report is generated later, call `PATCH /api/v1/my-projects/{project_id}/report`

For text-driven planning:
1. Let the user map the line first
2. Collect a natural-language prompt like “I want to build an airport in this area”
3. Call `POST /api/v1/planning/text/draft`
4. Show the extracted fields, missing values, and confidence
5. Let the user confirm any overrides
6. Call `POST /api/v1/planning/text/run`
7. Optionally save the finished result to `My Projects`

## Other API Endpoints

### Health
- `GET /api/v1/health`

### Raw Simulation
- `POST /api/v1/simulation/apply`
- `POST /api/v1/simulation/project`
- `POST /api/v1/simulation/compare`

### Scenario Templates
- `GET /api/v1/scenarios/templates`
- `GET /api/v1/scenarios/templates/{template_id}`
- `POST /api/v1/scenarios/templates/{template_id}/run`

### AI Explain
- `POST /api/v1/ai/explain`
- `POST /api/v1/ai/goal-to-actions`
- `POST /api/v1/ai/suggest-improvements`

### Report Generation
- `POST /api/v1/simulation/report`

### Text Planning
- `POST /api/v1/planning/text/draft`
- `POST /api/v1/planning/text/run`

## Deployment

Recommended free host:
- Render

Required Render settings:
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/v1/health`

Important environment variables:
- `CORS_ORIGINS`
- `GEMINI_API_KEY` if using Gemini endpoints

Optional tuning:
- `DATABASE_URL`
- `POSTGRES_HOST`
- `POSTGRES_PORT`
- `POSTGRES_DB`
- `POSTGRES_USER`
- `POSTGRES_PASSWORD`
- `SUPABASE_JWT_SECRET`
- `SUPABASE_JWT_AUDIENCE`
- `SUPABASE_JWT_ISSUER`
- `PROVIDER_CACHE_TABLE_NAME`
- `PUBLIC_DATA_TIMEOUT_SECONDS`
- `PROVIDER_CACHE_TTL_SECONDS`
- `PROVIDER_CACHE_CONNECT_TIMEOUT_SECONDS`
- `OPEN_METEO_WEATHER_URL`
- `OPEN_METEO_AIR_QUALITY_URL`
- `NOMINATIM_REVERSE_URL`
- `PUBLIC_DATA_USER_AGENT`

## Persistent Provider Cache With Docker Postgres

To keep provider snapshots warm across backend restarts, run the included Postgres service:

```bash
docker compose up -d postgres
```

Then set either:
- `DATABASE_URL=postgresql://earth_twin:earth_twin@localhost:5432/earth_twin`

or the standard component vars:
- `POSTGRES_HOST=localhost`
- `POSTGRES_PORT=5432`
- `POSTGRES_DB=earth_twin`
- `POSTGRES_USER=earth_twin`
- `POSTGRES_PASSWORD=earth_twin`

The backend creates the provider-cache table automatically on first use. If Postgres is not configured or unavailable, the app falls back to the current in-memory cache so local development still works.

The same Postgres connection is also used for authenticated `My Projects` storage.

## Local Development

```bash
cd earth-twin-backend
docker compose up -d postgres
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Local URLs:
- Base URL: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

## Limitations

- Public-data fetches depend on upstream availability.
- If a live provider is unavailable, the backend falls back to inferred baseline values so the API remains usable.
- Provider responses are cached with a TTL so repeated location lookups are faster and less dependent on upstream latency.
- If Postgres is configured, provider cache snapshots persist across restarts; otherwise the cache is in-memory only.
- Not all metrics are truly real-time; some are latest-available public indicators or modeled derivatives.
- The project-impact simulation is still rule-based, not a full scientific forecasting engine.
- The world state remains in memory.
- `My Projects` stores saved assessment snapshots, not the mutable world-state timeline.

## Verification

Current test status:
- `110 passed, 7 deselected`
