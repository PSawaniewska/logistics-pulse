# Logistics Pulse - working notes

Decisions, checks and limitations to use in the README. How the code works is
explained in the code comments, not here.

## Conventions

- Missing stays missing. The cleaning scripts leave unknown values empty
  instead of filling them with False, zero or a placeholder. An unknown delay
  counted as "on time" would make every headline number look better than it is.

## Cleaning

### clean_orders.py

- delay_days compares dates, not timestamps. The promised date is always
  00:00:00, the delivery date has real times. Using raw timestamps marks
  same-day deliveries as late and raises the late rate from 6.77% to 8.11%.

- The late rate covers delivered orders only. 2 965 orders never arrived, so
  "93.2% on time" does not mean "93.2% of orders arrived".

- Negative stage times become empty. Two flags say which dates contradict each
  other: carrier_before_approved (1 359 rows) and delivered_before_carrier
  (23). Both were open questions after exploration.

- delay_days is safe from the first flag but not from the second, because the
  delivery date is part of the formula. 23 rows, kept and flagged.

- Stage times are in hours. In days, payment approval would round to zero
  nearly everywhere.

### clean_order_items.py

- The carrier date is read from the cleaned orders file, not the raw CSV, so
  there is one source of truth for it. The cost is that clean_orders.py has to
  run first.

- Checked that adding it did not multiply rows: 112 650 items before and after.

- 9.35% of items missed the seller's deadline, against 6.77% of orders
  delivered late. Sellers break their deadline more often than the customer
  notices, so the promised date probably has spare time in it. The two rates
  count different things - items and orders - so this is a lead, not a result.

- freight_value has 383 zeros (0.34%). Free shipping is a normal promotion, so
  a zero cost is fine - a zero duration would not be. Left as is.

- The date comparison here is a local function, not a shared helper, although
  clean_orders.py does something similar. Two uses were not enough to justify
  a shared module.

### clean_geography.py

- One coordinate pair per zip code prefix, taken as the median of all its rows.
  Median, not mean, because one badly geocoded point would pull an average away
  from the real place.

- 31 rows in 20 prefixes sit outside Brazil, one at longitude +121. Checked
  whether these could be real foreign orders. They cannot: customer_state holds
  exactly Brazil's 27 regions, and 16 of those prefixes also have correct
  Brazilian points in their other rows.

- Checked the formula against the country: the longest distance is 3 579 km,
  under Brazil's longest diagonal of about 4 000 km. Tens of thousands would
  have meant a sign or radian error.

- 555 of 112 650 items (0.49%) have no distance, because one of the two zip
  prefixes has no coordinates.

- Distance is a straight line between prefix centres, not a road distance. The
  real distance is longer, and two addresses in one prefix come out as 0 km.
  Anything below a few tens of kilometres is noise, not signal.

### clean_payments.py - not written

- Boleto is a bank slip paid by hand. It takes 29 hours to clear, against 16
  minutes for a card. The delay is real, so the question was whether the
  customer feels it.

- They do not. Boleto orders are late 7.3% of the time, cards 6.7%: about 120
  extra late orders out of ~6 500, under 2%. The promised date has enough
  spare time to absorb the slower payment.

- So payment method is out of scope: no cleaning script and no table in the
  database.

### clean_reviews.py

- 547 orders have two or three reviews. A duplicate-row check finds nothing,
  because every review has its own id and only the order id repeats. Joined as
  it is, the table would quietly multiply those orders.

- The script keeps the review with the latest answer date, the customer's last
  word. An average was rejected: the score is a 1 to 5 scale, and an average
  gives values nobody chose.

- Checked that the answer dates have no gaps before sorting by them. An empty
  date sorts last and would be taken for the latest review.

- Checked that dropping those rows did not bend the data: the score
  distribution is the same, still 77% fours and fives.

- The output keeps only order_id and review_score. Comment text answers none
  of the questions this project asks.

- Reviews are worth keeping: late orders average 2.27 out of 5, on-time orders
  4.29. The review is written after delivery, so the gap points one way only.

### clean_products.py

- Category is the only thing this project needs from products. Name length,
  description length and photo count say something about the listing, not
  about delivery.

- Weight and dimensions were measured before being dropped. Heavier items do
  run late a little more often, but category already covers most of it -
  furniture and appliances are both heavy and slow. A category is also
  something a logistics team can act on. A weight bracket is not.

- Two of the 73 categories are missing from Olist's translation table and are
  translated in the script. Keeping the Portuguese name would put two
  languages in one column.

- 610 products have no category, so any split by category leaves them out.

## Database

### sql/schema.sql

- The schema describes the cleaned data, not the raw CSVs: no payments table,
  and products holds only a category.

- The zip code columns have no foreign key to geolocation. 157 customer and 7
  seller prefixes have no coordinates, and a foreign key would reject those
  rows instead of leaving the distance unknown.

- All five source timestamps stay in orders, so every calculated column can be
  checked against the dates it came from.

### database/load_data.py

- The database is built from data/processed. To rebuild it, delete the .duckdb
  file and run the script again.

- Loading is also a check on the cleaning phase: every foreign key matched,
  every primary key was unique and no CHECK failed. Row counts and empty-value
  counts match the parquet files.

## Open questions

- The seller scorecard needs a minimum number of orders per seller, or sellers
  with 3 orders will top the list.

- Scripts in cleaning/ and database/ run from their own folder (paths start
  with ../), pytest runs from the project root. README's How to Run has to say
  this, or a fresh clone fails on the file paths.

- reviews are one row per order, order_items one row per item. Any query
  joining them must group items to orders first, or one score gets counted
  once per item.