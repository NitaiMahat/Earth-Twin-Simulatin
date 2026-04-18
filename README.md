# Earth Twin Backend

Earth Twin Backend is a FastAPI service for an infrastructure planning demo with two product modes:
- `Education`
- `Builders`

Both modes use the same simulation engine, geometry tools, and Illinois demo planning site, but they serve different users.

- `Education` is open access and designed for exploration, learning, and scenario-based demos.
- `Builders` is gated and designed for authenticated builder workflows inside backend-managed USA sites and areas.

This backend is designed to be easy for frontend teams to use:
- it exposes planner-friendly endpoints
- it describes which form fields each infrastructure type needs
- it supports map-driven point selection
- it calculates geometry from clicked map points
- it converts those values into a simulation automatically
- it now stores builder project history, reports, and prior simulation snapshots

Important: this is a deterministic planning demo backend, not a scientific climate model and not a full GIS platform.

## What The Product Does

The backend supports a shared planning workflow:
1. choose a demo planning area in Illinois
2. choose an infrastructure type such as road, bridge, buildings, airport, general area, or solar panel
3. either fill in infrastructure details manually or draw/select points on a map
4. let the backend derive values like road length, runway length, or site area
5. run a 5-year simulation
6. compare the submitted plan against a stronger mitigated alternative
7. return a planner-friendly scorecard and recommendation

On top of that shared engine, the product is now split into two backend surfaces:

### Education Mode

- open access
- no account required
- lighter scenario and learning flow
- stateless in v1
- suited for classrooms, demos, and public exploration

### Builders Mode

- authenticated using third-party-style bearer tokens in this demo build
- limited to backend-managed USA builder sites and areas
- supports project creation, simulation, report retrieval, and history review
- stores full proposal/report snapshots so users can reopen prior work

The current demo is centered on one fixed site:
- `illinois_calumet_corridor_demo`

Within that site, the user chooses one of three proposal areas:
- `calumet_industrial_strip`
- `arterial_infill_corridor`
- `river_buffer_redevelopment`

## Why It Is Useful

This backend is useful because it gives a frontend application a ready-made planning engine without requiring the frontend to own complex business logic.

It helps with:
- infrastructure proposal intake
- dynamic form generation
- map-based geometry input
- environmental risk explanation
- scenario comparison
- demo-ready recommendation outputs
- builder report retrieval
- project history persistence within the running service

For planners and municipalities, that means they can explore questions like:
- what happens if we add a new road corridor here?
- how risky is an airport runway expansion in this zone?
- what does a solar field or redevelopment area do to sustainability?
- does a mitigated version of the plan perform better?

For frontend developers, it means they do not need to hardcode:
- every infrastructure form shape
- geometry calculations
- simulation mapping logic
- planner scorecard logic
- builder access control rules
- USA builder-site eligibility rules
- report snapshot reconstruction

## Product Modes

### Education

Education mode is the open surface of the product. It should be used for:
- scenario exploration
- learning simulations
- classroom demos
- AI explanations for non-builder audiences

Education routes do not require authentication.

### Builders

Builders mode is the gated surface of the product. It should be used for:
- selecting an approved USA builder site
- creating a planning project
- running or rerunning simulations
- retrieving a saved report
- viewing project history later

Builder routes require a bearer token and the backend enforces:
- token validation
- builder-role access
- USA-only builder site selection
- owner or organization access checks for project reads

## Current Infrastructure Types

The backend currently supports these infrastructure sections:
- `road`
- `bridge`
- `buildings`
- `airport`
- `general_area`
- `solar_panel`

Each section includes its own field definitions and map interaction mode.

Examples:
- `road`
  - lane count
  - daily vehicle trips
  - optional paved area
  - map line tool to derive `length_km`
- `bridge`
  - deck width
  - daily vehicle trips
  - optional approach area
  - map line tool to derive `span_length_m`
- `airport`
  - runway width
  - terminal area
  - apron area
  - daily vehicle trips
  - map line tool to derive `runway_length_m`
- `buildings`
  - building count
  - total floor area
  - daily trips
  - map polygon tool to derive `site_area_sq_m`
- `general_area`
  - impervious surface percentage
  - daily trips
  - map polygon tool to derive `site_area_sq_m`
- `solar_panel`
  - capacity
  - battery storage
  - maintenance trips
  - map polygon tool to derive `panel_field_area_sq_m`

## How Map-Based Geometry Works

The backend supports a map-first frontend flow.

Frontend responsibilities:
- show the map
- let the user click points
- draw the selected line or polygon
- send the clicked points to the backend
- render the returned preview and simulation result

Backend responsibilities:
- validate the point selection
- calculate geometry values from the clicked points
- derive infrastructure-specific fields
- run the simulation
- return planner scorecards and recommendations

