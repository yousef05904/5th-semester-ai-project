from __future__ import annotations

import json
from pathlib import Path
from typing import Sequence

import pandas as pd

from models import PROJECT_LEAD_FIELDS


def _to_dict(item):
    if hasattr(item, "model_dump"):
        return item.model_dump()
    return item.dict()


def export_leads(leads: Sequence, output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)

    json_path = output_dir / "leads.json"
    csv_path = output_dir / "leads.csv"

    data = [_to_dict(lead) for lead in leads]

    with open(json_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    frame = pd.DataFrame(data, columns=PROJECT_LEAD_FIELDS)
    frame.to_csv(csv_path, index=False, encoding="utf-8")

    return json_path, csv_path


def export_rejections(rejections: Sequence[dict], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)

    rejected_path = output_dir / "rejected.json"
    with open(rejected_path, "w", encoding="utf-8") as handle:
        json.dump(list(rejections), handle, ensure_ascii=False, indent=2)

    return rejected_path


def export_leads_json(leads: Sequence, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [_to_dict(lead) for lead in leads]

    with open(output_path, "w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)

    return output_path


def export_leads_excel(leads: Sequence, output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data = [_to_dict(lead) for lead in leads]
    frame = pd.DataFrame(data, columns=PROJECT_LEAD_FIELDS)
    frame = frame.rename(
        columns={
            "project_name": "Project Name",
            "region": "Region",
            "city": "City",
            "project_type": "Project Type",
            "stage": "Stage",
            "customer": "Customer",
            "short_description": "Short Description",
            "materials_demand": "Materials Demand",
            "priority": "Priority",
            "publication_date": "Publication Date",
            "source_url": "Source URL",
            "confidence": "Confidence",
            "reason": "Reason",
        }
    )
    frame = frame[
        [
            "Project Name",
            "Region",
            "City",
            "Project Type",
            "Stage",
            "Customer",
            "Short Description",
            "Materials Demand",
            "Priority",
            "Publication Date",
            "Source URL",
            "Confidence",
            "Reason",
        ]
    ]
    frame.to_excel(output_path, index=False, engine="openpyxl")
    return output_path
