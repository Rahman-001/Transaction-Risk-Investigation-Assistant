TRACK_ID=PS06

# Transaction Risk Investigation Assistant

AI-powered fraud desk tool for bank analysts. Reviews customer transaction histories against 5 deterministic risk rules, then uses Gemini Flash to generate a structured investigation report — complete with pattern analysis, investigator guidance, and recommended actions. Never decides fraud; always escalates to a human.

## Demo Video
Watch the project walkthrough demo video: [ADD LINK HERE]

## How to Run

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set API Key
**Linux / macOS:**
```bash
export GEMINI_API_KEY=your_key_here
```

**Windows PowerShell:**
```powershell
$env:GEMINI_API_KEY = "your_key_here"
```

**Windows Command Prompt (cmd):**
```cmd
set GEMINI_API_KEY=your_key_here
```

### 3. Launch Application
```bash
python app.py
```
Open [http://localhost:8000](http://localhost:8000) in your browser.

---

## Key Features
- **Deterministic Risk Engine**: 5 zero-LLM risk rules evaluate every transaction for abnormal transfers, unusual hours, payee bursts, channel anomalies, and baseline deviations.
- **Custom CSV Dataset Upload**: Upload custom bank transaction CSV files directly in the UI with automatic column validation, customer detection, and downloadable template support (`/api/sample-template`).
- **Structured AI Audit Reports**: Grounded Gemini Flash narrative reports detailing what happened, why suspicious, and recommended investigator actions.
- **3-Tab Analyst Workbench**: 
  - **Overview**: Verdict banner, count-up statistics, and flagged transaction case cards.
  - **All Transactions**: Filterable table with flagged indicator highlights.
  - **Customer Baseline**: Interactive Chart.js monthly cash flow chart and known payee profile map.

---

## Architecture — What the Judges Care About
- `src/rules_engine.py` → Pure deterministic Python. Zero LLM. Threshold checks, statistical percentile bounds, and pattern detection.
- `src/analyzer.py` → Gemini Flash generates narrative reports strictly grounded in deterministic rule outputs with strict 2.5-second timeout guards.
- **Clean Separation**: Rules layer feeds structured JSON findings to LLM; LLM only adds explanation and narrative.
- **Graceful Degradation**: If external API calls fail or time out, the system automatically falls back to an instant local audit generator so the UI never hangs.

---

## Data Structure
- `data/transactions.csv` — Synthetic transactions across 3 customers (CUST001, CUST002, CUST003), spanning 6 months.
- `data/risk_rules.json` — 5 rule definitions with severity parameters and recommended action workflows.
