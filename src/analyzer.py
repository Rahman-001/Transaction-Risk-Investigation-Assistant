from google import genai
import os
import json

def get_client():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        for fname in [".env", ".env.example"]:
            if os.path.exists(fname):
                try:
                    with open(fname, encoding="utf-8") as f:
                        for line in f:
                            if line.strip().startswith("GEMINI_API_KEY="):
                                val = line.strip().split("=", 1)[1].strip('"').strip("'")
                                if val and val != "your_gemini_api_key_here":
                                    api_key = val
                                    os.environ["GEMINI_API_KEY"] = val
                                    break
                except Exception:
                    pass
            if api_key:
                break

    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable not set")
    return genai.Client(api_key=api_key)

def generate_report(customer_id, profile, findings, recent_transactions_str):
    has_findings = len(findings) > 0
    findings_json = json.dumps(findings, indent=2, default=str)

    prompt = f"""You are a senior bank fraud investigation analyst. Your job is to flag and explain — never to declare fraud has occurred. Every finding must be traceable to a specific transaction and a specific rule. Human investigators make the final call.

CUSTOMER PROFILE:
{json.dumps(profile, indent=2)}

DETERMINISTIC RULE ENGINE FINDINGS ({len(findings)} rules triggered):
{findings_json}

RECENT TRANSACTIONS (last 30 days):
{recent_transactions_str}

Generate a complete investigation report as a single valid JSON object. No markdown, no text outside the JSON.

CRITICAL INSTRUCTIONS:
- If findings is empty → verdict MUST be "NO CONCERNS IDENTIFIED". flagged_transactions MUST be [].
- If findings exist → verdict MUST be "ATTENTION REQUIRED".
- Never invent transactions or findings not in the data above.
- Never say "fraud occurred" or "account is compromised" — only "warrants investigation", "inconsistent with baseline", "unusual pattern".
- Each flagged transaction must cite the exact rule_id and rule_name from the findings.
- Be specific — use actual amounts, dates, payee names from the data.

Return exactly this JSON structure:
{{
  "verdict": "ATTENTION REQUIRED" | "NO CONCERNS IDENTIFIED",
  "risk_level": "HIGH" | "MEDIUM" | "LOW" | "NONE",
  "verdict_reason": "1-2 sentence plain-language summary a bank manager can read",
  "normal_behaviour_summary": "2-3 sentences describing this customer's established baseline pattern — amounts, channels, timing, regular payees",
  "flagged_transactions": [
    {{
      "rule_id": "R01",
      "rule_name": "exact rule name from findings",
      "severity": "HIGH" | "MEDIUM",
      "date": "YYYY-MM-DD",
      "time": "HH:MM",
      "payee": "payee name",
      "amount": "₹XX,XXX",
      "channel": "channel name",
      "transaction_id": "TXN...",
      "what_happened": "1 sentence plain English — what this transaction is",
      "why_suspicious": "1-2 sentences — specifically how this deviates from this customer's baseline",
      "rule_citation": "The exact rule text that was triggered",
      "investigator_action": "Specific action the investigator should take for this transaction"
    }}
  ],
  "pattern_analysis": "2-3 sentences connecting the flagged transactions if there are multiple — do they form a pattern? Are they related?",
  "investigator_focus": "2-3 sentences — what the investigator should prioritise first and why. Be specific.",
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "unknowns": "What cannot be determined from transaction data alone — what the investigator must verify externally",
  "escalation_required": true | false
}}"""

    try:
        import concurrent.futures

        def _do_call():
            client = get_client()
            for m in ["gemini-3.5-flash-lite", "gemini-3.1-flash-lite", "gemini-3.6-flash"]:
                try:
                    res = client.models.generate_content(model=m, contents=prompt)
                    if res and res.text:
                        return res.text.strip().replace("```json", "").replace("```", "").strip()
                except Exception:
                    continue
            raise RuntimeError("No Gemini model responded")

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_do_call)
            return future.result(timeout=15.0)
    except Exception as e:
        verdict = "ATTENTION REQUIRED" if has_findings else "NO CONCERNS IDENTIFIED"
        risk_level = "HIGH" if has_findings else "NONE"
        reason = (
            f"Rule engine identified {len(findings)} anomaly trigger(s). AI report narrative generation offline: {str(e)}"
            if has_findings else
            "No risk rule triggers found across customer transaction history."
        )
        flagged_txns = []
        if has_findings:
            for f in findings:
                tx = f.get("transaction", {})
                flagged_txns.append({
                    "rule_id": f.get("rule_id", ""),
                    "rule_name": f.get("rule_name", ""),
                    "severity": f.get("severity", "HIGH"),
                    "date": tx.get("date", ""),
                    "time": tx.get("time", ""),
                    "payee": tx.get("payee", ""),
                    "amount": f"₹{abs(tx.get('amount', 0)):,.0f}",
                    "channel": tx.get("channel", ""),
                    "transaction_id": tx.get("transaction_id", ""),
                    "what_happened": f"Transaction of ₹{abs(tx.get('amount', 0)):,.0f} to {tx.get('payee', '')} via {tx.get('channel', '')}.",
                    "why_suspicious": f.get("detail", "Deviates from customer baseline pattern."),
                    "rule_citation": f"{f.get('rule_id')}: {f.get('rule_name')} — {f.get('rule_description', '')}",
                    "investigator_action": "Verify transaction authorization with customer."
                })

        fallback = {
            "verdict": verdict,
            "risk_level": risk_level,
            "verdict_reason": reason,
            "normal_behaviour_summary": f"Historical profile shows average debit ₹{profile.get('baseline_avg_debit', 0):,.0f} across {profile.get('total_transactions', 0)} total transactions.",
            "flagged_transactions": flagged_txns,
            "pattern_analysis": f"Detected {len(findings)} deterministic risk rule trigger(s) requiring analyst review.",
            "investigator_focus": f"Review triggered findings for customer {customer_id} ({profile.get('customer_name', '')}).",
            "recommended_actions": [
                "Verify customer identity and recent device usage",
                "Contact customer to confirm transaction legitimacy",
                "Check for recent phone number or address change requests"
            ],
            "unknowns": "External verification required (out-of-band contact with account holder).",
            "escalation_required": has_findings
        }
        return json.dumps(fallback)
