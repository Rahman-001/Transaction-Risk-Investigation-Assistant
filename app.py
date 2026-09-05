import io
import os
import json
import uvicorn
import pandas as pd
from typing import Optional
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from pydantic import BaseModel

from src.data_loader import (
    load_transactions, get_all_customers,
    get_customer_profile, get_transaction_timeline
)
from src.rules_engine import check_all_rules
from src.analyzer import generate_report

app = FastAPI(title="Transaction Risk Investigation Assistant")

# Load at startup
df = load_transactions()
customers = get_all_customers(df)

# Upload store — holds user-uploaded datasets in memory
upload_store = {}

def get_active_df(dataset_id: Optional[str] = None) -> pd.DataFrame:
    if dataset_id and dataset_id in upload_store:
        return upload_store[dataset_id]
    return df

def get_active_customers(active_df: pd.DataFrame):
    return get_all_customers(active_df)

app.mount("/static", StaticFiles(directory="frontend"), name="static")

@app.get("/")
def index():
    return FileResponse(
        "frontend/index.html",
        headers={
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }
    )

@app.get("/api/customers")
def list_customers(dataset_id: Optional[str] = None):
    active_df = get_active_df(dataset_id)
    return {"customers": get_active_customers(active_df)}

@app.get("/api/customers/{customer_id}/timeline")
def get_timeline(customer_id: str, dataset_id: Optional[str] = None):
    active_df = get_active_df(dataset_id)
    c_list = get_active_customers(active_df)
    if not any(c["id"] == customer_id for c in c_list):
        raise HTTPException(404, "Customer not found")
    timeline = get_transaction_timeline(active_df, customer_id)
    return {"timeline": timeline}

@app.get("/api/customers/{customer_id}/transactions")
def get_transactions(customer_id: str, dataset_id: Optional[str] = None):
    active_df = get_active_df(dataset_id)
    c_list = get_active_customers(active_df)
    if not any(c["id"] == customer_id for c in c_list):
        raise HTTPException(404, "Customer not found")
    cdf = active_df[active_df["customer_id"] == customer_id].copy()
    cdf["date"] = cdf["date"].astype(str)
    for col in ["description", "payee", "channel", "balance_after"]:
        if col not in cdf.columns:
            cdf[col] = "" if col != "balance_after" else 0
    records = cdf[["transaction_id","date","time","description","payee","amount","channel","balance_after"]].to_dict(orient="records")
    return {"transactions": records}

class InvestigateRequest(BaseModel):
    customer_id: str
    dataset_id: Optional[str] = None

@app.post("/api/investigate")
def investigate(req: InvestigateRequest):
    active_df = get_active_df(req.dataset_id)
    c_list = get_active_customers(active_df)
    if not any(c["id"] == req.customer_id for c in c_list):
        raise HTTPException(404, "Customer not found")

    profile = get_customer_profile(active_df, req.customer_id)
    findings = check_all_rules(active_df, req.customer_id, profile)

    cdf = active_df[active_df["customer_id"] == req.customer_id].sort_values("date").tail(30)
    summary_lines = []
    for _, row in cdf.iterrows():
        direction = "OUT" if row["amount"] < 0 else "IN"
        date_str = str(row['date'].date()) if hasattr(row['date'], 'date') else str(row['date'])
        payee_val = row.get('payee', 'Unknown')
        chan_val = row.get('channel', 'UNKNOWN')
        bal_val = row.get('balance_after', 0)
        summary_lines.append(
            f"{date_str} {row.get('time','')} | {payee_val} | "
            f"₹{abs(row['amount']):,.0f} {direction} | {chan_val} | Bal: ₹{bal_val:,.0f}"
        )
    recent_str = "\n".join(summary_lines)

    raw = generate_report(req.customer_id, profile, findings, recent_str)

    try:
        report = json.loads(raw)
    except json.JSONDecodeError:
        report = {
            "verdict": "PARSE ERROR",
            "risk_level": "UNKNOWN",
            "verdict_reason": "AI response could not be parsed. See raw output.",
            "flagged_transactions": [],
            "investigator_focus": "",
            "pattern_analysis": "",
            "recommended_actions": [],
            "unknowns": "",
            "normal_behaviour_summary": "",
            "escalation_required": False,
            "raw": raw
        }

    return {
        "customer_id": req.customer_id,
        "profile": profile,
        "rules_triggered": len(findings),
        "report": report
    }

@app.post("/api/upload-dataset")
async def upload_dataset(file: UploadFile = File(...)):
    try:
        contents = await file.read()
        uploaded_df = pd.read_csv(io.BytesIO(contents))
        uploaded_df["date"] = pd.to_datetime(uploaded_df["date"])
        
        required_cols = {"customer_id", "date", "time", "payee", "amount", "channel"}
        missing = required_cols - set(uploaded_df.columns)
        if missing:
            return {
                "success": False,
                "error": f"Missing columns: {', '.join(missing)}",
                "required_columns": list(required_cols)
            }

        if "transaction_id" not in uploaded_df.columns:
            uploaded_df["transaction_id"] = [f"TXN_{i+1:04d}" for i in range(len(uploaded_df))]
        if "description" not in uploaded_df.columns:
            uploaded_df["description"] = "Transaction"
        if "balance_after" not in uploaded_df.columns:
            uploaded_df["balance_after"] = 50000.0

        uploaded_df["time_parsed"] = pd.to_datetime(uploaded_df["time"].astype(str), format="%H:%M", errors="coerce")
        uploaded_df["hour"] = uploaded_df["time_parsed"].dt.hour.fillna(12).astype(int)
        uploaded_df["amount"] = uploaded_df["amount"].astype(float)
        uploaded_df = uploaded_df.sort_values(["customer_id", "date", "time"]).reset_index(drop=True)

        upload_store[file.filename] = uploaded_df
        customers_in_upload = sorted(uploaded_df["customer_id"].unique().tolist())

        return {
            "success": True,
            "filename": file.filename,
            "customers_found": customers_in_upload,
            "total_rows": len(uploaded_df),
            "dataset_id": file.filename
        }
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.get("/api/sample-template")
def download_template():
    template = """customer_id,date,time,description,payee,amount,channel,balance_after
CUST999,2024-01-01,10:30,Salary credit,Employer Ltd,45000,NEFT,85000
CUST999,2024-01-05,14:22,Grocery shopping,Zepto,-2300,UPI,82700
CUST999,2024-01-10,09:15,Electricity bill,BSNL,-1200,UPI,81500"""

    return StreamingResponse(
        io.StringIO(template),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=frauddesk_template.csv"}
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    return JSONResponse(
        status_code=500,
        content={"error": str(exc), "detail": "Internal server error"}
    )

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=8000, reload=True)
