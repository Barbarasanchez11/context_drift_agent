# Demo Dataset Reference

See root-level `DEMO_DATASET.md` for the full selection record.

## Quick Reference

**URN:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)`

**Platform:** Snowflake | **Name:** `order_entry_db.order_entry.customers`

**Field for demo:** `credit_limit` — current type `NUMBER`, description `"Maximum credit amount for the customer"`

**Drift scenario:** type changes `NUMBER → STRING` (e.g. field now stores `"5000 EUR"`)

**DataHub endpoint (local Quickstart):**
- GMS: `http://localhost:8080`
- Frontend: `http://localhost:9002`
- Auth: `datahub / datahub`

## Verified Schema (from live DataHub, 2026-07-31)

```
customer_id        NUMBER
cust_first_name    STRING
cust_last_name     STRING
credit_limit       NUMBER   ← demo field
cust_email         STRING
account_mgr_id     NUMBER
customer_since     STRING
customer_class     STRING
dob                STRING
phone_number       STRING
address_line1-3    STRING
town_city          STRING
country_id         NUMBER
zipcode            NUMBER
region_id          NUMBER
```
