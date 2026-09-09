# Logistics Pulse - working notes

Running log of data quality findings, decisions, and open questions.
Condensed into the README's Limitations section at the end.

## Phase 1 - Setup & Exploration

- orders: 23 orders show a delivery date before the carrier handoff date -
  no clear explanation, open question for clean_orders.py.
- orders: 1 359 orders show carrier handoff before payment approval -
  fast processing, minor, likely no action needed.
- products: 610 rows missing category/name/description/photos together
  (incomplete listings). A separate 2 rows missing physical dimensions.
  Needs a decision in clean_products.py.
- geolocation: many duplicate/near-duplicate rows per zip code (~52 rows
  per code on average) - needs aggregating to one row per zip code before
  distance calculations.
- geolocation: 157 of 14 994 customer zip codes (1.0%) and 7 of 2 246
  seller zip codes (0.3%) have no match - a few distance calculations
  will end up missing, not a major gap.