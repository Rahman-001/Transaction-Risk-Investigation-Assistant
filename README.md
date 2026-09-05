TRACK_ID=PS06

# Transaction Risk Investigation Assistant

AI-powered fraud desk tool for bank analysts. Reviews customer transaction histories against 5 deterministic risk rules, then uses Gemini 1.5 Flash to generate a structured investigation report — complete with pattern analysis, investigator guidance, and recommended actions. Never decides fraud; always escalates to a human.

## How to run
1. pip install -r requirements.txt
2. export GEMINI_API_KEY=your_key_here
3. python app.py
4. Open http://localhost:8000

## Architecture — what the judges care about
- rules_engine.py → pure deterministic Python. Zero LLM. Threshold checks, pattern detection.
- analyzer.py → Gemini 1.5 Flash generates narrative report grounded in rule output. Never guesses.
- Clean separation: rules layer feeds structured JSON findings to LLM; LLM only adds explanation and narrative.
- Graceful degradation: if Gemini fails, API returns structured error; UI shows clear message.

## Features
- 3-tab UI: Overview (verdict + flagged cards) | All Transactions (full table with flagged highlights) | Baseline Analysis (Chart.js cash flow + known payee map)
- 5 risk rules: R01 Large Transfer, R02 New Payee Burst, R03 Odd Hours, R04 Pattern Break, R05 Channel Anomaly
- 3 synthetic customers: normal (CUST001), edge case (CUST002), suspicious (CUST003)

## Data
- data/transactions.csv — 167 synthetic transactions across 3 customers, 6 months each
- data/risk_rules.json — 5 rule definitions with severity and recommended action
- Generated using Gemini 1.5 Flash with realistic Indian banking context (UPI/NEFT/IMPS, ₹ amounts)

## Demo video
[ADD LINK HERE]
