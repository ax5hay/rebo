# Orbitra Energy Systems: a made-up company for testing ReBo

A complete, synthetic company database to test ReBo at enterprise size, unrelated to JMS. Everything is
invented with [Faker](https://pypi.org/project/Faker/) 40.43 (MIT) and a seed, so every build is the same.

**The company.** Orbitra Energy Systems Pvt Ltd (headquarters in Pune) makes smart meters, solar
inverters and EV chargers in two plants (Chakan and Hosur), sells an energy-monitoring SaaS ("Energy
Cloud"), and runs field service for the devices it installs. Subsidiaries in the UK, Germany, the US,
Singapore and the UAE. People, customers and suppliers are a mix of Indian (about 60 %) and foreign
(UK, US, Germany, France, the Netherlands, Singapore, the UAE, Australia, Spain, Ireland, Japan), with the
matching names, addresses, phone formats, currencies and tax identifiers (GSTIN, PAN, IFSC; VAT numbers).

| | |
|---|---|
| Tables | 221 (258 declared foreign keys, a few deliberately undeclared) |
| Rows | about 3.1 million (`build.py` prints the count per table) |
| Period | April 2021 to 20 October 2026; Indian fiscal year April–March |
| Size | about 500 MB in PostgreSQL 18 |

Domains: reference data and fx rates; organisation, HR, payroll (one payslip per employee per month),
leave, attendance, performance, training, recruiting, expenses; products, pricing, CRM, opportunities,
quotes, sales orders, contracts, subscriptions and usage; general ledger (balanced journals), receivables
with each customer's payment habit, credit notes, dunning, banking, budgets, fixed assets, GST returns;
suppliers, RFQs, purchase orders, goods receipts, payables, TDS; warehouses, stock, transfers;
bills of material, routings, work orders, inspections, defects, NCR and CAPA, maintenance; carriers,
shipments, tracking events, returns; installed devices, daily meter readings, EV charging sessions,
alerts, firmware; AMC contracts, service requests and visits, warranty claims; support tickets with SLAs,
comments, CSAT, knowledge base; projects, tasks, timesheets; campaigns, email, web sessions; portal
users, API keys, login and audit logs; IT assets and licences; facilities, visitors and fleet; policies,
audits, risks, legal cases, consent (DPDP Act, GDPR); R&D prototypes and lab tests; energy, emissions,
waste and CSR.

**Coherent on purpose.** Child dates follow their parents; invoice totals equal their order lines; journal
lines balance; receipts never precede invoices and never overpay; statuses follow age (old orders are
delivered, recent ones open); order sizes follow product price; business grows over time with a
festive-season bump. `tests/test_orbitra.py` checks these on every CI run.

**Quirks a real database has** (for ReBo to learn from people, never from configuration): amounts in
the transaction currency next to an INR amount at a fixed rate; statuses as free text in some tables and
lookup tables in others; undeclared keys (`manager_id`, `approver_id`, `payslip.employee_id`, ...);
secrets the bot must never show (password hashes, API tokens, bank account numbers, PAN); a polymorphic
`item_id` (material or product, by `item_type`).

## Run it

```bash
docker compose up -d orbitra-db                                   # PostgreSQL 18 on 127.0.0.1:5434
uv run --extra synth python fixtures/orbitra/build.py             # about 1 minute
REBO_CONFIG=fixtures/orbitra/rebo.yaml uv run rebo bootstrap      # catalog, values, local embeddings; no model
REBO_CONFIG=fixtures/orbitra/rebo.yaml uv run rebo serve --port 8100
REBO_CONFIG=fixtures/orbitra/rebo.yaml uv run python tools/orbitra_check.py   # offline checks, no model
```

The bot connects as `orbitra_ro`, a read-only login (`readonly-user.sql`). A small copy for quick work:
`build.py --sqlite /tmp/orbitra.db --scale 0.05`.

## Gold set

`gold.jsonl`: 48 questions across every domain, each with a PostgreSQL reference query, made by
`make_gold.py`. Questions name explicit periods so answers do not drift. `note` marks a known
ambiguity. `conversations.jsonl`: 8 vague openers with a follow-up that settles them, for
`tools/eval_conversations.py`.

Offline results (2026-10-22, `offline_check_2026-10-22.json`, no model):

| Check | Result |
|---|---|
| Gold queries pass ReBo's guard and return rows | 48/48, slowest 29 ms |
| Gold tables among the 8 "likely tables" of the first request | recall 0.845; all tables for 32/48 questions |
| A saved gold report asked again is answered with the gold rows and no model call | 48/48 (route "direct") |
| Protected columns found | 8: password hash, API token, 3 bank account numbers, 3 PAN columns |

Not run yet: any model on this database.
