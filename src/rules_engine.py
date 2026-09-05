import pandas as pd
import json
from datetime import timedelta

def load_rules(path="data/risk_rules.json"):
    with open(path) as f:
        data = json.load(f)
    return {r["id"]: r for r in data["rules"]}

def safe_val(v):
    if hasattr(v, "isoformat"):
        return str(v)
    if hasattr(v, "item"):
        return v.item()
    if pd.isna(v) if not isinstance(v, (list, dict)) else False:
        return None
    return v

def row_to_dict(row):
    return {k: safe_val(v) for k, v in row.to_dict().items()}

def check_all_rules(df, customer_id, profile):
    rules = load_rules()
    cdf = df[df["customer_id"] == customer_id].copy().sort_values("date")
    
    max_date = cdf["date"].max()
    cutoff = max_date - pd.Timedelta(days=30)
    baseline = cdf[cdf["date"] < cutoff]
    recent = cdf[cdf["date"] >= cutoff]
    
    baseline_payees = set(baseline["payee"].unique())
    baseline_channels = set(baseline["channel"].unique())
    
    avg = profile["baseline_avg_debit"]
    p90 = profile["baseline_p90_debit"]
    
    findings = []
    seen_keys = set()

    for _, row in recent.iterrows():
        amt = abs(row["amount"])
        is_debit = row["amount"] < 0

        # R01 — Large transfer
        if is_debit and avg > 0 and amt > avg * 3:
            key = ("R01", str(row["date"].date()), row["payee"])
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append({
                    "rule_id": "R01",
                    "rule_name": rules["R01"]["name"],
                    "severity": rules["R01"]["severity"],
                    "rule_description": rules["R01"]["description"],
                    "transaction": row_to_dict(row),
                    "detail": f"₹{amt:,.0f} is {amt/avg:.1f}x the baseline average of ₹{avg:,.0f}",
                    "threshold_used": f"3x avg (₹{avg*3:,.0f})",
                    "actual_value": f"₹{amt:,.0f}"
                })

        # R03 — Odd hours
        if pd.notna(row.get("hour")) and 1 <= int(row["hour"]) <= 5:
            key = ("R03", str(row["date"].date()), row["time"])
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append({
                    "rule_id": "R03",
                    "rule_name": rules["R03"]["name"],
                    "severity": rules["R03"]["severity"],
                    "rule_description": rules["R03"]["description"],
                    "transaction": row_to_dict(row),
                    "detail": f"Transaction at {row['time']} — within 01:00–05:00 window",
                    "threshold_used": "01:00–05:00 AM",
                    "actual_value": row["time"]
                })

        # R04 — Pattern break amount
        if is_debit and p90 > 0 and amt > p90 * 2:
            key = ("R04", str(row["date"].date()), row["payee"])
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append({
                    "rule_id": "R04",
                    "rule_name": rules["R04"]["name"],
                    "severity": rules["R04"]["severity"],
                    "rule_description": rules["R04"]["description"],
                    "transaction": row_to_dict(row),
                    "detail": f"₹{amt:,.0f} is {amt/p90:.1f}x the 90th percentile of ₹{p90:,.0f}",
                    "threshold_used": f"2x p90 (₹{p90*2:,.0f})",
                    "actual_value": f"₹{amt:,.0f}"
                })

        # R05 — Channel anomaly
        if row["channel"] not in baseline_channels:
            key = ("R05", str(row["date"].date()), row["channel"])
            if key not in seen_keys:
                seen_keys.add(key)
                findings.append({
                    "rule_id": "R05",
                    "rule_name": rules["R05"]["name"],
                    "severity": rules["R05"]["severity"],
                    "rule_description": rules["R05"]["description"],
                    "transaction": row_to_dict(row),
                    "detail": f"Channel '{row['channel']}' not seen in prior 5 months. Known: {', '.join(baseline_channels)}",
                    "threshold_used": "Not in baseline channels",
                    "actual_value": row["channel"]
                })

    # R02 — New payee burst (group-level check)
    new_payee_recent = recent[
        (~recent["payee"].isin(baseline_payees)) & (recent["amount"] < 0)
    ]
    for payee, grp in new_payee_recent.groupby("payee"):
        if len(grp) >= 2:
            span = (grp["date"].max() - grp["date"].min()).days
            if span <= 10:
                total_amt = grp["amount"].abs().sum()
                key = ("R02", payee)
                if key not in seen_keys:
                    seen_keys.add(key)
                    findings.append({
                        "rule_id": "R02",
                        "rule_name": rules["R02"]["name"],
                        "severity": rules["R02"]["severity"],
                        "rule_description": rules["R02"]["description"],
                        "transaction": row_to_dict(grp.iloc[0]),
                        "all_transactions": [row_to_dict(r) for _, r in grp.iterrows()],
                        "detail": f"{len(grp)} payments totaling ₹{total_amt:,.0f} to new payee '{payee}' within {max(1,span)} days",
                        "threshold_used": "≥2 payments to new payee within 10 days",
                        "actual_value": f"{len(grp)} payments, ₹{total_amt:,.0f} total"
                    })

    return findings
