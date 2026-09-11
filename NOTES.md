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

## Phase 2 - Cleaning

### clean_orders.py

- delay_days uses dates, not timestamps. order_estimated_delivery_date is
  always 00:00:00, order_delivered_customer_date has real times. Raw
  timestamps would mark all 1 292 same-day deliveries as late and push the
  late rate from 6.77% to 8.11%.

- is_late is NA when delay_days is unknown, never False. 2 965 orders were
  never delivered, plus 8 "delivered" ones with no delivery date. Marking
  them False would make the baseline look better than it is.

- Non-delivered orders are kept with delay_days NULL, not dropped. The late
  rate covers delivered orders only - 6.77% of 96 470.

- Negative stage durations become NA, not zero. A negative value means the
  two timestamps contradict each other. Two flags record which stage:
  carrier_before_approved (1 359 rows) and delivered_before_carrier (23).
  Closes both open questions from Phase 1.

- delay_days is not affected by carrier_before_approved - neither column is
  in the formula. It can be affected by delivered_before_carrier, because
  the delivery date is in the formula. 23 rows, kept and flagged.

- Stage durations are in hours. In days, payment approval would round to
  zero almost everywhere.

- Sanity check before Phase 4: late rate 6.77%, on-time 93.2% of delivered
  orders. SQL in Phase 4 is the official source.

### Open questions

- Seller scorecard (Phase 4) needs a minimum order count per seller,
  otherwise sellers with 3 orders will top the list.

- clean_orders.py is run from the cleaning/ folder (paths start with ../),
  while pytest is run from the project root. Both work, but README's How to
  Run must say this explicitly, or a fresh clone will fail on the CSV path.