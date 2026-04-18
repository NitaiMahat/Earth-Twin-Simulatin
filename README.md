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
- `project_type`
- `footprint_acres`
- `estimated_daily_vehicle_trips`
- `buildout_years`
- `mitigation_commitment`
- optional `planner_notes`

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

## Main Planner Endpoints

### Get Site Metadata

`GET /api/v1/planning/site`

Returns the Illinois demo site and the three selectable proposal areas.

Example:

```bash
curl http://127.0.0.1:8000/api/v1/planning/site
```

### Assess a Proposal

`POST /api/v1/planning/proposals/assess`

Example:

```bash
curl -X POST http://127.0.0.1:8000/api/v1/planning/proposals/assess ^
  -H "Content-Type: application/json" ^
  -d "{\"site_id\":\"illinois_calumet_corridor_demo\",\"area_id\":\"calumet_industrial_strip\",\"project_type\":\"industrial_facility\",\"footprint_acres\":45,\"estimated_daily_vehicle_trips\":2600,\"buildout_years\":4,\"mitigation_commitment\":\"low\",\"planner_notes\":\"Freight-oriented advanced manufacturing campus.\"}"
```

Response shape:

```json
{
  "site_id": "illinois_calumet_corridor_demo",
  "area_id": "calumet_industrial_strip",
  "project_type": "industrial_facility",
  "footprint_acres": 45.0,
  "estimated_daily_vehicle_trips": 2600,
  "buildout_years": 4,
  "mitigation_commitment": "low",
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
