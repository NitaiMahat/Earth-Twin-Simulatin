# Earth Twin Backend

Earth Twin Backend is a FastAPI demo service for an Illinois municipal planning workflow.

This version focuses on one planner-facing story:
- choose a preconfigured area inside the Illinois Calumet Corridor demo site
- submit a proposed project brief
- simulate the submitted plan over 5 years
- compare it against an auto-mitigated alternative
- return a planner scorecard with risks, verdict, and required mitigations

It is intentionally lightweight:
- Python, FastAPI, and Pydantic
- JSON seed data plus in-memory state
- deterministic simulation rules
- no auth, database, background jobs, or GIS lookup

Important: this is a decision-support demo backend. It is not a scientific climate model and it does not do free-form parcel geocoding.

## Product Focus

Primary audience:
- urban planners
- municipalities
- local governments

Supporting audiences:
- students
- educators
- demo stakeholders who want to inspect the underlying simulation APIs

## Current Demo Story

The backend is centered on one fixed site:
- `illinois_calumet_corridor_demo`

The planner chooses one of three proposal areas:
- `calumet_industrial_strip`
- `arterial_infill_corridor`
- `river_buffer_redevelopment`

The planner then submits:
- `infrastructure_type`
- infrastructure-specific detail fields such as runway size, bridge span, road lanes, building floor area, site area, or solar field area
- `mitigation_commitment`
- optional `planner_notes`

The backend exposes build sections for:
- `road`
- `bridge`
- `buildings`
- `airport`
- `general_area`
- `solar_panel`

Each section can also advertise a map tool:
- line-based sections
  - user clicks a start point and an end point
- polygon-based sections
  - user clicks the site boundary corners

The backend maps that brief into deterministic simulation actions, runs the submitted plan and a stronger mitigated plan, then returns a scorecard for both.

## Project Layout

```text
earth-twin-backend/
  app/
    main.py
    api/v1/endpoints/
      health.py
      world.py
      zones.py
      simulation.py
      scenarios.py
      ai.py
      planning.py
    data/
      seed_world.json
      scenario_templates.json
      planning_site.json
    services/
      planning_service.py
      simulation_engine.py
      impact_service.py
      ai_service.py
      world_service.py
      zone_service.py
  tests/
  requirements.txt
  README.md
```

## Run Locally

```bash
cd earth-twin-backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Base URL:
- `http://127.0.0.1:8000`

Interactive docs:
- `http://127.0.0.1:8000/docs`

## Deployment

This backend is ready for GitHub-based deployment on platforms like Render and Koyeb.

Included deploy files:
- `render.yaml`
- `Procfile`
- `runtime.txt`

Important runtime settings:
- `PORT`
  - Set by most hosts automatically
- `CORS_ORIGINS`
  - Default is `*` for demo friendliness
  - For a tighter setup, set a comma-separated list such as:
  - `https://your-frontend.vercel.app,http://localhost:3000`

Health check path:
- `/api/v1/health`

### Fastest Free Path: Render

Render currently documents free web services for testing and hobby use:
- https://render.com/docs/free
- https://render.com/docs/deploy-fastapi

Steps:
1. Open Render and create a new Web Service from your GitHub repo.
2. Select this repository and branch `main`.
3. Render can use the included `render.yaml`, or you can enter:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
4. Set `CORS_ORIGINS` to your frontend URLs.
5. Deploy and share the generated `onrender.com` URL with the frontend team.

### Free Alternative: Koyeb

Koyeb currently documents FastAPI deployment and a free starter tier:
- https://www.koyeb.com/docs/deploy/fastapi
- https://www.koyeb.com/pricing/

Use:
- Run command: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Port: `8000`
- Health path: `/api/v1/health`

## Main Planner Endpoints

### Get Site Metadata

`GET /api/v1/planning/site`

Returns the Illinois demo site and the three selectable proposal areas.

Example:

```bash
curl http://127.0.0.1:8000/api/v1/planning/site
```

### Get Build Section Metadata

`GET /api/v1/planning/build-options`

Returns the build sections, the custom fields each section needs, and the map tool each section should use. This is the best endpoint for driving the frontend form builder.

Example:

```bash
curl http://127.0.0.1:8000/api/v1/planning/build-options
```

### Resolve Geometry From Map Clicks

`POST /api/v1/planning/geometry/resolve`

Use this when the user clicks points on the map and you want the backend to derive values like road length, runway length, or polygon area before running the final simulation.

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/planning/geometry/resolve ^
  -H "Content-Type: application/json" ^
  -d "{\"site_id\":\"illinois_calumet_corridor_demo\",\"area_id\":\"arterial_infill_corridor\",\"infrastructure_type\":\"road\",\"geometry_points\":[{\"latitude\":41.6401,\"longitude\":-87.5601},{\"latitude\":41.6501,\"longitude\":-87.5401}],\"infrastructure_details\":{\"lane_count\":4,\"daily_vehicle_trips\":1800,\"construction_years\":3}}"
