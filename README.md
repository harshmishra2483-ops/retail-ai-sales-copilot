
# Retail AI Sales Copilot — Final Prototype Base

## What this is
A local Streamlit web application for retail field-sales decision support.

Python starts the application; Streamlit serves the interface at `http://localhost:8501`.

## Included
- Existing AI feedback classification logic, strengthened and cleaned
- Same-category recurrence only
- Product-wise stock tracking
- Retailer order request -> DS queue
- DS visit status + optional photo proof + optional coordinates
- Area / outlet / DS / Area Executive fields
- Excel importer
- Issue history and audit memory
- Human-in-the-loop approval
- Area Executive dashboard
- Analytics charts
- Configurable market intelligence API with safe demo fallback
- Optional audio transcription entry point
- Persistent SQLite history
- Optional Anthropic live mode; local fallback works without API key

## Important
This prototype does NOT connect automatically to ITC systems and does not send data externally unless you explicitly configure an API.

The exact product catalogue and outlet/area data should come from your authorized Excel file. The importer is intentionally data-driven instead of inventing a complete company catalogue.

## Run
1. Open PowerShell in this folder.
2. `python -m pip install -r requirements.txt`
3. `python generate_data.py` is optional; for the Excel demo, import your sheet from the app.
4. `python -m streamlit run app.py`
5. Open `http://localhost:8501`

## Excel
Upload the Excel from `Data Import`. Common columns supported:
outlet_id, outlet_name/outlet/shop_name, city, area/zone/location/territory,
outlet_type/shop_type, ds/ds_name/salesperson/field_executive,
area_executive/ae/supervisor, monthly_potential/potential/monthly_sales,
products/product/sku/brand.

## Neural network / GPU note
The prototype is intentionally CPU-safe for a student laptop. A future GPU model can be plugged into `ai_engine.py`; no fake claim of local neural-network training is made.

## Voice/video note
The UI accepts media. Direct local transcription currently supports WAV when SpeechRecognition is installed. MP3/M4A/video conversion requires FFmpeg and an approved transcription engine.

## Market API note
Set `MARKET_API_URL` only to an authorized endpoint. The prototype does not pretend that a generic public API is cigarette-market intelligence.
