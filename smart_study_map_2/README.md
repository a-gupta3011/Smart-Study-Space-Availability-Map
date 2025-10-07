[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-API-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Streamlit](https://img.shields.io/badge/Streamlit-Apps-FF4B4B?logo=streamlit&logoColor=white)](https://streamlit.io/)

# Smart Study Map

Discover free study spaces on campus in real time. This project provides a FastAPI backend with a lightweight SQLite database and multiple Streamlit frontends (Admin, User, Ops) for browsing, simulating, and monitoring room availability.

- Backend: FastAPI + SQLAlchemy + SQLite
- Frontend: Streamlit (Admin, User, Ops dashboards) + Plotly + Folium
- Data: CSV-driven seed with a live occupancy simulator for demos


## Table of Contents
- Features
- Screenshots
- Tech Stack
- Quickstart
- Running Services Individually
- API Reference
- Data and Database
- Configuration
- Project Structure
- Development Notes
- Contributing
- License


## Features
- Real-time occupancy simulation updating room statuses.
- Filter free rooms by block and capacity.
- Room details with timetable and recent occupancy history.
- Summary analytics (per block, types, coverage, insert rates) and heatmap aggregation.
- Multiple Streamlit apps for different roles: Admin, User, and Ops.


## Screenshots
<!-- Replace these image paths with your actual screenshots/GIFs once captured -->

- Admin Dashboard
  
  

- User App
  
  ![User App](docs/images/user-app.png)

- Ops Dashboard
  
  ![Ops Dashboard](docs/images/ops-dashboard.png)

- Campus Map (GIF)
  
  ![Campus Map](docs/images/campus-map.gif)

## Tech Stack
- Python 3.10+
- FastAPI, Uvicorn
- SQLAlchemy, SQLite
- Streamlit, Plotly, Folium (via streamlit-folium)


## Quickstart
1) Create and activate a virtual environment
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2) Install dependencies
   ```bash
   pip install -r requirements.txt
   ```

3) Launch everything (data generation, DB populate, backend, and Streamlit apps)
   ```bash
   python3 run_all.py
   ```
   Services will be available at:
   - Backend API: http://localhost:8000
   - Streamlit Admin: http://localhost:8501
   - Streamlit User: http://localhost:8502
   - Ops Dashboard: http://localhost:8503


## Running Services Individually
- Backend (FastAPI + Uvicorn)
  ```bash
  uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
  ```

- Streamlit Admin
  ```bash
  streamlit run streamlit_admin/admin.py --server.port 8501
  ```

- Streamlit User
  ```bash
  streamlit run streamlit_user/user.py --server.port 8502
  ```

- Streamlit Ops
  ```bash
  streamlit run streamlit_ops/ops_dashboard.py --server.port 8503
  ```


## API Reference
Base URL: http://localhost:8000

- Health
  - GET /health
  - Response: `{ "status": "ok" }`

- Rooms
  - GET /rooms/all → List all rooms with current status and occupancy level.
  - GET /rooms/free?block=BLOCK&capacity=MIN_CAP → Free & empty rooms filtered by block/capacity.
  - GET /rooms/{room_id} → Room details, timetable, and recent occupancy history.

- Check-in (simulate/update occupancy)
  - POST /rooms/{room_id}/checkin
    - JSON body: `{ "occupancy_level": 50 }`

- Analytics
  - GET /analytics/heatmap → Average occupancy per block.
  - GET /analytics/summary → Summary metrics (blocks, types, coverage, insert rates, etc.).

Example requests:
```bash
# All rooms
curl -s http://localhost:8000/rooms/all | head -n 20

# Free rooms in block "UB" with capacity >= 40
curl -s "http://localhost:8000/rooms/free?block=UB&capacity=40" | head -n 20

# Room details
curl -s http://localhost:8000/rooms/UB-101

# Check in with an occupancy level of 30
curl -s -X POST http://localhost:8000/rooms/UB-101/checkin \
  -H 'Content-Type: application/json' \
  -d '{"occupancy_level":30}'
```


## Data and Database
- Database: SQLite file at `backend/database.db`.
- Seed CSVs: `backend/rooms.csv` and `backend/timetable.csv`.
- On startup, `run_all.py`:
  1) Generates sample CSVs (if missing) via `scripts/generate_sample_data.py` (uses `--seed 42`).
  2) Populates the database from CSVs.
  3) Starts backend and Streamlit apps.

Regenerate seed data manually:
```bash
python3 scripts/generate_sample_data.py --seed 42
python3 -c "import backend.init_db as i; i.populate_from_csv()"
```

Reset database (start fresh):
```bash
rm -f backend/database.db
python3 -c "import backend.init_db as i; i.populate_from_csv()"
```


## Configuration
- CORS is enabled for localhost development in `backend/main.py`.
- Campus map center can be customized in `streamlit_campus_map.py` by changing `CENTER = (lat, lon)`.
- For larger datasets, adjust the generator or CSV inputs accordingly.


## Project Structure
```
smart_study_map_2/
├─ backend/
│  ├─ main.py            # FastAPI app (endpoints, simulator)
│  ├─ database.py        # SQLAlchemy engine + session
│  ├─ models.py          # ORM models (Room, Timetable, Occupancy)
│  ├─ schemas.py         # Pydantic models
│  ├─ crud.py            # Data access/helpers
│  ├─ init_db.py         # Create/populate from CSV
│  ├─ database.db        # SQLite DB (generated)
│  ├─ rooms.csv          # Seed CSV (generated)
│  └─ timetable.csv      # Seed CSV (generated)
├─ scripts/
│  └─ generate_sample_data.py # Generates seed CSVs
├─ streamlit_admin/
│  └─ admin.py
├─ streamlit_user/
│  └─ user.py
├─ streamlit_ops/
│  └─ ops_dashboard.py
├─ streamlit_campus_map.py
├─ data/                 # Optional data assets
├─ ops/                  # Operational notes/configs
├─ run_all.py            # Orchestrates data gen, DB populate, and services
├─ requirements.txt
└─ README.md
```


## Development Notes
- Python version: 3.10+
- Recommended to use a virtual environment (`.venv`).
- Use `--reload` with Uvicorn during development.
- This is a demo/hackathon-focused project and intentionally lightweight.

Possible improvements:
- Add tests for API endpoints.
- Containerize with Docker and docker-compose.
- Add CI and formatting/linting (e.g., ruff/black, mypy).
- Add authentication for admin endpoints.


## Contributing
Contributions are welcome! Please open an issue or submit a pull request. For larger changes, start with an issue to discuss direction.


## License
No license specified yet. Consider adding a LICENSE file (e.g., MIT) to clarify usage.
