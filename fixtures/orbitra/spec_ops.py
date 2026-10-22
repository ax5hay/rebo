"""Operations: suppliers and procurement (with payables), warehouses and stock, manufacturing and quality,
logistics and returns."""
from __future__ import annotations

import datetime as dt

from h import *  # noqa: F403

MATERIALS = [("PCB bare board", 180), ("Microcontroller STM32", 260), ("Current sensor", 95), ("LCD 128x64", 210), ("Relay 100A", 340),
             ("Polycarbonate enclosure", 120), ("Copper busbar", 850), ("IGBT module 1200V", 6400), ("DC link capacitor", 1450), ("Heat sink", 980),
             ("Cooling fan", 520), ("Type 2 socket", 3100), ("CCS2 connector", 18500), ("Cable 35 sq mm (m)", 410), ("Contactor 125A", 4300),
             ("Power supply 24V", 760), ("4G modem module", 1650), ("RF module 865 MHz", 380), ("Lithium cell 18650", 210), ("Screws and fasteners kit", 35),
             ("Gasket", 22), ("Label set", 6), ("Packaging carton", 48), ("Thermal paste", 90), ("Fuse 32A", 55), ("MOV surge arrester", 140),
             ("Ferrite core", 18), ("Inductor 2mH", 620), ("Transformer 10kVA", 14800), ("Wiring harness", 760)]


def _po_status(r, g):
    return age_status("order_date", [(90, ["Closed", "Cancelled"], [93, 7]), (25, ["Received", "Partially received", "Closed"], [45, 25, 30]),
                                     (5, ["Approved", "Sent", "Partially received"], [30, 55, 15])], "Draft")(r, g)


def _wo_status(r, g):
    return age_status("planned_start", [(30, ["Completed", "Closed", "Cancelled"], [55, 40, 5]), (5, ["In progress", "Completed", "On hold"], [60, 30, 10])],
                      "Released")(r, g)


def _ap_payments(inv, g):
    age = (END - inv["due_date"]).days
    n = 1 if age > -3 and g.chance(0.94) else 0
    inv["_n"] = n
    return n