The current geometry calculations are backend math, not external APIs:
- line-based infrastructure uses the Haversine formula to calculate straight-line distance from latitude/longitude points
- polygon-based infrastructure converts lat/lng to a local XY plane and computes polygon area

This is intentional for the demo:
- fast
- free
- deterministic
- easy to test

Current limitation:
- it does not snap to real road networks
- it does not call parcel GIS services
- it does not use real airport or zoning datasets

So if a user clicks two points for a road, the backend computes straight-line distance, not actual road travel distance.

## Main Shared Planning Endpoints

### 1. Get Site Metadata

`GET /api/v1/planning/site`

Use this to load the Illinois demo site and its proposal areas.

### 2. Get Build Section Metadata

`GET /api/v1/planning/build-options`

Use this to drive the frontend form builder.

This endpoint returns:
- infrastructure sections
- section summaries
- field definitions
- map tool definitions

The frontend should use this endpoint to decide:
- which card to show for each infrastructure type
- which fields are required
- whether the user should draw a line or polygon
- how many points are expected

### 3. Resolve Geometry From Clicked Points

`POST /api/v1/planning/geometry/resolve`

Use this to preview geometry-derived values after the user clicks points on the map.

Examples of derived values:
- road length
- bridge span
- runway length
- site area
- solar field area

This is the best endpoint for:
- live preview
- "did the map selection work?" checks
- showing auto-filled values before simulation

### 4. Assess a Proposal

`POST /api/v1/planning/proposals/assess`

Use this to run the actual planning simulation.

This endpoint returns:
- resolved project type
- derived infrastructure details
- footprint and traffic buckets
- submitted plan scorecard
- mitigated plan scorecard
- recommended option
- comparison summary

These shared planning routes are the engine underneath both product modes.

## Education Endpoints

Education routes are open and intended for lightweight learning flows.

- `GET /api/v1/education/scenarios/templates`
- `GET /api/v1/education/scenarios/templates/{template_id}`
- `POST /api/v1/education/scenarios/templates/{template_id}/run`
- `POST /api/v1/education/simulation/project`
- `POST /api/v1/education/ai/explain`

Frontend ownership for Education:
- route users into the open education experience
- render scenario pickers, explainers, and lightweight simulation outputs
- no login or saved-project UX required in v1

## Builder Endpoints

Builder routes are authenticated and intended for saved planning work.

- `GET /api/v1/builders/sites`
- `GET /api/v1/builders/sites/{site_id}/areas`
- `POST /api/v1/builders/projects`
- `GET /api/v1/builders/projects`
- `GET /api/v1/builders/projects/{project_id}`
- `POST /api/v1/builders/projects/{project_id}/simulate`
- `GET /api/v1/builders/projects/{project_id}/report`
- `GET /api/v1/builders/projects/{project_id}/history`

What the backend owns for Builders:
- auth token validation
- builder-role authorization
- backend-managed USA site and area definitions
- proposal persistence
- report generation
- report/history retrieval

What the frontend should own for Builders:
- auth UI and session handling
- builder dashboard routing
- project list and create screens
- map interaction and clicked-point collection
- report rendering
- history/timeline visualization

## Recommended Frontend Flow

### Education Flow

1. Call `GET /api/v1/education/scenarios/templates`
2. Let the user choose a learning scenario
3. Run the scenario or open `POST /api/v1/education/simulation/project`
4. Optionally call `POST /api/v1/education/ai/explain`
5. Render the learning output without saving project state

### Builder Flow

1. Authenticate the user in the frontend
2. Send the bearer token with all builder requests
3. Call `GET /api/v1/builders/sites`
4. Call `GET /api/v1/builders/sites/{site_id}/areas`
5. Call `GET /api/v1/planning/build-options`
6. Let the user choose:
   - area
   - infrastructure type
7. Read the chosen section's `map_tool`
8. Let the user click:
   - 2 points for line tools
   - 3+ points for polygon tools
9. Call `POST /api/v1/planning/geometry/resolve`
10. Create the project with `POST /api/v1/builders/projects`
11. Run or rerun the simulation with `POST /api/v1/builders/projects/{project_id}/simulate`
12. Reopen project results later with:
   - `GET /api/v1/builders/projects/{project_id}`
   - `GET /api/v1/builders/projects/{project_id}/report`
   - `GET /api/v1/builders/projects/{project_id}/history`

### Shared Planning Flow

1. Call `GET /api/v1/planning/site`
2. Call `GET /api/v1/planning/build-options`
3. Let the user choose:
   - area
   - infrastructure type
4. Read the chosen section's `map_tool`
5. Let the user click:
   - 2 points for line tools
   - 3+ points for polygon tools
6. Call `POST /api/v1/planning/geometry/resolve`
7. Show the user the derived values
8. Submit the final proposal to `POST /api/v1/planning/proposals/assess`
9. Render:
   - `submitted_plan`
   - `mitigated_plan`
   - `recommended_option`
   - `comparison_summary`

## Example Requests

