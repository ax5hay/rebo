"""Finance: chart of accounts, journals (balanced), receivables with real payment behaviour, banking,
budgets, fixed assets, tax filings, intercompany."""
from __future__ import annotations

import datetime as dt

from h import *  # noqa: F403

ACCOUNTS = [  # code, name, type, normal side
    ("1010", "Cash on hand", "Asset", "D"), ("1020", "HDFC Bank current account", "Asset", "D"), ("1021", "ICICI Bank current account", "Asset", "D"),
    ("1030", "Barclays GBP account", "Asset", "D"), ("1031", "Deutsche Bank EUR account", "Asset", "D"), ("1100", "Trade receivables - domestic", "Asset", "D"),
    ("1110", "Trade receivables - export", "Asset", "D"), ("1150", "Allowance for doubtful debts", "Asset", "C"), ("1200", "Raw material inventory", "Asset", "D"),
    ("1210", "Work in progress", "Asset", "D"), ("1220", "Finished goods", "Asset", "D"), ("1230", "Spares inventory", "Asset", "D"),
    ("1300", "GST input credit - CGST", "Asset", "D"), ("1301", "GST input credit - SGST", "Asset", "D"), ("1302", "GST input credit - IGST", "Asset", "D"),
    ("1310", "TDS receivable", "Asset", "D"), ("1400", "Prepaid expenses", "Asset", "D"), ("1500", "Plant and machinery", "Asset", "D"),
    ("1510", "Computers and IT equipment", "Asset", "D"), ("1520", "Vehicles", "Asset", "D"), ("1530", "Furniture and fixtures", "Asset", "D"),
    ("1540", "Leasehold improvements", "Asset", "D"), ("1590", "Accumulated depreciation", "Asset", "C"), ("1600", "Capital work in progress", "Asset", "D"),
    ("1700", "Intercompany receivable", "Asset", "D"), ("2010", "Trade payables - domestic", "Liability", "C"), ("2020", "Trade payables - import", "Liability", "C"),
    ("2100", "GST output - CGST", "Liability", "C"), ("2101", "GST output - SGST", "Liability", "C"), ("2102", "GST output - IGST", "Liability", "C"),
    ("2110", "TDS payable", "Liability", "C"), ("2120", "PF and ESI payable", "Liability", "C"), ("2130", "Professional tax payable", "Liability", "C"),
    ("2200", "Salaries payable", "Liability", "C"), ("2300", "Customer advances", "Liability", "C"), ("2400", "Deferred revenue - subscriptions", "Liability", "C"),
    ("2500", "Warranty provision", "Liability", "C"), ("2600", "Term loan - SBI", "Liability", "C"), ("2700", "Intercompany payable", "Liability", "C"),
    ("3010", "Share capital", "Equity", "C"), ("3020", "Retained earnings", "Equity", "C"), ("4010", "Sales - smart meters", "Revenue", "C"),
    ("4020", "Sales - solar inverters", "Revenue", "C"), ("4030", "Sales - EV chargers", "Revenue", "C"), ("4040", "Sales - grid equipment", "Revenue", "C"),
    ("4050", "Sales - spares", "Revenue", "C"), ("4100", "Subscription revenue", "Revenue", "C"), ("4200", "Service and AMC revenue", "Revenue", "C"),
    ("4300", "Export incentives", "Revenue", "C"), ("4900", "Foreign exchange gain", "Revenue", "C"), ("5010", "Cost of materials consumed", "Expense", "D"),
    ("5020", "Freight inward", "Expense", "D"), ("5030", "Change in inventories", "Expense", "D"), ("6010", "Salaries and wages", "Expense", "D"),
    ("6020", "Contribution to PF", "Expense", "D"), ("6030", "Staff welfare", "Expense", "D"), ("6100", "Rent", "Expense", "D"),
    ("6110", "Electricity", "Expense", "D"), ("6120", "Repairs and maintenance", "Expense", "D"), ("6130", "Insurance", "Expense", "D"),
    ("6140", "Travel and conveyance", "Expense", "D"), ("6150", "Communication", "Expense", "D"), ("6160", "Legal and professional fees", "Expense", "D"),
    ("6170", "Advertising and marketing", "Expense", "D"), ("6180", "Freight outward", "Expense", "D"), ("6190", "Warranty expense", "Expense", "D"),
    ("6200", "Software subscriptions", "Expense", "D"), ("6210", "Cloud hosting", "Expense", "D"), ("6220", "Bad debts written off", "Expense", "D"),
    ("6230", "Bank charges", "Expense", "D"), ("6240", "CSR expenditure", "Expense", "D"), ("6300", "Depreciation", "Expense", "D"),
    ("6400", "Interest on term loan", "Expense", "D"), ("6900", "Foreign exchange loss", "Expense", "D"), ("7010", "Income tax expense", "Expense", "D"),
]


