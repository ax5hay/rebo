"""Products, customers and CRM, pricing, sales orders, contracts, subscriptions (the Energy Cloud SaaS)."""
from __future__ import annotations

import datetime as dt

from h import *  # noqa: F403

FAMILIES = {  # business unit id -> (category, [(model prefix, name, base price INR, uom id)])
    1: ("Smart meters", [("SM1", "Single-phase smart meter", 2900, 1), ("SM3", "Three-phase smart meter", 7800, 1),
                         ("SMC", "CT-operated smart meter", 14500, 1), ("DCU", "Data concentrator unit", 48000, 1),
                         ("NIC", "RF mesh comms module", 1900, 1), ("PRE", "Prepaid meter kit", 4200, 9)]),
    2: ("Solar inverters", [("SI3K", "3 kW string inverter", 38000, 1), ("SI5K", "5 kW string inverter", 52000, 1),
                            ("SI10", "10 kW three-phase inverter", 98000, 1), ("SI50", "50 kW commercial inverter", 310000, 1),
                            ("HYB", "Hybrid inverter with battery port", 125000, 1), ("MON", "Solar monitoring gateway", 9500, 1)]),
    3: ("EV chargers", [("AC7", "7.4 kW AC wallbox", 42000, 1), ("AC22", "22 kW AC charger", 98000, 1),
                        ("DC30", "30 kW DC fast charger", 820000, 1), ("DC60", "60 kW DC fast charger", 1450000, 1),
                        ("DC120", "120 kW DC charger", 2650000, 1), ("CAB", "Type 2 charging cable", 9800, 1)]),
    4: ("Grid equipment", [("RTU", "Remote terminal unit", 185000, 1), ("FPI", "Fault passage indicator", 24000, 1),
                           ("PQM", "Power quality analyser", 76000, 1), ("CTS", "Current transformer set", 6800, 9)]),
}
PRODUCTS = [(bu, cat, f"{p}-{v}", f"{name} {vname}".strip(), round(price * mult, -1), uom)
            for bu, (cat, items) in FAMILIES.items() for p, name, price, uom in items
            for v, vname, mult in [("A", "", 1.0), ("B", "Pro", 1.28), ("C", "Lite", 0.84), ("IP", "IP65 outdoor", 1.12),
                                   ("X", "Export (CE)", 1.18), ("U", "UL listed", 1.22)]]
PRODUCTS += [(4, "Spares", f"SP-{i:03d}", n, p, 1) for i, (n, p) in enumerate([
    ("Meter terminal cover", 120), ("LCD module", 640), ("Main relay 100A", 980), ("Optical port", 310), ("IGBT power module", 8400),
    ("DC contactor 250A", 12600), ("Cooling fan 120mm", 1450), ("Control board (charger)", 21800), ("RFID reader", 3900),
    ("Surge protection device", 2600), ("Battery backup pack", 5200), ("Enclosure gasket kit", 450), ("Communication SIM (M2M)", 350),
    ("Firmware licence key", 1800), ("Installation kit", 1100), ("Mounting bracket", 690)], 1)]
PRODUCTS += [(5, "Software", "CLD-" + c, n, p, 7) for c, n, p in [
    ("IMPL", "Energy Cloud implementation (per hour)", 4500), ("TRN", "Operator training (per hour)", 3200), ("API", "API integration (per hour)", 5200)]]

STAGES = [("Prospecting", 10), ("Qualification", 20), ("Needs analysis", 35), ("Proposal", 55), ("Negotiation", 75),
          ("Closed won", 100), ("Closed lost", 0)]


def _price(r, g):
    return r["list_price_inr"]


def _order_status(r, g):
    return age_status("order_date", [(60, ["Delivered", "Closed", "Cancelled"], [62, 30, 8]),
                                     (20, ["Shipped", "Delivered", "Partially shipped", "Cancelled"], [30, 50, 14, 6]),
                                     (5, ["Confirmed", "In production", "Partially shipped", "On hold"], [45, 30, 15, 10])],
                      "Draft")(r, g)


def _tax(r, g):
    """GST 18 % in India (IGST across states), VAT or sales tax in the subsidiaries' countries, zero-rated exports."""
    c = r["@sales_order_id"]["_cc"]
    return {"IN": g.pick([1, 5], [70, 30]), "GB": 6, "DE": 7, "US": 8, "AE": 10}.get(c, 9)