### Build Options

```bash
curl http://127.0.0.1:8000/api/v1/planning/build-options
```

### Geometry Resolve For Road

```bash
curl -X POST http://127.0.0.1:8000/api/v1/planning/geometry/resolve ^
  -H "Content-Type: application/json" ^
  -d "{\"site_id\":\"illinois_calumet_corridor_demo\",\"area_id\":\"arterial_infill_corridor\",\"infrastructure_type\":\"road\",\"geometry_points\":[{\"latitude\":41.6401,\"longitude\":-87.5601},{\"latitude\":41.6501,\"longitude\":-87.5401}],\"infrastructure_details\":{\"lane_count\":4,\"daily_vehicle_trips\":1800,\"construction_years\":3}}"
```

### Proposal Assessment For Airport Using Map Points

```bash
curl -X POST http://127.0.0.1:8000/api/v1/planning/proposals/assess ^
  -H "Content-Type: application/json" ^
  -d "{\"site_id\":\"illinois_calumet_corridor_demo\",\"area_id\":\"calumet_industrial_strip\",\"infrastructure_type\":\"airport\",\"geometry_points\":[{\"latitude\":41.6400,\"longitude\":-87.5700},{\"latitude\":41.6540,\"longitude\":-87.5450}],\"infrastructure_details\":{\"runway_width_m\":45,\"terminal_area_sq_m\":18000,\"apron_area_sq_m\":42000,\"daily_vehicle_trips\":3200,\"construction_years\":5},\"mitigation_commitment\":\"medium\",\"planner_notes\":\"Regional cargo airport expansion.\"}"
```

### Builder Project Create

```bash
curl -X POST http://127.0.0.1:8000/api/v1/builders/projects ^
  -H "Authorization: Bearer builder-demo-token" ^
  -H "Content-Type: application/json" ^
  -d "{\"project_name\":\"Calumet runway plan\",\"site_id\":\"usa_calumet_builder_site\",\"area_id\":\"calumet_industrial_strip\",\"infrastructure_type\":\"airport\",\"geometry_points\":[{\"latitude\":41.6400,\"longitude\":-87.5700},{\"latitude\":41.6540,\"longitude\":-87.5450}],\"infrastructure_details\":{\"runway_width_m\":45,\"terminal_area_sq_m\":18000,\"apron_area_sq_m\":42000,\"daily_vehicle_trips\":3200,\"construction_years\":5},\"mitigation_commitment\":\"medium\",\"planner_notes\":\"Builder runway project.\"}"
```

### Builder Project Simulate

```bash
curl -X POST http://127.0.0.1:8000/api/v1/builders/projects/{project_id}/simulate ^
  -H "Authorization: Bearer builder-demo-token" ^
  -H "Content-Type: application/json" ^
  -d "{}"
```

## Other API Endpoints

### Health
- `GET /api/v1/health`

### World State
- `GET /api/v1/world`
- `POST /api/v1/world/reset`

### Zone Views
- `GET /api/v1/zones`
- `GET /api/v1/zones/{zone_id}`

### Raw Simulation APIs
- `POST /api/v1/simulation/apply`
- `POST /api/v1/simulation/project`
- `POST /api/v1/simulation/compare`

## Deployment

This repo is ready for GitHub-based deployment.

Included deploy files:
- `render.yaml`
- `Procfile`
- `runtime.txt`

Recommended free hosting path:
- Render

Current deployed example:
- docs: `https://earth-twin-simulatin.onrender.com/docs`
- base: `https://earth-twin-simulatin.onrender.com`

Important environment variable:
- `CORS_ORIGINS`
  - set to `*` for broad demo access
  - or set to specific frontend domains like:
  - `http://localhost:3000,https://your-frontend-domain.vercel.app`

Render settings:
- Build Command: `pip install -r requirements.txt`
- Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health Check Path: `/api/v1/health`

## Local Development

```bash
cd earth-twin-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Local URLs:
- Base URL: `http://127.0.0.1:8000`
- Swagger docs: `http://127.0.0.1:8000/docs`

## Project Layout

```text
earth-twin-backend/
  app/
    api/v1/endpoints/
    core/
    data/
    models/
    repositories/
    rules/
    services/
  tests/
  render.yaml
  Procfile
  runtime.txt
  requirements.txt
  README.md
```

## Notes And Limitations

- The world state is stored in memory only.
- Builder projects and builder history are also stored in memory only in this demo build.
- Restarting the service or calling `/api/v1/world/reset` restores the seed data.
- Restarting the service clears saved builder projects.
- This is a demo backend, not a production persistence layer.
- Geometry is calculated internally from map points and is approximate.
- The backend currently does not connect to real parcel GIS, road routing, or zoning APIs.
- Demo builder tokens are stored in local seed data to mimic third-party auth claims.
- The raw simulation endpoints remain available, but the education and builder endpoints are the recommended product-facing integration path.