TABLES = [
    # ---- suppliers and procurement ----
    lookup("supplier_category", ["Electronic components", "Mechanical parts", "Cables and wires", "Packaging", "Logistics services", "IT services",
                                 "Facility services", "Professional services", "Contract manufacturing", "Raw metals", "Office supplies", "Staffing"]),
    Table("supplier", 1400, [cc(), col("_c", S(2), lambda r, g: g.pick(["IN", "IN", "IN", "CN", "TW", "DE", "US", "JP", "SG", "GB"], [40, 20, 10, 10, 5, 4, 3, 3, 3, 2])),
                             col("supplier_code", S(12), code("SUP", 5), unique=True),
                             col("supplier_name", S(160), lambda r, g: (r.__setitem__("_cc", r["_c"] if r["_c"] in LOC_OK else "US") or company_name()(r, g))),
                             fk("supplier_category_id", "supplier_category", skew=0.8), col("country_code", S(2), copy("_c")),
                             col("gstin", S(15), lambda r, g: gstin()(r, g) if r["_c"] == "IN" else None),
                             col("pan_number", S(10), lambda r, g: pan("C")(r, g) if r["_c"] == "IN" else None),
                             col("is_msme", B, lambda r, g: r["_c"] == "IN" and g.chance(0.35)), fk("payment_term_id", "payment_term", skew=0.4),
                             col("currency", S(3), lambda r, g: {"IN": "INR", "DE": "EUR", "GB": "GBP", "SG": "SGD", "JP": "JPY"}.get(r["_c"], "USD")),
                             col("bank_account_no", S(30), lambda r, g: str(g.int(10 ** 11, 10 ** 13))), col("onboarded_on", D, when(dt.date(2014, 1, 1), growth=1.3)),
                             col("status", S(24), ch(["Approved", "Approved", "On hold", "Blocked", "Pending approval"], [60, 25, 6, 3, 6]))]),
    Table("supplier_contact", 0, [fk("supplier_id", "supplier"), cc("@supplier_id._cc"), col("contact_name", S(120), fake("name")), col("email", S(120), email_of()),
                                  col("phone", S(30), phone()), col("role", S(30), ch(["Sales", "Accounts", "Quality", "Logistics", "Owner"]))], per=("supplier", 1, 3)),
    Table("supplier_rating", 0, [fk("supplier_id", "supplier"), col("rated_quarter", S(8), lambda r, g: f"FY{24 + r['_i'] % 3}Q{r['_i'] % 4 + 1}"),
                                 col("quality_score", I, rng(55, 100)), col("delivery_score", I, rng(40, 100)), col("cost_score", I, rng(50, 100)),
                                 col("overall_grade", S(2), lambda r, g: "A" if (r["quality_score"] + r["delivery_score"] + r["cost_score"]) > 255 else "B" if
                                     (r["quality_score"] + r["delivery_score"] + r["cost_score"]) > 215 else "C")], per=("supplier", 0, 6)),
    Table("material", 0, [col("material_code", S(16)), col("material_name", S(120)), fk("uom_id", "uom"), col("standard_cost_inr", N),
                          col("lead_time_days", I), col("is_critical", B), fk("preferred_supplier_id", "supplier", declare=False)],
          fixed=[{"material_code": f"RM-{i:04d}", "material_name": f"{n}{'' if v == 0 else ' rev ' + 'ABCD'[v]}", "uom_id": 3 if "(m)" in n else 1,
                  "standard_cost_inr": round(c * (1 + v * 0.07), 2), "lead_time_days": 7 + (i * 13) % 80, "is_critical": c > 3000 or (i % 9 == 0),
                  "preferred_supplier_id": 1 + (i * 37) % 1000}
                 for i, (n, c, v) in enumerate([(n, c, v) for n, c in MATERIALS for v in range(4)], 1)]),
    Table("purchase_requisition", 7000, [fk("requested_by_id", "employee", declare=False), fk("department_id", "department", skew=0.5), col("requested_on", D, when(dt.date(2022, 4, 1))),
                                         col("needed_by", D, after("requested_on", 7, 60)), col("justification", S(200), words(4, 12), null=0.3),
                                         col("status", S(28), age_status("requested_on", [(20, ["Converted to PO", "Rejected", "Cancelled"], [82, 10, 8])], "Pending approval"))]),
    Table("rfq", 1600, [col("rfq_number", S(16), code("RFQ", 6)), fk("buyer_id", "employee", declare=False), col("issued_on", D, when(dt.date(2022, 4, 1))),
                        col("closes_on", D, after("issued_on", 7, 30)), fk("material_id", "material"), col("quantity", N, lambda r, g: float(g.pick([100, 500, 1000, 5000, 20000]))),
                        col("status", S(24), age_status("issued_on", [(35, ["Awarded", "Cancelled"], [85, 15])], "Open"))]),
    Table("rfq_response", 0, [fk("rfq_id", "rfq"), fk("supplier_id", "supplier", skew=0.6), col("quoted_price_inr", N, lambda r, g: round(float(g.by_id("material", r["@rfq_id"]["material_id"])["standard_cost_inr"]) * g.normal(1.0, 0.12, 0.6, 1.6), 2)),
                              col("lead_time_days", I, rng(5, 90)), col("is_awarded", B, const(False))], per=("rfq", 1, 5)),
    Table("purchase_order", 24000, [
        fk("supplier_id", "supplier", skew=0.9, where=lambda p, r: p["status"] in ("Approved", "On hold")),
        col("po_number", S(18), lambda r, g: f"PO/{r['_i']:06d}", unique=True), col("order_date", D, when()), fk("buyer_id", "employee", declare=False),
        fk("legal_entity_id", "legal_entity", skew=2.5), fk("ship_to_location_id", "office_location", where=lambda p, r: p["site_type"] in ("plant", "warehouse")),
        fk("purchase_requisition_id", "purchase_requisition", null=0.45), col("currency", S(3), copy("@supplier_id.currency")),
        fk("payment_term_id", "payment_term", pick=lambda r, g: r["@supplier_id"]["payment_term_id"]), fk("incoterm_id", "incoterm", null=0.6),
        col("expected_date", D, lambda r, g: g.after(r["order_date"], 5, 75)), col("status", S(20), _po_status),
        col("total_amount", N, const(0)), col("approved_by_id", I, lambda r, g: g.int(1, 3400) if r["status"] != "Draft" else None),
    ], comment="Purchase orders to suppliers; total in the PO currency"),
    Table("purchase_order_line", 0, [fk("purchase_order_id", "purchase_order"), fk("material_id", "material", skew=0.6), col("line_no", I, lambda r, g: r["_i"] % 8 + 1),
                                     col("quantity", N, qty_for("@material_id.standard_cost_inr", 180000, 1.2)),
                                     col("unit_price", N, lambda r, g: local(float(r["@material_id"]["standard_cost_inr"]) * g.normal(1.0, 0.08, 0.7, 1.4), r["@purchase_order_id"]["currency"])),
                                     col("received_qty", N, lambda r, g: r["quantity"] if r["@purchase_order_id"]["status"] in ("Closed", "Received") else
                                         (round(r["quantity"] * g.pick([0.3, 0.5, 0.8]), 0) if r["@purchase_order_id"]["status"] == "Partially received" else 0.0)),
                                     fk("tax_code_id", "tax_code", pick=lambda r, g: g.pick([1, 2, 5]) if r["@purchase_order_id"]["currency"] == "INR" else 9)],
          per=("purchase_order", 1, 8),
          after_load=["UPDATE purchase_order SET total_amount = COALESCE((SELECT ROUND(SUM(l.quantity * l.unit_price), 2) FROM purchase_order_line l "
                      "WHERE l.purchase_order_id = purchase_order.purchase_order_id), 0)"],
          reload=[("purchase_order", ["total_amount"])]),
    Table("goods_receipt", 0, [fk("purchase_order_id", "purchase_order"), col("grn_number", S(16), code("GRN", 7)),
                               col("received_on", D, lambda r, g: g.after(r["@parent"]["expected_date"], -5, 25) or END), fk("received_by_id", "employee", declare=False),
                               fk("warehouse_location_id", "office_location", pick=lambda r, g: r["@parent"]["ship_to_location_id"], declare=False),
                               col("status", S(24), ch(["Accepted", "Accepted", "Partially rejected", "Rejected"], [80, 10, 8, 2]))],
          per=("purchase_order", lambda p, g: 0 if p["status"] in ("Draft", "Approved", "Sent", "Cancelled") else (2 if p["status"] == "Partially received" else 1))),
    Table("goods_receipt_line", 0, [fk("goods_receipt_id", "goods_receipt"), fk("material_id", "material", skew=0.6), col("received_qty", N, lambda r, g: float(g.pick([10, 50, 100, 500, 1000, 5000]))),
                                    col("rejected_qty", N, lambda r, g: float(round(r["received_qty"] * g.pick([0, 0, 0, 0.01, 0.05]), 0))),
                                    col("lot_number", S(20), lambda r, g: f"LOT{g.int(100000, 999999)}")], per=("goods_receipt", 1, 4)),
    Table("ap_invoice", 0, [fk("purchase_order_id", "purchase_order"), fk("supplier_id", "supplier", pick=lambda r, g: r["@parent"]["supplier_id"]),
                            col("supplier_invoice_no", S(30), lambda r, g: f"{g.faker('US').bothify('??').upper()}/{g.int(100, 99999)}/{r['@parent']['order_date'].year % 100}"),
                            col("invoice_date", D, lambda r, g: g.after(r["@parent"]["expected_date"], 0, 20) or END),
                            col("due_date", D, lambda r, g: r["invoice_date"] + dt.timedelta(days=g.by_id("payment_term", r["@parent"]["payment_term_id"])["due_days"])),
                            col("currency", S(3), copy("@parent.currency")), col("amount", N, lambda r, g: round(float(r["@parent"]["total_amount"]) * g.pick([1.0, 1.0, 1.0, 0.98, 1.02]), 2)),
                            col("tds_amount", N, lambda r, g: round(r["amount"] * 0.02, 2) if r["currency"] == "INR" and g.chance(0.4) else 0.0),
                            col("match_status", S(32), ch(["3-way matched", "2-way matched", "Price variance", "Quantity variance"], [78, 10, 7, 5])),
                            col("status", S(24), const("Unpaid"))],
          per=("purchase_order", lambda p, g: 1 if p["status"] in ("Closed", "Received", "Partially received") else 0),
          post=["UPDATE ap_invoice SET status = CASE WHEN EXISTS (SELECT 1 FROM ap_payment p WHERE p.ap_invoice_id = ap_invoice.ap_invoice_id) THEN 'Paid' "
                "WHEN due_date < '2026-10-20' THEN 'Overdue' ELSE 'Unpaid' END"]),
    Table("ap_payment", 0, [fk("ap_invoice_id", "ap_invoice"), col("payment_ref", S(20), code("PAY", 7)), col("paid_on", D, lambda r, g: g.after(r["@parent"]["due_date"], -10, 20) or END),
                            col("amount", N, lambda r, g: round(float(r["@parent"]["amount"]) - float(r["@parent"]["tds_amount"]), 2)), col("currency", S(3), copy("@parent.currency")),
                            fk("bank_account_id", "bank_account", pick=lambda r, g: 2 if r["@parent"]["currency"] == "INR" else 4)],
          per=("ap_invoice", _ap_payments)),
    # ---- warehouses and stock ----
    Table("warehouse", 0, [col("warehouse_code", S(10)), col("warehouse_name", S(80)), fk("office_location_id", "office_location"), col("warehouse_type", S(20))],
          fixed=[{"warehouse_code": c, "warehouse_name": n, "office_location_id": l, "warehouse_type": t} for c, n, l, t in [
              ("WH-CHK-RM", "Chakan raw materials", 2, "Raw material"), ("WH-CHK-FG", "Chakan finished goods", 2, "Finished goods"),
              ("WH-HSR-RM", "Hosur raw materials", 4, "Raw material"), ("WH-HSR-FG", "Hosur finished goods", 4, "Finished goods"),
              ("WH-BHW", "Bhiwandi distribution centre", 6, "Distribution"), ("WH-CHN", "Chennai distribution centre", 7, "Distribution"),
              ("WH-MAN", "Manchester depot", 10, "Distribution"), ("WH-HYD-SP", "Hyderabad spares", 8, "Spares"), ("WH-KOL-SP", "Kolkata spares", 15, "Spares")]]),
    Table("bin_location", 0, [fk("warehouse_id", "warehouse"), col("bin_code", S(12), lambda r, g: f"{'ABCDEFGH'[r['_i'] % 8]}-{r['_i'] % 40:02d}-{r['_i'] % 5 + 1}"),
                              col("bin_type", S(12), ch(["Rack", "Floor", "Cold", "Quarantine"], [70, 20, 3, 7]))], per=("warehouse", 30, 80)),
    Table("stock_balance", 0, [fk("warehouse_id", "warehouse"), col("item_type", S(10), lambda r, g: "Material" if r["@parent"]["warehouse_type"] == "Raw material" else "Product"),
                               col("item_id", I, lambda r, g: g.int(1, 120) if r["item_type"] == "Material" else g.int(1, len(g.rows["product"]))),
                               col("on_hand_qty", N, lambda r, g: float(max(0, round(g.normal(400, 600, 0))))), col("reserved_qty", N, lambda r, g: float(round(r["on_hand_qty"] * g.pick([0, 0, 0.1, 0.3])))),
                               col("reorder_level", N, lambda r, g: float(g.pick([20, 50, 100, 250, 500]))), col("last_counted_on", D, when(dt.date(2025, 10, 1), growth=1.0))],
          per=("warehouse", 80, 140), comment="item_id points to material or product depending on item_type"),
    lookup("movement_type", [("Goods receipt", "GR"), ("Issue to production", "GI_PROD"), ("Production receipt", "PR"), ("Sales dispatch", "DISP"),
                             ("Customer return", "RET"), ("Transfer out", "TR_OUT"), ("Transfer in", "TR_IN"), ("Scrap", "SCRAP"), ("Count adjustment", "ADJ")],
           {"direction": [1, -1, 1, -1, 1, -1, 1, -1, 0]}),
    Table("stock_movement", 70000, [fk("warehouse_id", "warehouse", skew=0.6), fk("movement_type_id", "movement_type", skew=0.4),
                                    col("item_type", S(10), lambda r, g: "Material" if r["movement_type_id"] in (1, 2) else "Product"),
                                    col("item_id", I, lambda r, g: g.int(1, 120) if r["item_type"] == "Material" else g.int(1, len(g.rows["product"]))),
                                    col("quantity", N, lambda r, g: float(g.pick([1, 2, 5, 10, 20, 50, 100, 500, 1000]))), col("moved_at", TS, lambda r, g: g.ts(g.date())),
                                    col("reference_doc", S(30), lambda r, g: g.pick(["GRN", "WO", "SO", "TO", "RMA", "ADJ"]) + f"-{g.int(1, 99999):05d}"),
                                    fk("moved_by_id", "employee", declare=False)]),
    Table("cycle_count", 900, [fk("warehouse_id", "warehouse"), col("counted_on", D, when(dt.date(2023, 4, 1))), fk("counted_by_id", "employee", declare=False),
                               col("items_counted", I, rng(20, 400)), col("variance_items", I, rng(0, 25)), col("variance_value_inr", N, money(0, 400000, 10, 2.5))]),
    Table("transfer_order", 3200, [fk("from_warehouse_id", "warehouse", declare=False), fk("to_warehouse_id", "warehouse", declare=False),
                                   col("created_on", D, when(dt.date(2022, 4, 1))), col("shipped_on", D, after("created_on", 0, 5), null=0.05),
                                   col("received_on", D, after("shipped_on", 1, 9), null=0.08),
                                   col("status", S(24), lambda r, g: "Received" if r["received_on"] else "In transit" if r["shipped_on"] else "Open")]),
    Table("transfer_order_line", 0, [fk("transfer_order_id", "transfer_order"), fk("product_id", "product", skew=0.6), col("quantity", N, lambda r, g: float(g.pick([5, 10, 20, 50, 100, 300])))],
          per=("transfer_order", 1, 5)),
    # ---- manufacturing and quality ----
    Table("work_center", 0, [col("wc_code", S(12)), col("wc_name", S(80)), fk("office_location_id", "office_location"), col("capacity_per_shift", I), col("cost_per_hour_inr", N)],
          fixed=[{"wc_code": f"{p}-{c}", "wc_name": f"{n} ({p})", "office_location_id": loc, "capacity_per_shift": cap, "cost_per_hour_inr": cost}
                 for p, loc in (("CHK", 2), ("HSR", 4)) for c, n, cap, cost in [("SMT", "SMT line", 2400, 6800.0), ("THT", "Through-hole assembly", 900, 2400.0),
                                                                              ("AOI", "Optical inspection", 3000, 1900.0), ("ASM", "Final assembly", 600, 2100.0),
                                                                              ("CAL", "Calibration", 800, 2600.0), ("BRN", "Burn-in", 400, 1500.0),
                                                                              ("PKG", "Packing", 1200, 900.0), ("HV", "High-voltage test", 300, 3200.0)]]),
    Table("machine", 0, [fk("work_center_id", "work_center"), col("machine_tag", S(16), lambda r, g: f"MC-{r['_i']:04d}"), col("make_model", S(80), ch(
        ["Fuji NXT III", "Yamaha YSM20", "Heller 1936", "Koh Young Zenith", "Chroma 8000", "ESPEC climate chamber", "Hioki ST5520", "Custom test jig"])),
        col("commissioned_on", D, when(dt.date(2012, 1, 1), growth=1.0)), col("is_active", B, yes(0.93))], per=("work_center", 2, 6)),
    Table("machine_downtime", 6500, [fk("machine_id", "machine", skew=0.7), col("started_at", TS, lambda r, g: g.ts(g.date(dt.date(2023, 4, 1)), 0, 23)),
                                     col("duration_min", I, lambda r, g: int(g.normal(90, 120, 5, 2880))),
                                     col("reason", S(30), ch(["Breakdown", "Planned maintenance", "Changeover", "No material", "No operator", "Quality hold", "Power cut"], [30, 25, 20, 10, 5, 5, 5]))]),
    Table("bom", 0, [fk("product_id", "product"), col("revision", S(4), lambda r, g: g.pick(["A", "B", "C"])), col("effective_from", D, when(dt.date(2018, 1, 1), growth=1.0)),
                     col("is_current", B, const(True))], per=("product", lambda p, g: 1 if p["business_unit_id"] in (1, 2, 3, 4) and p["product_category_id"] != 5 else 0)),
    Table("bom_line", 0, [fk("bom_id", "bom"), fk("material_id", "material", skew=0.3), col("qty_per_unit", N4, lambda r, g: float(g.pick([1, 1, 2, 4, 6, 12, 0.5, 1.5]))),
                          col("scrap_pct", N, ch([0.0, 0.5, 1.0, 2.0]))], per=("bom", 6, 14)),
    Table("routing_step", 0, [fk("product_id", "product"), col("step_no", I, lambda r, g: (r["_i"] % 6 + 1) * 10), fk("work_center_id", "work_center"),
                              col("std_minutes", N, lambda r, g: round(g.normal(6, 5, 0.5, 45), 1))],
          per=("product", lambda p, g: g.int(4, 7) if p["business_unit_id"] in (1, 2, 3, 4) else 0)),
    Table("work_order", 16000, [col("wo_number", S(16), code("WO", 7)), fk("product_id", "product", skew=0.6, where=lambda p, r: p["business_unit_id"] in (1, 2, 3)),
                                fk("work_center_id", "work_center"), col("planned_qty", N, lambda r, g: float(g.pick([20, 50, 100, 250, 500, 1000, 2500]))),
                                col("planned_start", D, when()), col("planned_end", D, after("planned_start", 1, 12)),
                                col("status", S(28), _wo_status),
                                col("actual_start", D, lambda r, g: g.after(r["planned_start"], -1, 3) if r["status"] not in ("Released",) else None),
                                col("actual_end", D, lambda r, g: g.after(r["planned_end"], -1, 8) if r["status"] in ("Completed", "Closed") else None),
                                col("completed_qty", N, lambda r, g: round(r["planned_qty"] * g.normal(0.97, 0.04, 0.6, 1.0)) if r["actual_end"] else 0.0),
                                col("scrap_qty", N, lambda r, g: round(r["completed_qty"] * g.pick([0, 0.005, 0.01, 0.03, 0.08], [30, 30, 25, 10, 5]))),
                                fk("sales_order_id", "sales_order", null=0.6, declare=False)]),
    Table("material_issue", 0, [fk("work_order_id", "work_order"), fk("material_id", "material", skew=0.4), col("issued_qty", N, lambda r, g: float(r["@parent"]["planned_qty"]) * g.pick([1, 2, 4])),
                                col("issued_on", D, lambda r, g: r["@parent"]["actual_start"] or r["@parent"]["planned_start"])],
          per=("work_order", lambda p, g: g.int(3, 7) if p["actual_start"] else 0)),
    lookup("defect_type", ["Solder bridge", "Missing component", "Wrong polarity", "Calibration out of tolerance", "Enclosure crack", "Firmware flash failed",
                           "Insulation failure", "Cosmetic scratch", "Label misprint", "Connector loose", "Display dead pixel", "Overheating in burn-in"],
           {"severity": ["Major", "Critical", "Critical", "Major", "Minor", "Major", "Critical", "Minor", "Minor", "Major", "Minor", "Critical"]}),
    Table("quality_inspection", 0, [fk("work_order_id", "work_order"), col("inspection_stage", S(16), ch(["Incoming", "In-process", "Final", "Pre-dispatch"], [10, 35, 45, 10])),
                                    col("inspected_on", D, lambda r, g: r["@parent"]["actual_end"] or r["@parent"]["actual_start"] or r["@parent"]["planned_start"]),
                                    fk("inspector_id", "employee", declare=False), col("sample_size", I, ch([5, 13, 20, 32, 50, 80])),
                                    col("defects_found", I, lambda r, g: g.pick([0, 0, 0, 1, 2, 3, 5])),
                                    col("result", S(10), lambda r, g: "Pass" if r["defects_found"] == 0 else g.pick(["Pass", "Rework", "Fail"], [40, 45, 15]))],
          per=("work_order", lambda p, g: g.int(1, 3) if p["actual_start"] else 0)),
    Table("defect", 0, [fk("quality_inspection_id", "quality_inspection"), fk("defect_type_id", "defect_type", skew=0.7), col("units_affected", I, rng(1, 6)),
                        col("root_cause", S(30), ch(["Operator", "Machine", "Material", "Method", "Design", "Unknown"], [25, 20, 25, 15, 5, 10]))],
          per=("quality_inspection", lambda p, g: p["defects_found"])),
    Table("ncr", 1100, [col("ncr_number", S(16), code("NCR", 5)), fk("supplier_id", "supplier", null=0.5, skew=0.8), fk("work_order_id", "work_order", null=0.5),
                        col("raised_on", D, when(dt.date(2022, 4, 1))), col("description", S(240), words(6, 16)), col("disposition", S(20), ch(["Rework", "Scrap", "Use as is", "Return to supplier"])),
                        col("cost_of_poor_quality_inr", N, money(500, 2500000, 10, 2.4)), col("closed_on", D, after("raised_on", 3, 120), null=0.2)],
          comment="Non-conformance reports"),
    Table("capa", 600, [fk("ncr_id", "ncr"), col("action_type", S(12), ch(["Corrective", "Preventive"], [70, 30])), col("action", S(240), words(6, 14)),
                        fk("owner_id", "employee", declare=False), col("due_on", D, after("@ncr_id.raised_on", 14, 90)), col("done_on", D, after("due_on", -20, 40), null=0.25),
                        col("effective", B, yes(0.82))]),
    Table("maintenance_order", 5200, [fk("machine_id", "machine", skew=0.5), col("mo_type", S(14), ch(["Preventive", "Breakdown", "Calibration", "Inspection"], [45, 30, 15, 10])),
                                      col("opened_on", D, when(dt.date(2022, 4, 1))), col("closed_on", D, after("opened_on", 0, 21), null=0.06),
                                      fk("technician_id", "employee", declare=False), col("labour_hours", N, lambda r, g: round(g.normal(4, 3, 0.5, 40), 1)),
                                      col("parts_cost_inr", N, money(0, 350000, 10, 2.5))]),
    # ---- logistics ----
    Table("carrier", 0, [col("carrier_name", S(60)), col("mode", S(10)), col("country_code", S(2)), col("is_active", B)],
          fixed=[{"carrier_name": n, "mode": m, "country_code": c, "is_active": a} for n, m, c, a in [
              ("Blue Dart", "Air", "IN", True), ("Delhivery", "Road", "IN", True), ("Gati", "Road", "IN", True), ("VRL Logistics", "Road", "IN", True),
              ("TCI Freight", "Road", "IN", True), ("Safexpress", "Road", "IN", False), ("DHL Express", "Air", "DE", True), ("FedEx", "Air", "US", True),
              ("Maersk", "Sea", "DK", True), ("DB Schenker", "Road", "DE", True), ("Royal Mail Parcelforce", "Road", "GB", True), ("Aramex", "Air", "AE", True)]]),
    Table("shipment", 0, [fk("sales_order_id", "sales_order"), col("shipment_number", S(18), code("SHP", 7)), fk("carrier_id", "carrier", pick=lambda r, g: (
        g.pick([1, 2, 3, 4, 5], [15, 35, 20, 15, 15]) if r["@parent"]["_cc"] == "IN" else g.pick([7, 8, 9, 10, 11, 12], [30, 20, 20, 10, 10, 10]))),
        fk("from_warehouse_id", "warehouse", pick=lambda r, g: g.pick([2, 4, 5, 6]) if r["@parent"]["_cc"] == "IN" else g.pick([2, 7], [60, 40]), declare=False),
        col("shipped_on", D, lambda r, g: g.after(r["@parent"]["order_date"], 2, 40) or END), col("expected_delivery", D, after("shipped_on", 1, 21)),
        col("delivered_on", D, lambda r, g: g.after(r["expected_delivery"], -2, g.pick([0, 2, 6, 15], [55, 25, 15, 5])) if r["@parent"]["status"] in ("Delivered", "Closed") else None),
        col("tracking_number", S(30), lambda r, g: g.faker("US").bothify("##########")), col("freight_cost_inr", N, money(400, 380000, 10, 2.4)),
        col("gross_weight_kg", N, lambda r, g: round(g.normal(120, 300, 0.5, 9000), 1)), col("eway_bill_no", S(12), lambda r, g: str(g.int(10 ** 11, 10 ** 12 - 1)) if r["@parent"]["_cc"] == "IN" else None),
        col("status", S(28), lambda r, g: "Delivered" if r["delivered_on"] else g.pick(["In transit", "Out for delivery", "Exception"], [80, 12, 8]))],
          per=("sales_order", lambda p, g: 0 if p["status"] in ("Draft", "Confirmed", "In production", "On hold", "Cancelled") else (2 if p["status"] == "Partially shipped" else 1))),
    Table("shipment_event", 0, [fk("shipment_id", "shipment"), col("event_code", S(20), lambda r, g: ["PICKED_UP", "IN_TRANSIT", "AT_HUB", "OUT_FOR_DELIVERY", "DELIVERED"][r["_i"] % 5]),
                                col("event_at", TS, lambda r, g: g.ts(g.after(r["@parent"]["shipped_on"], r["_i"] % 5, r["_i"] % 5 + 2)), null=0.0),
                                col("location", S(60), lambda r, g: g.faker("IN").city())], per=("shipment", 3, 5)),
    lookup("return_reason", ["Damaged in transit", "Wrong item", "Defective on arrival", "Customer cancelled", "Excess quantity", "Warranty return"]),
    Table("return_authorization", 2400, [col("rma_number", S(16), code("RMA", 6)), fk("sales_order_id", "sales_order", where=lambda p, r: p["status"] in ("Delivered", "Closed")),
                                         fk("return_reason_id", "return_reason", skew=0.6), col("requested_on", D, after("@sales_order_id.order_date", 10, 200)),
                                         col("received_on", D, after("requested_on", 3, 30), null=0.15),
                                         col("resolution", S(16), lambda r, g: g.pick(["Replaced", "Credited", "Repaired", "Rejected"], [35, 35, 20, 10]) if r["received_on"] else "Pending")]),
    Table("return_line", 0, [fk("return_authorization_id", "return_authorization"), fk("product_id", "product", skew=0.5), col("quantity", N, lambda r, g: float(g.pick([1, 1, 2, 5, 10, 50]))),
                             col("condition", S(16), ch(["Unopened", "Damaged", "Faulty", "Used"], [20, 30, 40, 10]))], per=("return_authorization", 1, 3)),
]

LOC_OK = {"IN", "DE", "US", "GB", "SG", "JP"}