```

### Assess a Proposal

`POST /api/v1/planning/proposals/assess`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/planning/proposals/assess ^
  -H "Content-Type: application/json" ^
  -d "{\"site_id\":\"illinois_calumet_corridor_demo\",\"area_id\":\"calumet_industrial_strip\",\"infrastructure_type\":\"airport\",\"geometry_points\":[{\"latitude\":41.6400,\"longitude\":-87.5700},{\"latitude\":41.6540,\"longitude\":-87.5450}],\"infrastructure_details\":{\"runway_width_m\":45,\"terminal_area_sq_m\":18000,\"apron_area_sq_m\":42000,\"daily_vehicle_trips\":3200,\"construction_years\":5},\"mitigation_commitment\":\"medium\",\"planner_notes\":\"Regional cargo airport expansion.\"}"
```

Response shape:

```json
{
  "site_id": "illinois_calumet_corridor_demo",
  "area_id": "calumet_industrial_strip",
  "project_type": "industrial_facility",
  "infrastructure_type": "airport",
  "geometry_summary": {
    "selection_mode": "line",
    "point_count": 2,
    "start_point": {
      "latitude": 41.64,
      "longitude": -87.57
    },
    "end_point": {
      "latitude": 41.654,
      "longitude": -87.545
    },
    "center_point": {
      "latitude": 41.647,
      "longitude": -87.5575
    },
    "length_m": 2556.42,
    "area_sq_m": null
  },
  "infrastructure_details": {
    "runway_length_m": 2556.42,
    "runway_width_m": 45,
    "terminal_area_sq_m": 18000,
    "apron_area_sq_m": 42000,
    "daily_vehicle_trips": 3200,
    "construction_years": 5
  },
  "footprint_acres": 39.29,
  "estimated_daily_vehicle_trips": 3200,
  "buildout_years": 5,
  "mitigation_commitment": "medium",
  "submitted_plan": {
    "plan_score": 41.23,
    "verdict": "conditional",
    "overall_outlook": "mixed",
    "highest_risk_zone": {
      "zone_id": "zone_calumet_industrial_strip",
      "name": "Calumet Industrial Strip",
      "risk_level": "high",
      "sustainability_score": 32.5
    },
    "top_risks": [
      "High pollution (63.0) is adding direct environmental stress."
    ],
    "required_mitigations": [
      "Require emissions controls and pollution monitoring before approval."
    ],
    "summary_text": "Projected to 2031. Highest risk is Calumet Industrial Strip."
  },
  "mitigated_plan": {
    "plan_score": 48.76,
    "verdict": "recommended",
    "overall_outlook": "positive",
    "highest_risk_zone": {
      "zone_id": "zone_calumet_industrial_strip",
      "name": "Calumet Industrial Strip",
      "risk_level": "medium",
      "sustainability_score": 44.1
    },
    "top_risks": [
      "Low ecosystem health (52.0) reduces the zone's ability to absorb shocks."
    ],
    "required_mitigations": [
      "Maintain the proposed mitigation bundle and monitor the highest-risk parcel during delivery."
    ],
    "summary_text": "Projected to 2031. Highest risk is Calumet Industrial Strip."
  },
  "recommended_option": "mitigated_plan",
  "comparison_summary": "Mitigated Plan is the preferred scenario because it delivers the strongest sustainability outcome with lower long-term environmental risk.",
  "simulation_inputs": {
    "projection_years": 5,
    "baseline_zone_id": "zone_calumet_industrial_strip",
    "footprint_bucket": "large",
    "traffic_bucket": "high",
    "resolved_project_type": "industrial_facility",
    "infrastructure_type": "airport",
    "geometry_summary": {
      "selection_mode": "line",
      "point_count": 2,
      "start_point": {
        "latitude": 41.64,
        "longitude": -87.57
      },
      "end_point": {
        "latitude": 41.654,
        "longitude": -87.545
      },
      "center_point": {
        "latitude": 41.647,
        "longitude": -87.5575
      },
      "length_m": 2556.42,
      "area_sq_m": null
    },
    "infrastructure_details": {
      "runway_length_m": 2556.42,
      "runway_width_m": 45,
      "terminal_area_sq_m": 18000,
      "apron_area_sq_m": 42000,
      "daily_vehicle_trips": 3200,
      "construction_years": 5
    },
    "submitted_actions": [],
    "mitigated_actions": []
  }
}
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

### Scenario Templates
- `GET /api/v1/scenarios/templates`
- `GET /api/v1/scenarios/templates/{template_id}`
- `POST /api/v1/scenarios/templates/{template_id}/run`

### AI Explain
- `POST /api/v1/ai/explain`

## Existing Modes

Earth Twin still supports:
- `planning`
- `learning`

The new planner proposal flow always uses `planning` mode internally.

## Supported Simulation Actions

Planning-oriented labels:
- `reduce_green_space`
- `expand_roadway`
- `industrial_expansion`
- `add_urban_park`
- `improve_public_transit`
- `restoration_corridor`

Learning-oriented labels:
- `cut_trees`
- `increase_traffic`
- `increase_pollution`
- `restore_ecosystem`

Legacy labels still supported:
- `deforestation`
- `traffic_increase`
- `pollution_spike`
- `restoration`

## Notes for Demo Usage

- The planner flow is the recommended starting point in `/docs`.
- The world remains in memory only; restart the app or call `/api/v1/world/reset` to restore seed values.
- The raw simulation endpoints are still available for debugging and demos, but they expose lower-level actions than the planner scorecard flow.
- For browser frontend access, set `CORS_ORIGINS` to the frontend domains before sharing the deployment URL.