def _lines(p, g):
    p["_n"], p["_k"], p["_sum"] = g.pick([2, 2, 3, 4, 5, 6], [30, 20, 20, 15, 10, 5]), 0, 0.0
    return p["_n"]


def _debit(r, g):
    p = r["@parent"]
    p["_k"] += 1
    if p["_k"] < p["_n"]:
        amt = g.money(500, 4500000, 1, 2.2)
        p["_sum"] += amt
        r["_side"] = "D"
        return amt
    r["_side"] = "C"
    return 0.0


def _credit(r, g):
    return round(r["@parent"]["_sum"], 2) if r["_side"] == "C" else 0.0


def _invoices(order, g):
    """An invoice for each order that has shipped something."""
    return 1 if order["status"] in ("Shipped", "Partially shipped", "Delivered", "Closed") else 0


def _receipts(inv, g):
    """How an invoice gets paid, by the customer's habit: in full, in two parts, partly (balance still
    open), or not yet (recent, a slow payer, or a bad debt)."""
    age = (END - inv["due_date"]).days
    delay = inv["_pay_delay"]
    if inv["_bad"]:
        mode = "none" if g.chance(0.7) else "partial"
    elif age < delay - 5:
        mode = g.pick(["none", "partial", "full"], [70, 15, 15])
    else:
        mode = g.pick(["full", "split", "partial"], [80, 14, 6])
    inv["_mode"], inv["_k"] = mode, 0
    return {"none": 0, "full": 1, "partial": 1, "split": 2}[mode]


def _receipt_amount(r, g):
    inv = r["@parent"]
    inv["_k"] += 1
    total = float(inv["total_amount"] or 0)
    if inv["_mode"] == "full":
        return round(total, 2)
    half = round(total * g.pick([0.3, 0.5, 0.6]) if inv["_mode"] == "partial" else total * 0.5, 2)
    return half if inv["_k"] == 1 else round(total - inv.get("_first", half), 2)


def _receipt_date(r, g):
    inv = r["@parent"]
    if inv["_k"] == 1:
        inv["_first"] = r["amount"]
    d = g.after(inv["due_date"], max(-25, inv["_pay_delay"] - 12), inv["_pay_delay"] + 18) or END
    d = max(d, inv["invoice_date"])
    return d if inv["_k"] == 1 else (g.after(d, 10, 45) or END)


