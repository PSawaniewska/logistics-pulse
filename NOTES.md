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

- Sanity check on the cleaned data: late rate 6.77%, on-time 93.2% of
  delivered orders. The SQL analysis is the official source for this figure.

### clean_order_items.py

- The carrier handoff date comes from data/processed/orders.parquet, not from
  the raw CSV. One source of truth, and it makes clean_orders.py a prerequisite.

- The merge is validated as many-to-one, so a duplicate order_id in orders would
  raise instead of silently multiplying rows. Row count after the merge is
  112 650, unchanged.

- missed_shipping_deadline is NA when the carrier date is missing (1 194 items),
  never False. Same rule as is_late.

- 10 423 of the 111 456 items with a known flag (9.35%) were handed to the
  carrier after the seller's deadline. That is higher than the 6.77% of orders
  delivered late, which suggests the promised delivery date carries some slack.
  The two rates sit on different grains - items vs orders - so they can only be
  compared properly once items are aggregated to order level in the SQL
  analysis.

- freight_value has 383 zeros (0.34%). Free shipping is a normal seller
  promotion, so a zero cost is plausible - unlike a zero duration. No action
  taken; the column is left as is.

- The date comparison here is a local function rather than a shared helper,
  even though clean_orders.py does something similar. Two uses were not enough
  to justify a shared module; revisit if a third one appears.

### clean_geography.py

- geolocation is reduced to one coordinate pair per zip code prefix, using the
  median of lat and lng. The median is used instead of the mean because a single
  badly geocoded point would pull an average away from the real location.

- 31 rows across 20 zip prefixes sit far outside Brazil - one as far as
  longitude +121, which is the eastern hemisphere. These are dropped before
  aggregating.

- Checked whether those could be genuine foreign orders rather than bad
  coordinates. They cannot: customer_state has exactly 27 values, which is
  Brazil's 26 states plus the Federal District, and 16 of the 20 affected
  prefixes also carry valid Brazilian coordinates in their other rows. One zip
  prefix cannot be in two hemispheres at once.

- 4 zip prefixes had only bad coordinates and disappear after filtering, leaving
  19 011 of 19 015. Customers and sellers in those prefixes get no distance.

- distance_km uses the haversine formula and is written to its own file,
  order_distances.parquet, keyed by order_id and order_item_id. It is not added
  to order_items.parquet, so neither script overwrites the other's output.

- The grain is the order item, not the order: one order can have several sellers
  in different parts of the country.

- 555 of 112 650 items (0.49%) have no distance, because one of the two zip
  prefixes involved has no coordinates.

- Distances: median 432 km, mean 597 km, max 3 579 km. The maximum sits below
  Brazil's longest diagonal of roughly 4 000 km - a quick check that the formula
  returns real distances and not nonsense.

- Two limitations for any analysis that uses distance. It is a straight line,
  not a road distance, so real transport distance is longer. And it is measured
  between zip prefix centres, so two addresses inside the same prefix come out
  as 0 km - anything below a few tens of kilometres is resolution noise rather
  than signal.

### Open questions

- The seller scorecard will need a minimum order count per seller, otherwise
  sellers with 3 orders will top the list.

- clean_orders.py is run from the cleaning/ folder (paths start with ../),
  while pytest is run from the project root. Both work, but README's How to
  Run must say this explicitly, or a fresh clone will fail on the CSV path.