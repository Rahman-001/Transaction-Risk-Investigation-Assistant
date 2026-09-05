import pandas as pd
import numpy as np

def load_transactions(path="data/transactions.csv"):
    df = pd.read_csv(path)
    df["date"] = pd.to_datetime(df["date"])
    df["time_parsed"] = pd.to_datetime(df["time"], format="%H:%M", errors="coerce")
    df["hour"] = df["time_parsed"].dt.hour
    df["amount"] = df["amount"].astype(float)
    df["balance_after"] = df["balance_after"].astype(float)
    df = df.sort_values(["customer_id", "date", "time"]).reset_index(drop=True)
    return df

def get_all_customers(df):
    result = []
    for cid in sorted(df["customer_id"].unique()):
        name = df[df["customer_id"] == cid]["customer_name"].iloc[0] if "customer_name" in df.columns else f"Customer {cid}"
        result.append({"id": cid, "name": name, "display": f"{cid} — {name}"})
    return result

def get_customer_profile(df, customer_id):
    cdf = df[df["customer_id"] == customer_id].copy()
    debits = cdf[cdf["amount"] < 0]["amount"].abs()
    credits = cdf[cdf["amount"] > 0]["amount"]
    
    # Establish baseline = all except last 30 days
    cutoff = cdf["date"].max() - pd.Timedelta(days=30)
    baseline = cdf[cdf["date"] < cutoff]
    baseline_debits = baseline[baseline["amount"] < 0]["amount"].abs()
    baseline_payees = baseline["payee"].unique().tolist()
    baseline_channels = baseline["channel"].unique().tolist()
    
    cust_name = cdf["customer_name"].iloc[0] if "customer_name" in cdf.columns else f"Customer {customer_id}"

    return {
        "customer_id": customer_id,
        "customer_name": cust_name,
        "total_transactions": len(cdf),
        "date_range_start": str(cdf["date"].min().date()),
        "date_range_end": str(cdf["date"].max().date()),
        "avg_debit": round(float(debits.mean()), 2) if len(debits) else 0,
        "median_debit": round(float(debits.median()), 2) if len(debits) else 0,
        "p90_debit": round(float(debits.quantile(0.90)), 2) if len(debits) else 0,
        "max_debit": round(float(debits.max()), 2) if len(debits) else 0,
        "avg_credit": round(float(credits.mean()), 2) if len(credits) else 0,
        "total_debits": len(debits),
        "total_credits": len(credits),
        "baseline_avg_debit": round(float(baseline_debits.mean()), 2) if len(baseline_debits) else 0,
        "baseline_p90_debit": round(float(baseline_debits.quantile(0.90)), 2) if len(baseline_debits) else 0,
        "known_payees": baseline_payees,
        "known_channels": baseline_channels,
        "usual_hour_range": "daytime" if (cdf["hour"].dropna().between(8, 22).mean() > 0.95) else "mixed"
    }

def get_transaction_timeline(df, customer_id):
    cdf = df[df["customer_id"] == customer_id].copy()
    cdf["month"] = cdf["date"].dt.to_period("M").astype(str)
    monthly = cdf.groupby("month").agg(
        total_out=("amount", lambda x: abs(x[x < 0].sum())),
        total_in=("amount", lambda x: x[x > 0].sum()),
        count=("amount", "count")
    ).reset_index()
    return monthly.to_dict(orient="records")