TABLES = [
    lookup("account_type", ["Asset", "Liability", "Equity", "Revenue", "Expense"]),
    Table("gl_account", 0, [col("account_code", S(10)), col("account_name", S(80)), fk("account_type_id", "account_type"), col("normal_balance", S(1)),
                            col("is_active", B), col("is_control_account", B)],
          fixed=[{"account_code": c, "account_name": n, "account_type_id": ["Asset", "Liability", "Equity", "Revenue", "Expense"].index(t) + 1,
                  "normal_balance": side, "is_active": True, "is_control_account": c in ("1100", "1110", "2010", "2020")} for c, n, t, side in ACCOUNTS]),
    lookup("journal", [("Sales journal", "SJ"), ("Purchase journal", "PJ"), ("Payroll journal", "PY"), ("Bank journal", "BJ"),
                       ("General journal", "GJ"), ("Depreciation journal", "DJ"), ("Accruals", "AC")]),
    Table("journal_entry", 26000, [fk("journal_id", "journal", skew=0.5), fk("legal_entity_id", "legal_entity", skew=1.4), col("entry_number", S(16), code("JE", 7)),
                                   col("posting_date", D, when()), fk("fiscal_period_id", "fiscal_period", pick=lambda r, g: (r["posting_date"].year - 2021) * 12 + r["posting_date"].month - 3),
                                   col("description", S(200), lambda r, g: g.pick(["Accrual", "Reversal of accrual", "Freight provision", "Depreciation run", "Payroll posting",
                                                                                     "Bank charges", "FX revaluation", "GST set-off", "Customer receipt", "Vendor payment",
                                                                                     "Inventory adjustment", "Warranty provision", "Prepaid amortisation", "Intercompany recharge"])
                                       + f" - {r['posting_date']:%b %Y}"), col("source", S(12), ch(["Manual", "System", "Import", "Recurring"], [20, 65, 10, 5])),
                                   fk("created_by_id", "employee", declare=False),
                                   col("status", S(10), age_status("posting_date", [(10, ["Posted", "Reversed"], [97, 3])], "Draft"))],
          ),
    Table("journal_line", 0, [fk("journal_entry_id", "journal_entry"), fk("gl_account_id", "gl_account", skew=0.3),
                              col("debit", N, _debit), col("credit", N, _credit), fk("cost_center_id", "cost_center", null=0.4),
                              col("line_memo", S(120), words(2, 6), null=0.6)], per=("journal_entry", _lines),
          comment="Debits equal credits within each entry"),
    # ---- receivables ----
    Table("ar_invoice", 0, [
        fk("sales_order_id", "sales_order"), cc("@sales_order_id._cc"),
        col("_pay_delay", I, lambda r, g: g.by_id("customer_account", r["@sales_order_id"]["customer_account_id"])["_pay_delay"]),
        col("_bad", B, lambda r, g: r["_pay_delay"] >= 80 and g.chance(0.5)),
        fk("customer_account_id", "customer_account", pick=lambda r, g: r["@sales_order_id"]["customer_account_id"]),
        fk("legal_entity_id", "legal_entity", pick=lambda r, g: r["@sales_order_id"]["legal_entity_id"]),
        col("invoice_number", S(20), lambda r, g: f"{'INV' if r['_cc'] == 'IN' else 'EXP'}/{r['@sales_order_id']['order_date'].year % 100:02d}-{r['_i']:06d}", unique=True),
        col("invoice_date", D, lambda r, g: g.after(r["@sales_order_id"]["order_date"], 4, 35) or END),
        col("due_date", D, lambda r, g: r["invoice_date"] + dt.timedelta(days=g.by_id("payment_term", r["@sales_order_id"]["payment_term_id"])["due_days"])),
        col("currency", S(3), copy("@sales_order_id.currency")),
        col("subtotal", N, copy("@sales_order_id.subtotal")), col("tax_amount", N, copy("@sales_order_id.tax_amount")),
        col("total_amount", N, copy("@sales_order_id.total_amount")), col("total_amount_inr", N, copy("@sales_order_id.total_amount_inr")),
        col("irn", S(64), lambda r, g: secret()(r, g)[7:71] if r["_cc"] == "IN" else None),
        col("status", S(16), const("Open")),
    ], per=("sales_order", _invoices), comment="Customer invoices; irn is the Indian e-invoice reference",
          post=["UPDATE ar_invoice SET status = CASE "
                "WHEN COALESCE((SELECT SUM(x.amount) FROM ar_receipt x WHERE x.ar_invoice_id = ar_invoice.ar_invoice_id), 0) >= total_amount - 0.01 THEN 'Paid' "
                "WHEN COALESCE((SELECT SUM(x.amount) FROM ar_receipt x WHERE x.ar_invoice_id = ar_invoice.ar_invoice_id), 0) > 0 THEN 'Partially paid' "
                "WHEN due_date < '2026-10-20' THEN 'Overdue' ELSE 'Open' END"]),
    Table("ar_invoice_line", 0, [fk("ar_invoice_id", "ar_invoice"), fk("product_id", "product"), col("quantity", N), col("unit_price", N),
                                 col("line_amount", N), fk("tax_code_id", "tax_code")], fixed=[],
          post=["INSERT INTO ar_invoice_line (ar_invoice_line_id, ar_invoice_id, product_id, quantity, unit_price, line_amount, tax_code_id) "
                "SELECT l.sales_order_line_id, i.ar_invoice_id, l.product_id, l.quantity, l.unit_price, l.line_amount, l.tax_code_id "
                "FROM sales_order_line l JOIN ar_invoice i ON i.sales_order_id = l.sales_order_id"]),
    lookup("payment_method", ["NEFT", "RTGS", "SWIFT wire", "Cheque", "UPI", "SEPA transfer", "ACH", "Letter of credit"]),
    Table("ar_receipt", 0, [fk("ar_invoice_id", "ar_invoice"), fk("customer_account_id", "customer_account", pick=lambda r, g: r["@parent"]["customer_account_id"]),
                            col("receipt_number", S(16), code("RCPT", 7)), col("amount", N, _receipt_amount), col("receipt_date", D, _receipt_date),
                            col("currency", S(3), copy("@parent.currency")),
                            fk("payment_method_id", "payment_method", pick=lambda r, g: g.pick([1, 2, 4, 5], [55, 25, 8, 12]) if r["@parent"]["_cc"] == "IN" else g.pick([3, 6, 7, 8], [50, 25, 15, 10])),
                            col("bank_reference", S(30), lambda r, g: f"UTR{g.int(10 ** 11, 10 ** 12 - 1)}")],
          per=("ar_invoice", _receipts), comment="Money received from customers against invoices"),
    Table("credit_note", 1800, [fk("ar_invoice_id", "ar_invoice", where=lambda p, r: True), col("credit_note_number", S(16), code("CN", 6)),
                                col("issued_on", D, after("@ar_invoice_id.invoice_date", 3, 120)), col("reason", S(40), ch(["Price difference", "Damaged in transit", "Short supply",
                                                                                                                                "Warranty replacement", "Rate contract revision", "Duplicate billing"])),
                                col("amount", N, lambda r, g: round(float(r["@ar_invoice_id"]["total_amount"] or 0) * g.pick([0.02, 0.05, 0.1, 0.25, 1.0], [30, 30, 20, 15, 5]), 2)),
                                col("currency", S(3), copy("@ar_invoice_id.currency"))]),
    Table("dunning_notice", 0, [fk("ar_invoice_id", "ar_invoice"), col("level", I, lambda r, g: r["_i"] % 3 + 1),
                                col("sent_on", D, lambda r, g: g.after(r["@parent"]["due_date"], 7 + 14 * (r["_i"] % 3), 10 + 14 * (r["_i"] % 3)) or END),
                                col("channel", S(10), ch(["Email", "Letter", "Phone"], [75, 10, 15]))],
          per=("ar_invoice", lambda p, g: g.int(1, 3) if p["_pay_delay"] >= 35 and p["due_date"] < END - dt.timedelta(days=30) else 0)),
    # ---- banking ----
    Table("bank", 0, [col("bank_name", S(60)), col("swift_code", S(11)), col("country_code", S(2))],
          fixed=[{"bank_name": n, "swift_code": s, "country_code": c} for n, s, c in [("HDFC Bank", "HDFCINBB", "IN"), ("ICICI Bank", "ICICINBB", "IN"),
                                                                                    ("State Bank of India", "SBININBB", "IN"), ("Barclays", "BARCGB22", "GB"),
                                                                                    ("Deutsche Bank", "DEUTDEFF", "DE"), ("JPMorgan Chase", "CHASUS33", "US"),
                                                                                    ("DBS Bank", "DBSSSGSG", "SG"), ("Emirates NBD", "EBILAEAD", "AE")]]),
    Table("bank_account", 0, [fk("bank_id", "bank"), fk("legal_entity_id", "legal_entity"), col("account_label", S(60)), col("account_number", S(30)),
                              col("currency", S(3)), fk("gl_account_id", "gl_account")],
          fixed=[{"bank_id": b, "legal_entity_id": e, "account_label": lbl, "account_number": num, "currency": cur, "gl_account_id": gl} for b, e, lbl, num, cur, gl in [
              (1, 1, "HDFC collections", "50200019283746", "INR", 2), (2, 1, "ICICI payments", "001905012345", "INR", 3), (3, 1, "SBI term loan", "39876543210", "INR", 2),
              (1, 1, "HDFC EEFC USD", "50200077112233", "USD", 2), (4, 2, "Barclays GBP", "20325511", "GBP", 4), (5, 3, "Deutsche EUR", "DE89370400440532013000", "EUR", 5),
              (6, 4, "Chase USD", "000123456789", "USD", 2), (7, 5, "DBS SGD", "0720118812", "SGD", 2), (8, 6, "ENBD AED", "1015512345601", "AED", 2)]]),
    Table("bank_statement_line", 34000, [fk("bank_account_id", "bank_account", skew=1.6), col("value_date", D, when()),
                                         col("narration", S(160), lambda r, g: g.pick(["NEFT CR", "RTGS CR", "IMPS DR", "SWIFT CR", "CHQ DEP", "BANK CHG", "GST PMT", "SALARY BATCH", "ACH DR", "INT CR"])
                                             + " " + g.faker("US").bothify("??########").upper()),
                                         col("amount", N, lambda r, g: round(g.money(50, 9000000, 1, 2.5) * g.pick([1, -1], [55, 45]), 2)),
                                         col("is_reconciled", B, lambda r, g: (END - r["value_date"]).days > 20 or g.chance(0.4))],
          comment="Positive amounts are credits to the account"),
    # ---- budgets ----
    Table("budget", 0, [col("fiscal_year", S(9)), fk("cost_center_id", "cost_center"), col("version", S(10)), col("approved_on", D)],
          fixed=[{"fiscal_year": fy, "cost_center_id": c, "version": v, "approved_on": dt.date(2000 + int(fy[2:4]), 3, 20)}
                 for fy in ("FY24-25", "FY25-26", "FY26-27") for c in range(1, 40) for v in ("Original",) + (("Revised",) if c % 4 == 0 else ())]),
    Table("budget_line", 0, [fk("budget_id", "budget"), fk("gl_account_id", "gl_account", where=lambda p, r: p["account_code"] >= "6000"),
                             col("period_no", I, lambda r, g: (r["_i"] % 12) + 1), col("amount_inr", N, money(20000, 3500000, 1000, 1.8))],
          per=("budget", 12, 36)),
    # ---- fixed assets ----
    lookup("asset_category", [("Plant and machinery", "PM"), ("Computers", "IT"), ("Vehicles", "VEH"), ("Furniture", "FUR"), ("Test equipment", "TEST"),
                              ("Leasehold improvements", "LHI")], {"useful_life_years": [15, 3, 8, 10, 7, 5]}),
    Table("fixed_asset", 3200, [fk("asset_category_id", "asset_category", skew=0.5), col("asset_tag", S(16), code("FA", 6)), col("description", S(160), lambda r, g: g.pick(
        ["SMT pick-and-place line", "Reflow oven", "Laptop Dell Latitude", "MacBook Pro", "Tata Ace delivery van", "Office chairs (lot)", "Oscilloscope Keysight",
         "Burn-in chamber", "Forklift 2T", "Server rack", "Conference room AV", "Climate chamber", "EV charger test rig", "Meter calibration bench"]) + f" #{r['_i']}"),
        fk("office_location_id", "office_location"), fk("custodian_id", "employee", null=0.4, declare=False), col("acquired_on", D, when(dt.date(2015, 4, 1), growth=1.3)),
        col("cost_inr", N, money(25000, 42000000, 100, 2.6)), col("salvage_value_inr", N, lambda r, g: round(r["cost_inr"] * 0.05, 2)),
        col("disposed_on", D, lambda r, g: g.after(r["acquired_on"], 900, 4000) if g.chance(0.12) else None),
        col("status", S(12), lambda r, g: "Disposed" if r["disposed_on"] else g.pick(["In use", "Under repair", "Idle"], [90, 4, 6]))]),
    Table("depreciation_entry", 0, [fk("fixed_asset_id", "fixed_asset"), col("fiscal_year", S(9), lambda r, g: f"FY{22 + r['_i'] % 5}-{23 + r['_i'] % 5}"),
                                    col("amount_inr", N, lambda r, g: round(float(r["@parent"]["cost_inr"]) / g.pick([3, 5, 8, 10, 15]), 2)), col("method", S(4), const("SLM"))],
          per=("fixed_asset", 1, 5)),
    # ---- tax ----
    Table("gst_return", 0, [col("gstin", S(15)), col("return_type", S(8)), col("tax_period", S(7)), col("filed_on", D), col("output_tax_inr", N),
                            col("input_credit_inr", N), col("cash_paid_inr", N), col("status", S(10))],
          fixed=[{"gstin": gin, "return_type": rt, "tax_period": f"{y}-{m:02d}", "filed_on": dt.date(y + (m == 12), m % 12 + 1, 11 if rt == "GSTR-1" else 20) if (y, m) < (2026, 10) else None,
                  "output_tax_inr": float(4000000 + (y * 7 + m * 13) % 9 * 900000), "input_credit_inr": float(2600000 + (y * 5 + m * 11) % 7 * 700000),
                  "cash_paid_inr": float(max(0, 1400000 + ((y * 7 + m * 13) % 9 - (y * 5 + m * 11) % 7) * 300000)), "status": "Filed" if (y, m) < (2026, 9) else "Pending"}
                 for gin in ("27AABCO4821K1Z5", "29AABCO4821K1Z3", "33AABCO4821K1Z1") for rt in ("GSTR-1", "GSTR-3B")
                 for y in range(2022, 2027) for m in range(1, 13) if (2022, 4) <= (y, m) <= (2026, 9)]),
    Table("intercompany_transfer", 700, [fk("from_entity_id", "legal_entity", declare=False), fk("to_entity_id", "legal_entity", declare=False),
                                         col("transfer_date", D, when(dt.date(2022, 4, 1))), col("purpose", S(40), ch(["Goods supply", "Management fee", "Royalty", "Loan", "Cost recharge"])),
                                         col("currency", S(3), ch(["INR", "USD", "EUR", "GBP"])), col("amount", N, money(10000, 25000000, 100, 2.0)),
                                         col("is_settled", B, yes(0.8))]),
]
