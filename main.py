from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Optional, List

app = FastAPI(title="calculatePension API")

@app.post("/validateContributionHistory")
def validateContributionHistory(data: dict):
    for item in data.get("contributions", []):
        status = item.get("participation_status")

        if status == "contributed":
            if not item.get("contribution_type"):
                return {"validation": False, "detail": "Missing contribution_type"}
            if not item.get("basis_input_type"):
                return {"validation": False, "detail": "Missing basis_input_type"}

        if status == "credited_duration_only":
            if item.get("duration_only_reason") != "pre1995_no_salary_or_living_allowance":
                return {"validation": False, "detail": "Missing duration_only_reason"}

    return {
        "validation": True,
        "detail": "Contribution history valid"
    }


@app.post("/calculatePension")
def calculatePension(data: dict):
    # Thay thế phần này bằng engine tính toán thật.
    # API phải trả đúng các trường mà GPT cần đọc.
    return {
        "total_months": 0,
        "average_salary": 0,
        "replacement_rate": 0,
        "early_retirement_reduction": 0,
        "estimated_pension": 0,
        "warnings": [
            "Đây là bộ khung triển khai. Cần nối engine tính lương hưu thực tế."
        ]
    }
