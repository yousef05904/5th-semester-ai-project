from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Form, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from app.database import create_db_and_tables, get_session
from app.db_models import MonitoringRun, ProjectLeadDB
from app.region_config import get_region, list_regions
from app.runner import run_monitoring_for_region


BASE_DIR = Path(__file__).resolve().parent

app = FastAPI(title="AI Media Monitoring MVP")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()


@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "regions": list_regions(),
        },
    )


@app.post("/run")
def run_monitoring(request: Request, region_key: str = Form(...)):
    try:
        get_region(region_key)
        summary = run_monitoring_for_region(region_key)
    except RuntimeError as exc:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Configuration Error",
                "message": str(exc),
            },
            status_code=400,
        )
    except ValueError as exc:
        return templates.TemplateResponse(
            "error.html",
            {
                "request": request,
                "title": "Unknown Region",
                "message": str(exc),
            },
            status_code=400,
        )

    return RedirectResponse(url=f"/results/{summary['run_id']}", status_code=303)


@app.get("/results/{run_id}")
def results(request: Request, run_id: int, session: Session = Depends(get_session)):
    run = session.get(MonitoringRun, run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    leads = session.exec(
        select(ProjectLeadDB)
        .where(ProjectLeadDB.run_id == run_id)
        .order_by(ProjectLeadDB.priority, ProjectLeadDB.project_name)
    ).all()

    return templates.TemplateResponse(
        "results.html",
        {
            "request": request,
            "run": run,
            "leads": leads,
        },
    )


@app.get("/download/{run_id}/excel")
def download_excel(run_id: int, session: Session = Depends(get_session)):
    run = session.get(MonitoringRun, run_id)
    if not run or not run.excel_path:
        raise HTTPException(status_code=404, detail="Excel export not found")

    path = Path(run.excel_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Excel export file is missing")

    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=path.name,
    )


@app.get("/download/{run_id}/json")
def download_json(run_id: int, session: Session = Depends(get_session)):
    run = session.get(MonitoringRun, run_id)
    if not run or not run.json_path:
        raise HTTPException(status_code=404, detail="JSON export not found")

    path = Path(run.json_path)
    if not path.exists():
        raise HTTPException(status_code=404, detail="JSON export file is missing")

    return FileResponse(
        path,
        media_type="application/json",
        filename=path.name,
    )