def _territory(r, g):
    c, st = r["_cc"], r["_state"]
    if c == "IN":
        return {"27": 1, "24": 1, "08": 1, "23": 1, "29": 2, "33": 2, "36": 2, "32": 2, "07": 3, "09": 3, "06": 3, "03": 3}.get(st, 4)
    return {"GB": 5, "IE": 5, "DE": 6, "FR": 7, "NL": 7, "ES": 7, "US": 8, "SG": 9, "AE": 10, "AU": 11, "JP": 11}.get(c, 8)


def _stage(r, g):
    """Older opportunities are closed (won about a third of the time); recent ones are spread over the funnel."""
    age = (END - r["created_on"]).days
    if age > 240:
        return g.pick([6, 7, 5], [33, 60, 7])
    if age > 90:
        return g.pick([3, 4, 5, 6, 7], [10, 20, 20, 20, 30])
    return g.pick([1, 2, 3, 4, 7], [30, 30, 20, 15, 5])


TABLES = [
    lookup("brand", [("Orbitra", "ORB"), ("Orbitra Volt", "VOLT"), ("Orbitra Sunline", "SUN"), ("GridSense by Orbitra", "GRID")]),
    Table("product_category", 0, [col("category_name", S(60)), fk("business_unit_id", "business_unit", null=0.01)],
          fixed=[{"category_name": c, "business_unit_id": bu} for bu, c in [(1, "Smart meters"), (2, "Solar inverters"), (3, "EV chargers"),
                                                                           (4, "Grid equipment"), (4, "Spares"), (5, "Software")]]),
    lookup("warranty_policy", [("12 months standard", "W12"), ("24 months standard", "W24"), ("60 months inverter", "W60"),
                               ("Extended 36 months", "X36"), ("No warranty", "NONE")], {"months": [12, 24, 60, 36, 0]}),
    Table("product", 0, [col("sku", S(20)), col("product_name", S(140)), fk("product_category_id", "product_category"), fk("brand_id", "brand"),
                         fk("business_unit_id", "business_unit"), fk("uom_id", "uom"), col("list_price_inr", N), col("standard_cost_inr", N),
                         col("hsn_code", S(8)), fk("warranty_policy_id", "warranty_policy"), col("launched_on", D), col("is_active", B),
                         col("weight_kg", N)],
          fixed=[{"sku": sku, "product_name": name, "product_category_id": {"Smart meters": 1, "Solar inverters": 2, "EV chargers": 3, "Grid equipment": 4,
                                                                             "Spares": 5, "Software": 6}[cat],
                  "brand_id": {1: 4, 2: 3, 3: 2, 4: 4, 5: 1}[bu], "business_unit_id": bu, "uom_id": uom, "list_price_inr": price,
                  "standard_cost_inr": round(price * (0.52 + (i % 17) / 100), -1),
                  "hsn_code": {1: "90283010", 2: "85044090", 3: "85044030", 4: "85371000", 5: "998314"}[bu],
                  "warranty_policy_id": {1: 2, 2: 3, 3: 2, 4: 1, 5: 5}[bu] if cat != "Spares" else 1,
                  "launched_on": dt.date(2017 + i % 9, 1 + i % 12, 1), "is_active": i % 13 != 0, "weight_kg": round(0.4 + (i % 40) * 1.7, 1)}
                 for i, (bu, cat, sku, name, price, uom) in enumerate(PRODUCTS, 1)]),
    Table("product_spec", 0, [fk("product_id", "product"), col("spec_key", S(40), ch(["Rated voltage", "Rated current", "Accuracy class", "IP rating",
                                                                                       "Operating temperature", "Communication", "Efficiency", "Dimensions"])),
                              col("spec_value", S(60), ch(["230 V", "415 V", "10-60 A", "Class 1.0", "IP54", "IP65", "-25 to 60 C", "RF mesh",
                                                           "NB-IoT", "4G LTE", "97.8 %", "98.4 %", "420 x 300 x 160 mm"]))], per=("product", 3, 6)),
    Table("product_certification", 0, [fk("product_id", "product"), col("standard", S(30), ch(["BIS IS 16444", "IEC 62052", "CE", "UL 2594", "IEC 61851",
                                                                                                  "MNRE ALMM", "IEC 62109", "ARAI"])),
                                       col("certificate_no", S(30), lambda r, g: f"CERT-{g.int(10000, 99999)}"), col("valid_until", D, when(dt.date(2025, 1, 1), dt.date(2029, 12, 31), 1.0))],
          per=("product", 0, 3)),
    Table("price_list", 0, [col("price_list_name", S(60)), col("currency_code", S(3)), col("valid_from", D), col("is_default", B)],
          fixed=[{"price_list_name": f"{n} {c} {y}", "currency_code": c, "valid_from": dt.date(y, 4, 1), "is_default": y == 2026}
                 for y in (2024, 2025, 2026) for n, c in [("Domestic", "INR"), ("Export", "USD"), ("Europe", "EUR"), ("UK", "GBP"), ("Middle East", "AED")]]),
    Table("price_list_item", 0, [fk("price_list_id", "price_list"), fk("product_id", "product"),
                                 col("unit_price", N, lambda r, g: local(r["@product_id"]["list_price_inr"] * (1 + 0.06 * (r["@price_list_id"]["valid_from"].year - 2024))
                                                                         * (1.15 if r["@price_list_id"]["currency_code"] != "INR" else 1), r["@price_list_id"]["currency_code"]))],
          per=("price_list", lambda p, g: len(PRODUCTS)), comment="Price of every product in each price list"),
    lookup("customer_segment", [("Enterprise", "ENT"), ("Mid-market", "MID"), ("SMB", "SMB"), ("Utility", "UTL"), ("Government", "GOV"),
                                ("Channel partner", "CHN")]),
    lookup("lead_source", ["Website", "Trade show", "Partner referral", "Cold call", "LinkedIn", "Tender portal", "Existing customer", "Webinar"]),
    lookup("sales_territory", [("India West", "INW"), ("India South", "INS"), ("India North", "INN"), ("India East", "INE"), ("UK and Ireland", "UKI"),
                               ("DACH", "DACH"), ("Western Europe", "WEU"), ("North America", "NAM"), ("South-East Asia", "SEA"), ("Middle East", "MEA"),
                               ("Australia and Japan", "APJ")]),
    Table("sales_rep", 180, [fk("employee_id", "employee", where=lambda p, r: p["department_id"] == 1), fk("sales_territory_id", "sales_territory"),
                             col("quota_band", S(20), ch(["Junior", "Senior", "Key account"], [40, 45, 15])), col("is_active", B, yes(0.88))]),
    Table("customer_account", 6500, [
        cc(), col("_state", S(2), lambda r, g: g.pick(INDIAN_STATES)[0]),
        col("_pay_delay", I, lambda r, g: g.pick([-6, 0, 4, 12, 35, 80], [12, 30, 25, 18, 10, 5])),  # how late this customer pays
        col("account_number", S(12), code("CUS", 6), unique=True), col("account_name", S(160), company_name()),
        fk("industry_id", "industry", skew=0.7), fk("customer_segment_id", "customer_segment", skew=0.5),
        col("country_code", S(2), copy("_cc")), col("gstin", S(15), gstin()), col("vat_number", S(20), vat_no()),
        col("pan_number", S(10), lambda r, g: pan("C")(r, g) if r["_cc"] == "IN" else None),
        col("billing_currency", S(3), currency_of()), fk("payment_term_id", "payment_term", skew=0.6),
        col("credit_limit", N, lambda r, g: local(g.money(200000, 80000000, 50000, 2.2), CURRENCY.get(r["_cc"], "INR"))),
        fk("sales_territory_id", "sales_territory", pick=_territory),
        fk("account_owner_id", "sales_rep", match=("sales_territory_id", "sales_territory_id")),
        col("created_on", D, when(dt.date(2016, 1, 1), growth=1.5)),
        col("status", S(12), lambda r, g: g.pick(["Active", "Prospect", "Dormant", "Blacklisted"], [72, 15, 12, 1])),
        col("website", S(120), lambda r, g: f"www.{ascii_slug(r['account_name'].split(' ')[0])}{ascii_slug(r['account_name'].split(' ')[1]) if len(r['account_name'].split(' ')) > 2 else ''}.{ {'IN': 'in', 'GB': 'co.uk', 'DE': 'de', 'FR': 'fr', 'NL': 'nl', 'AU': 'com.au', 'SG': 'sg', 'AE': 'ae', 'JP': 'jp', 'ES': 'es', 'IE': 'ie'}.get(r['_cc'], 'com')}", null=0.25),
    ]),
    Table("customer_site", 0, [fk("customer_account_id", "customer_account"), cc("@customer_account_id._cc"), col("site_name", S(120), lambda r, g: g.pick(
        ["Head office", "Plant", "Warehouse", "Substation", "Solar park", "Charging hub", "Data centre", "Branch"]) + " " + g.faker(r["_cc"]).city()),
        col("address_line", S(200), street()), col("city", S(80), city()), col("postcode", S(12), postcode()),
        col("state_name", S(60), lambda r, g: dict(INDIAN_STATES).get(r["@customer_account_id"]["_state"]) if r["_cc"] == "IN" else None),
        col("country_code", S(2), copy("_cc")), col("is_billing", B, lambda r, g: r["_i"] % 3 == 1), col("latitude", N4, lambda r, g: round(g.normal(19, 6, -40, 60), 4)),
        col("longitude", N4, lambda r, g: round(g.normal(76, 20, -120, 150), 4))], per=("customer_account", 1, 4)),
    Table("contact", 0, [fk("customer_account_id", "customer_account"), cc("@customer_account_id._cc"), col("first_name", S(60), person_name("first")),
                         col("last_name", S(60), person_name("last")), col("job_title", S(80), ch(["Procurement Manager", "Chief Engineer", "CFO", "Head of Operations",
                                                                                                     "Project Manager", "Director", "Electrical Engineer", "CEO", "Sustainability Lead"])),
                         col("email", S(120), lambda r, g: email_of(r["@customer_account_id"]["website"].replace("www.", "") if r["@customer_account_id"]["website"] else None)(r, g)),
                         col("phone", S(30), phone()), col("is_primary", B, lambda r, g: r["_i"] % 4 == 1),
                         col("email_opt_in", B, yes(0.62)), col("created_on", D, after("@customer_account_id.created_on", 0, 900))],
          per=("customer_account", 1, 5)),
    Table("lead", 22000, [cc(), col("company_name", S(160), company_name()), col("contact_name", S(120), fake("name")), col("email", S(120), email_of()),
                          col("phone", S(30), phone()), fk("lead_source_id", "lead_source", skew=0.4), fk("industry_id", "industry"),
                          col("interest", S(40), ch(["Smart meters", "Solar inverters", "EV chargers", "Grid equipment", "Energy Cloud"], [30, 25, 30, 5, 10])),
                          col("created_on", D, when(dt.date(2022, 4, 1))), fk("owner_rep_id", "sales_rep", null=0.15),
                          col("status", S(14), age_status("created_on", [(90, ["Converted", "Disqualified", "Nurturing"], [18, 60, 22]),
                                                                         (14, ["Contacted", "Qualified", "Disqualified", "Nurturing"], [35, 25, 25, 15])], "New")),
                          col("score", I, rng(0, 100)), fk("converted_account_id", "customer_account", declare=False, optional=True)],
          post=["UPDATE lead SET converted_account_id = NULL WHERE status <> 'Converted'"]),
    lookup("opportunity_stage", [(s, s.upper().replace(" ", "_")) for s, _ in STAGES], {"probability_pct": [p for _, p in STAGES]}),
    Table("opportunity", 11000, [fk("customer_account_id", "customer_account", skew=0.6), col("opportunity_name", S(160), lambda r, g: f"{r['@customer_account_id']['account_name'].split(' ')[0]} - "
                                 + g.pick(["AMI rollout", "rooftop solar", "fleet charging", "DC fast charging corridor", "meter replacement", "grid automation",
                                           "Energy Cloud subscription", "inverter retrofit", "campus charging", "prepaid metering"])),
                                 fk("owner_rep_id", "sales_rep"), fk("lead_source_id", "lead_source"), col("created_on", D, when(dt.date(2022, 4, 1))),
                                 col("expected_close", D, after("created_on", 30, 240)), fk("opportunity_stage_id", "opportunity_stage", pick=_stage),
                                 col("currency", S(3), copy("@customer_account_id.billing_currency")),
                                 col("amount", N, lambda r, g: local(g.money(150000, 180000000, 1000, 2.6), r["currency"])),
                                 col("closed_on", D, lambda r, g: g.after(r["created_on"], 20, 300) if r["opportunity_stage_id"] in (6, 7) else None),
                                 col("loss_reason", S(40), lambda r, g: g.pick(["Price", "Competitor product", "No budget", "Timing", "Lost to incumbent", "Tender cancelled"])
                                     if r["opportunity_stage_id"] == 7 else None)]),
    Table("opportunity_line", 0, [fk("opportunity_id", "opportunity"), fk("product_id", "product", skew=0.5), col("quantity", N, qty_for("@product_id.list_price_inr", 900000, 1.5)),
                                  col("unit_price", N, lambda r, g: local(r["@product_id"]["list_price_inr"], r["@opportunity_id"]["currency"]))], per=("opportunity", 1, 4)),
    lookup("competitor", ["Secure Meters", "Genus Power", "Landis+Gyr", "Itron", "SMA", "Huawei FusionSolar", "Delta Electronics", "ABB E-mobility",
                          "Tata Power EZ Charge", "Exicom", "Schneider Electric", "Siemens"]),
    Table("opportunity_competitor", 5200, [fk("opportunity_id", "opportunity"), fk("competitor_id", "competitor", skew=0.6), col("their_price_known", B, yes(0.3))]),
    Table("quote", 9000, [fk("opportunity_id", "opportunity", skew=0.2), col("quote_number", S(16), code("QT", 7)), col("revision", I, ch([1, 1, 1, 2, 3])),
                          col("issued_on", D, after("@opportunity_id.created_on", 5, 120)), col("valid_until", D, after("issued_on", 30, 90)),
                          col("currency", S(3), copy("@opportunity_id.currency")), col("discount_pct", N, ch([0.0, 2.5, 5.0, 7.5, 10.0, 15.0], [30, 15, 25, 12, 12, 6])),
                          col("total_amount", N, const(0)), col("status", S(12), ch(["Sent", "Accepted", "Rejected", "Expired", "Draft"], [20, 30, 20, 25, 5]))],
          post=["UPDATE quote SET total_amount = COALESCE((SELECT SUM(l.quantity * l.unit_price) FROM quote_line l WHERE l.quote_id = quote.quote_id), 0) * (100 - discount_pct) / 100"]),
    Table("quote_line", 0, [fk("quote_id", "quote"), fk("product_id", "product", skew=0.5), col("quantity", N, qty_for("@product_id.list_price_inr", 400000)),
                            col("unit_price", N, lambda r, g: local(r["@product_id"]["list_price_inr"], r["@quote_id"]["currency"]))], per=("quote", 1, 5)),
    Table("customer_contract", 2600, [fk("customer_account_id", "customer_account", skew=0.4), col("contract_number", S(16), code("CTR", 6)),
                                      col("contract_type", S(20), ch(["Supply", "Annual maintenance", "Rate contract", "Framework", "SaaS"], [35, 25, 15, 10, 15])),
                                      col("start_date", D, when(dt.date(2021, 4, 1))), col("end_date", D, after("start_date", 365, 1825)),
                                      col("currency", S(3), copy("@customer_account_id.billing_currency")),
                                      col("contract_value", N, lambda r, g: local(g.money(500000, 400000000, 10000, 2.4), r["currency"])),
                                      col("auto_renew", B, yes(0.4)), col("status", S(12), lambda r, g: "Expired" if r["end_date"] is None or r["end_date"] < END else g.pick(["Active", "Suspended"], [95, 5]))]),
    Table("sales_order", 42000, [
        fk("customer_account_id", "customer_account", skew=0.7, where=lambda p, r: p["status"] != "Prospect"),
        cc("@customer_account_id._cc"),
        col("order_number", S(16), lambda r, g: f"SO{r['_i']:07d}", unique=True), col("order_date", D, when()),
        col("_ship", I, lambda r, g: r["_i"]),
        fk("ship_to_site_id", "customer_site", match=("customer_account_id", "customer_account_id"), declare=False),
        fk("sales_rep_id", "sales_rep"), fk("legal_entity_id", "legal_entity", where=lambda p, r: p["legal_entity_id"] == {"IN": 1, "GB": 2, "IE": 2, "DE": 3, "FR": 3, "NL": 3, "ES": 3,
                                                                                                                       "US": 4, "SG": 5, "AU": 5, "JP": 5, "AE": 6}.get(r["_cc"], 1)),
        col("currency", S(3), copy("@customer_account_id.billing_currency")),
        fk("payment_term_id", "payment_term"), fk("incoterm_id", "incoterm", null=0.5),
        col("customer_po_ref", S(30), lambda r, g: f"PO/{g.int(1000, 99999)}/{r['order_date'].year}", null=0.2),
        col("status", S(20), _order_status), col("channel", S(12), ch(["Direct", "Partner", "Tender", "Online"], [55, 25, 15, 5])),
        col("requested_delivery", D, after("order_date", 7, 75)),
        col("subtotal", N, const(0)), col("tax_amount", N, const(0)), col("total_amount", N, const(0)), col("total_amount_inr", N, const(0)),
    ], comment="Customer orders; amounts in the order currency; total_amount_inr uses the fixed budget rate of the year, not fx_rate",
          ),
    Table("sales_order_line", 0, [fk("sales_order_id", "sales_order"), col("line_no", I, lambda r, g: r["_i"] % 6 + 1), fk("product_id", "product", skew=0.55),
                                  col("quantity", N, qty_for("@product_id.list_price_inr")),
                                  col("unit_price", N, lambda r, g: local(r["@product_id"]["list_price_inr"] * (1.15 if r["@sales_order_id"]["currency"] != "INR" else 1), r["@sales_order_id"]["currency"])),
                                  col("discount_pct", N, ch([0.0, 0.0, 2.0, 5.0, 8.0, 12.0])),
                                  col("line_amount", N, lambda r, g: round(r["quantity"] * r["unit_price"] * (100 - r["discount_pct"]) / 100, 2)),
                                  fk("tax_code_id", "tax_code", pick=_tax),
                                  col("delivered_qty", N, lambda r, g: r["quantity"] if r["@sales_order_id"]["status"] in ("Delivered", "Closed") else
                                      (round(r["quantity"] * g.pick([0, 0.5, 1]), 0) if r["@sales_order_id"]["status"] in ("Shipped", "Partially shipped") else 0.0))],
          per=("sales_order", 1, 6),
          after_load=["UPDATE sales_order SET subtotal = COALESCE((SELECT SUM(l.line_amount) FROM sales_order_line l WHERE l.sales_order_id = sales_order.sales_order_id), 0)",
                      "UPDATE sales_order SET tax_amount = ROUND(COALESCE((SELECT SUM(l.line_amount * t.rate_pct / 100) FROM sales_order_line l JOIN tax_code t ON t.tax_code_id = l.tax_code_id "
                      "WHERE l.sales_order_id = sales_order.sales_order_id), 0), 2)",
                      "UPDATE sales_order SET total_amount = subtotal + tax_amount",
                      "UPDATE sales_order SET total_amount_inr = ROUND(total_amount * CASE currency WHEN 'INR' THEN 1 WHEN 'USD' THEN 83.1 WHEN 'GBP' THEN 105.2 "
                      "WHEN 'EUR' THEN 90.3 WHEN 'SGD' THEN 61.9 WHEN 'AED' THEN 22.6 WHEN 'AUD' THEN 54.8 WHEN 'JPY' THEN 0.56 ELSE 1 END, 2)"],
          reload=[("sales_order", ["subtotal", "tax_amount", "total_amount", "total_amount_inr"])]),
    Table("crm_activity", 52000, [fk("customer_account_id", "customer_account", skew=0.5), fk("contact_id", "contact", null=0.3, declare=False, match=("customer_account_id", "customer_account_id")), fk("sales_rep_id", "sales_rep"),
                                  col("activity_type", S(12), ch(["Call", "Email", "Meeting", "Site visit", "Demo"], [35, 35, 15, 10, 5])),
                                  col("activity_at", TS, lambda r, g: g.ts(g.date(dt.date(2022, 4, 1)))), col("duration_min", I, ch([5, 15, 30, 45, 60, 120, 240])),
                                  col("subject", S(160), words(3, 8)), col("outcome", S(20), ch(["Positive", "Neutral", "Negative", "No answer"], [35, 40, 10, 15]))]),
    Table("sales_target", 0, [fk("sales_rep_id", "sales_rep"), col("fiscal_quarter", S(8), lambda r, g: f"FY{25 + (r['_i'] % 8) // 4}Q{r['_i'] % 4 + 1}"),
                              col("target_amount_inr", N, money(2000000, 60000000, 100000, 1.4))], per=("sales_rep", 8, 8)),
    Table("commission_plan", 0, [col("plan_name", S(40)), col("rate_pct", N), col("accelerator_pct", N)],
          fixed=[{"plan_name": n, "rate_pct": a, "accelerator_pct": b} for n, a, b in [("Standard FY26", 2.0, 3.0), ("Key account FY26", 1.5, 2.5), ("Channel FY26", 1.0, 1.5)]]),
    Table("commission_payout", 0, [fk("sales_rep_id", "sales_rep"), fk("commission_plan_id", "commission_plan"), col("payout_month", D, lambda r, g: dt.date(2025 + (r["_i"] % 18 + 3) // 12, (r["_i"] % 18 + 3) % 12 + 1, 1)),
                                   col("amount_inr", N, money(0, 400000, 100, 2.0)), col("status", S(10), ch(["Paid", "Approved", "Held"], [85, 10, 5]))],
          per=("sales_rep", 6, 18)),
    # ---- Energy Cloud: subscriptions ----
    Table("subscription_plan", 0, [col("plan_code", S(12)), col("plan_name", S(60)), col("billing_period", S(10)), col("price_inr", N), col("included_devices", I)],
          fixed=[{"plan_code": c, "plan_name": n, "billing_period": p, "price_inr": pr, "included_devices": d} for c, n, p, pr, d in [
              ("BASIC-M", "Energy Cloud Basic", "Monthly", 4900, 50), ("BASIC-Y", "Energy Cloud Basic", "Annual", 49000, 50),
              ("PRO-M", "Energy Cloud Pro", "Monthly", 18900, 500), ("PRO-Y", "Energy Cloud Pro", "Annual", 189000, 500),
              ("ENT-Y", "Energy Cloud Enterprise", "Annual", 1450000, 10000), ("CPO-M", "Charge Point Operator", "Monthly", 29900, 200)]]),
    lookup("plan_feature", ["Live dashboards", "Alerts", "Billing export", "Open API", "Remote firmware update", "OCPP 2.0.1 backend",
                            "Tariff engine", "SSO", "Dedicated support", "Data residency (India)"]),
    lookup("churn_reason", ["Price", "Moved to competitor", "Project ended", "Budget cut", "Poor support", "Missing feature", "Company closed"]),
    Table("subscription", 3800, [fk("customer_account_id", "customer_account", skew=0.4), fk("subscription_plan_id", "subscription_plan", skew=0.6),
                                 col("started_on", D, when(dt.date(2022, 1, 1))), col("devices_licensed", I, lambda r, g: r["@subscription_plan_id"]["included_devices"] * g.pick([1, 1, 2, 3])),
                                 col("currency", S(3), copy("@customer_account_id.billing_currency")),
                                 col("mrr", N, lambda r, g: local(r["@subscription_plan_id"]["price_inr"] / (12 if r["@subscription_plan_id"]["billing_period"] == "Annual" else 1)
                                                                  * r["devices_licensed"] / r["@subscription_plan_id"]["included_devices"], r["currency"])),
                                 col("cancelled_on", D, lambda r, g: g.after(r["started_on"], 60, 1200) if g.chance(0.24) else None),
                                 fk("churn_reason_id", "churn_reason", optional=True),
                                 col("status", S(12), lambda r, g: "Cancelled" if r["cancelled_on"] else g.pick(["Active", "Trial", "Past due"], [86, 6, 8]))],
          post=["UPDATE subscription SET churn_reason_id = NULL WHERE cancelled_on IS NULL"]),
    Table("subscription_event", 0, [fk("subscription_id", "subscription"), col("event_type", S(20), ch(["Created", "Upgraded", "Downgraded", "Renewed", "Payment failed", "Seats added"], [5, 15, 8, 50, 10, 12])),
                                    col("event_on", D, after("@subscription_id.started_on", 0, 1100)), col("mrr_delta", N, lambda r, g: local(g.money(-40000, 90000, 100, 1.0), r["@subscription_id"]["currency"]))],
          per=("subscription", 1, 5)),
    Table("usage_record", 0, [fk("subscription_id", "subscription"), col("usage_month", D, lambda r, g: dt.date(2025 + (r["_i"] % 18 + 3) // 12, (r["_i"] % 18 + 3) % 12 + 1, 1)),
                              col("active_devices", I, lambda r, g: int(r["@subscription_id"]["devices_licensed"] * g.normal(0.8, 0.2, 0.05, 1.3))),
                              col("api_calls", BI, lambda r, g: g.int(1000, 4000000)), col("data_gb", N, lambda r, g: round(g.normal(40, 30, 0.1, 900), 2))],
          per=("subscription", 4, 14)),
]
