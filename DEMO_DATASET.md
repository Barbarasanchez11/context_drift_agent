# Demo Dataset — Selection Record

**Project:** Context Drift Agent
**Purpose:** Document the concrete dataset and field used for the demo scenario,
replacing the illustrative `customer_profile / age` example used in earlier
architecture docs with a real dataset from the loaded showcase-ecommerce sample data.

---

## Dataset

**URN:** `urn:li:dataset:(urn:li:dataPlatform:snowflake,b2fd91.order_entry_db.order_entry.customers,PROD)`
**Platform:** Snowflake
**Name:** `order_entry_db.order_entry.customers`

---

## Field Chosen for the Demo

| Attribute | Value |
|---|---|
| Field | `credit_limit` |
| Current type | `Number` |
| Current description | `"Maximum credit amount for the customer"` |

---

## Demo Scenario

**Before:** `credit_limit` is type `Number`, description says _"Maximum credit amount
for the customer"_ — schema and documentation are consistent.

**Change:** `credit_limit` type is changed to `String` (simulating a schema migration
where the field starts storing values like `"5000 EUR"` instead of a raw number).

**Expected agent behavior:**

1. **Poller** detects the schema change (`Number → String`) on this field.
2. **Context Retriever** pulls the current description (`"Maximum credit amount for
   the customer"`) and any glossary terms.
3. **LLM Judge** evaluates: the description implies a numeric amount, but the field
   is now free-text — the existing documentation may no longer correctly describe how
   to interpret or aggregate this field.
4. **Metadata Writer** writes `context_stale=true` with a reason referencing the type
   change, into `customProperties` (see DECISIONS.md #006).

---

## Other Fields Observed on This Dataset (Reference / Backup Options)

| Field | Type | Description | Notes |
|---|---|---|---|
| `credit_limit` | Number | Maximum credit amount for the customer | **Selected** |
| `cust_email` | String | Customer email address | Tagged "Email Address" |
| `account_mgr_id` | Number | ID of the account manager assigned to the customer | |
| `customer_since` | String | Date when customer was first registered | Already a String storing a date — backup scenario (e.g. date format change) |
| `customer_class` | String | Classification of the customer (e.g., Platinum, Gold, Silver) | |
| `dob` | String | Customer date of birth | Tagged "PII" |
| `phone_number` | String | Customer contact phone number | Tagged "Phone Number" |
| `address_line1–3, town_city, country_id, zipcode, region_id` | Various | Customer address fields | Tagged "PII" |

---

## Backup Scenario

If `credit_limit` proves inconvenient during implementation:

**`customer_since`** — currently `String` but conceptually a date; a change in its
expected format could serve as a plausible drift scenario (e.g. format changes from
`YYYY-MM-DD` to `DD/MM/YYYY`).
