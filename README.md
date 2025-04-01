# Dynamic Pricing Tool

This web application helps determine competitive product prices based on internal purchase prices and publicly available pharmacy prices.

## Features (MVP)

- Upload a CSV with product names and purchase prices.
- Set a global margin.
- Scrape competitor prices from partner pharmacy websites.
- Calculate average and minimum market prices.
- Recommend a price based on margin and competitor pricing.

## Setup

1. Clone the repository.
2. Create a virtual environment: `python -m venv venv`
3. Activate the virtual environment: `source venv/bin/activate` (or `venv\Scripts\activate` on Windows)
4. Install dependencies: `pip install -r requirements.txt`
5. Run the application: `flask run` 