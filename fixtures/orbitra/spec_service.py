"""The installed base and after-sales: devices in the field and their telemetry, EV charging sessions,
alerts, AMC contracts, field service visits, warranty claims, and customer support with SLAs."""
from __future__ import annotations

import datetime as dt

from h import *  # noqa: F403

VEHICLES = ["Tata Nexon EV", "Tata Punch EV", "MG ZS EV", "Mahindra XUV400", "Hyundai Ioniq 5", "BYD Atto 3", "Kia EV6", "Tesla Model 3",
            "VW ID.4", "BMW iX1", "Ola S1 (2W)", "Ather 450X (2W)", "Tata Ace EV (LCV)", "Euler HiLoad (3W)"]


def _sla_due(r, g):
    hours = {1: 4, 2: 8, 3: 24, 4: 72}[r["ticket_priority_id"]]
    return r["opened_at"] + dt.timedelta(hours=hours)


def _resolved(r, g):
    age = (dt.datetime(2026, 10, 20) - r["opened_at"]).days
    if age < 1 and g.chance(0.7):
        return None
    if age < 10 and g.chance(0.3):
        return None
    hours = {1: 3, 2: 10, 3: 30, 4: 90}[r["ticket_priority_id"]] * g.pick([0.3, 0.7, 1.0, 1.6, 3.5], [20, 35, 25, 15, 5])
    return r["opened_at"] + dt.timedelta(hours=hours)


TABLES = [
    Table("firmware_version", 0, [fk("business_unit_id", "business_unit"), col("version", S(12)), col("released_on", D), col("is_recommended", B), col("release_notes", S(200))],
          fixed=[{"business_unit_id": bu, "version": f"{maj}.{mi}.{p}", "released_on": dt.date(2021 + maj - 1 + (mi > 3), 1 + (mi * 3 + p) % 12, 5),
                  "is_recommended": (maj, mi) == (5, 4), "release_notes": "Security fixes and stability" if p else "Feature release"}
                 for bu in (1, 2, 3) for maj in range(1, 6) for mi in range(0, 5) for p in (0, 1)]),
    Table("device", 32000, [
        fk("customer_site_id", "customer_site", skew=0.9), col("_acct", I, lambda r, g: r["@customer_site_id"]["customer_account_id"]),
        fk("product_id", "product", skew=0.5, where=lambda p, r: p["business_unit_id"] in (1, 2, 3) and p["product_category_id"] in (1, 2, 3)),
        col("serial_number", S(24), lambda r, g: f"{r['@product_id']['sku'].split('-')[0]}{g.int(21, 26)}{r['_i']:07d}", unique=True),
        fk("sales_order_id", "sales_order", null=0.3, declare=False, match=("customer_account_id", "_acct")),
        col("installed_on", D, when(dt.date(2019, 1, 1), growth=1.7)),
        fk("firmware_version_id", "firmware_version", match=("business_unit_id", "@product_id.business_unit_id")),
        col("comm_type", S(10), ch(["RF mesh", "NB-IoT", "4G", "Ethernet", "Wi-Fi"], [35, 20, 30, 10, 5])),
        col("sim_iccid", S(22), lambda r, g: f"8991{g.int(10 ** 15, 10 ** 16 - 1)}" if r["comm_type"] in ("NB-IoT", "4G") else None),
        col("last_seen_at", TS, lambda r, g: dt.datetime(2026, 10, 20, 12) - dt.timedelta(minutes=g.pick([5, 30, 240, 3000, 30000, 200000], [50, 20, 12, 10, 5, 3]))),
        col("status", S(28), lambda r, g: "Decommissioned" if g.chance(0.04) else ("Offline" if (dt.datetime(2026, 10, 20, 12) - r["last_seen_at"]).days >= 2 else "Online")),
    ], comment="Meters, inverters and chargers installed at customer sites"),
    Table("meter_reading_daily", 140000, [fk("device_id", "device", skew=0.3), col("reading_date", D, when(dt.date(2025, 10, 1), growth=1.0)),
                                          col("energy_kwh", N, lambda r, g: round(g.normal(38, 30, 0, 900), 2)), col("peak_kw", N, lambda r, g: round(g.normal(6, 5, 0, 180), 2)),
                                          col("uptime_pct", N, lambda r, g: round(g.normal(98.5, 4, 40, 100), 2)), col("power_factor", N4, lambda r, g: round(g.normal(0.93, 0.05, 0.5, 1.0), 3)),
                                          col("tamper_flag", B, yes(0.004))], comment="One row per device per day it reported"),
    Table("charging_session", 65000, [fk("device_id", "device", skew=0.8, where=lambda p, r: p["product_id"] and p["serial_number"][:2] in ("AC", "DC")),
                                      col("started_at", TS, lambda r, g: g.ts(g.date(dt.date(2023, 1, 1), growth=2.2), 0, 23)),
                                      col("duration_min", I, lambda r, g: int(g.normal(55, 45, 4, 720))), col("energy_kwh", N, lambda r, g: round(r["duration_min"] / 60 * g.normal(14, 9, 1.5, 110), 2)),
                                      col("tariff_per_kwh", N, ch([14.0, 16.0, 18.0, 19.5, 21.0, 24.0])), col("amount_inr", N, lambda r, g: round(r["energy_kwh"] * r["tariff_per_kwh"], 2)),
                                      col("payment_mode", S(14), ch(["UPI", "RFID card", "App wallet", "Credit card", "Fleet account"], [45, 20, 20, 8, 7])),
                                      col("vehicle_model", S(40), ch(VEHICLES, [18, 12, 8, 7, 4, 4, 3, 3, 2, 2, 12, 10, 8, 7])),
                                      col("stop_reason", S(20), ch(["User stopped", "Battery full", "Timeout", "Fault", "Power cut"], [60, 25, 8, 4, 3]))]),
    lookup("alert_rule", [("Device offline > 24 h", "OFFLINE"), ("Tamper detected", "TAMPER"), ("Over-temperature", "OVERTEMP"), ("Ground fault", "GFAULT"),
                          ("Low power factor", "LOWPF"), ("Firmware update failed", "FWFAIL"), ("Connector stuck", "STUCK"), ("Grid voltage out of range", "VOLT")],
           {"severity": ["Warning", "Critical", "Critical", "Critical", "Info", "Warning", "Warning", "Warning"]}),
    Table("device_alert", 26000, [fk("device_id", "device", skew=0.9), fk("alert_rule_id", "alert_rule", skew=0.7), col("raised_at", TS, lambda r, g: g.ts(g.date(dt.date(2024, 1, 1)), 0, 23)),
                                  col("cleared_at", TS, lambda r, g: r["raised_at"] + dt.timedelta(minutes=g.int(5, 6000)) if g.chance(0.9) else None),
                                  col("acknowledged_by_id", I, lambda r, g: g.int(1, 3400) if g.chance(0.6) else None)]),
    Table("firmware_update_job", 3600, [fk("firmware_version_id", "firmware_version"), col("scheduled_for", TS, lambda r, g: g.ts(g.date(dt.date(2023, 1, 1)), 0, 6)),
                                        col("target_devices", I, rng(1, 5000)), col("succeeded", I, lambda r, g: int(r["target_devices"] * g.normal(0.95, 0.05, 0.4, 1.0))),
                                        col("failed", I, lambda r, g: r["target_devices"] - r["succeeded"])]),
    # ---- field service ----
    Table("technician", 0, [fk("employee_id", "employee"), fk("home_location_id", "office_location", pick=lambda r, g: g.pick([8, 15, 16, 1, 4, 10])),
                            col("vehicle_no", S(14), lambda r, g: f"MH{g.int(10, 50)} {g.pick(UP)}{g.pick(UP)} {g.int(1000, 9999)}"), col("is_contractor", B, yes(0.25))],
          per=("employee", lambda p, g: 1 if p["department_id"] == 13 and p["exit_date"] is None else 0)),
    Table("service_contract", 3200, [fk("customer_account_id", "customer_account", skew=0.5), col("contract_number", S(16), code("AMC", 6)),
                                     col("coverage", S(20), ch(["Comprehensive", "Labour only", "Parts only", "Remote monitoring"], [40, 30, 10, 20])),
                                     col("start_date", D, when(dt.date(2021, 4, 1))), col("end_date", D, after("start_date", 365, 1095)),
                                     col("devices_covered", I, rng(5, 4000)), col("annual_fee_inr", N, money(25000, 18000000, 1000, 2.3)),
                                     col("response_hours", I, ch([4, 8, 24, 48])), col("status", S(12), lambda r, g: "Expired" if r["end_date"] is None or r["end_date"] < END else "Active")]),
    Table("service_request", 19000, [col("sr_number", S(16), code("SR", 7)), fk("device_id", "device", skew=0.6), col("_acct", I, lambda r, g: r["@device_id"]["_acct"]),
                                     fk("customer_account_id", "customer_account", pick=lambda r, g: r["_acct"]),
                                     fk("service_contract_id", "service_contract", null=0.35, match=("customer_account_id", "_acct")),
                                     col("reported_at", TS, lambda r, g: g.ts(g.date(dt.date(2022, 4, 1)), 6, 22)),
                                     col("problem", S(30), ch(["Not powering on", "Display blank", "Communication lost", "Charging fails", "Inverter tripping", "Wrong reading",
                                                               "Physical damage", "Installation request", "Relocation", "Firmware issue"])),
                                     col("priority", S(8), ch(["P1", "P2", "P3", "P4"], [8, 22, 50, 20])),
                                     col("closed_at", TS, lambda r, g: r["reported_at"] + dt.timedelta(hours=g.int(2, 400)) if (END - r["reported_at"].date()).days > 3 or g.chance(0.3) else None),
                                     col("status", S(28), lambda r, g: g.pick(["Resolved", "Closed"], [40, 60]) if r["closed_at"] else g.pick(["Open", "Assigned", "On site", "Waiting parts"]))]),
    Table("service_visit", 0, [fk("service_request_id", "service_request"), fk("technician_id", "technician"),
                               col("visit_date", D, lambda r, g: g.after(r["@parent"]["reported_at"], 0, 6) or END),
                               col("travel_km", N, lambda r, g: round(g.normal(28, 25, 1, 400), 1)), col("time_on_site_min", I, lambda r, g: int(g.normal(75, 50, 10, 600))),
                               col("outcome", S(40), ch(["Fixed", "Fixed", "Part ordered", "Revisit needed", "Customer not available"], [55, 15, 15, 10, 5])),
                               col("customer_signature", B, yes(0.86))], per=("service_request", lambda p, g: g.pick([0, 1, 1, 1, 2, 3]) if p["closed_at"] or g.chance(0.5) else 0)),
    Table("visit_part_used", 0, [fk("service_visit_id", "service_visit"), fk("product_id", "product", where=lambda p, r: p["product_category_id"] == 5),
                                 col("quantity", N, lambda r, g: float(g.pick([1, 1, 1, 2, 4]))), col("billable", B, yes(0.35))], per=("service_visit", 0, 2)),
    Table("warranty_claim", 4200, [fk("device_id", "device", skew=0.5), col("claim_number", S(16), code("WC", 6)), col("claimed_on", D, lambda r, g: g.after(r["@device_id"]["installed_on"], 20, 1500) or END),
                                   col("failure_mode", S(30), ch(["Relay failure", "Display failure", "Comms module", "Power board", "Connector wear", "Water ingress", "Firmware brick"])),
                                   col("decision", S(12), ch(["Approved", "Rejected", "Pending"], [72, 18, 10])), col("cost_inr", N, money(300, 160000, 10, 2.2)),
                                   col("rejection_reason", S(40), lambda r, g: g.pick(["Out of warranty", "Physical damage", "Tampering", "Improper installation"]) if r["decision"] == "Rejected" else None)]),
    # ---- customer support ----
    lookup("ticket_priority", [("Urgent", "P1"), ("High", "P2"), ("Normal", "P3"), ("Low", "P4")], {"target_hours": [4, 8, 24, 72]}),
    lookup("ticket_category", ["Billing", "Login and access", "Device offline", "Data missing", "Charging failure", "Installation", "Feature request",
                               "API and integration", "Firmware", "Refund", "Account change", "Other"]),
    lookup("support_channel", ["Email", "Phone", "Web portal", "WhatsApp", "Chat", "Partner"]),
    Table("support_ticket", 30000, [col("ticket_number", S(16), lambda r, g: f"TKT-{r['_i'] + 100000}"), fk("customer_account_id", "customer_account", skew=0.7),
                                    fk("contact_id", "contact", null=0.15, match=("customer_account_id", "customer_account_id")),
                                    fk("ticket_category_id", "ticket_category", skew=0.5), fk("ticket_priority_id", "ticket_priority", pick=lambda r, g: g.pick([1, 2, 3, 4], [6, 20, 54, 20])),
                                    fk("support_channel_id", "support_channel", skew=0.6), col("subject", S(200), words(4, 10)),
                                    col("opened_at", TS, lambda r, g: g.ts(g.date(dt.date(2022, 4, 1)), 0, 23)), col("sla_due_at", TS, _sla_due),
                                    col("first_response_at", TS, lambda r, g: r["opened_at"] + dt.timedelta(minutes=int(g.normal(140, 200, 2, 4000)))),
                                    col("resolved_at", TS, _resolved), col("_support", I, const(14)), fk("assigned_agent_id", "employee", match=("department_id", "_support"), null=0.04),
                                    col("status", S(28), lambda r, g: g.pick(["Resolved", "Closed"], [30, 70]) if r["resolved_at"] else g.pick(["Open", "Pending customer", "In progress", "Escalated"], [35, 25, 30, 10])),
                                    col("sla_breached", B, lambda r, g: (r["resolved_at"] or dt.datetime(2026, 10, 20, 18)) > r["sla_due_at"])]),
    Table("ticket_comment", 0, [fk("support_ticket_id", "support_ticket"), col("author_type", S(10), ch(["Agent", "Customer", "System"], [50, 40, 10])),
                                col("body", TX, paragraph()), col("is_internal", B, yes(0.2)),
                                col("created_at", TS, lambda r, g: r["@parent"]["opened_at"] + dt.timedelta(minutes=g.int(1, 9000)))], per=("support_ticket", 1, 4)),
    Table("ticket_assignment", 0, [fk("support_ticket_id", "support_ticket"), col("_support", I, const(14)), fk("agent_id", "employee", match=("department_id", "_support"), declare=False),
                                   col("assigned_at", TS, lambda r, g: r["@parent"]["opened_at"] + dt.timedelta(minutes=g.int(1, 3000))), col("reason", S(20), ch(["Initial", "Escalation", "Rebalance", "Skill match"], [60, 15, 15, 10]))],
          per=("support_ticket", 1, 2)),
    Table("csat_response", 0, [fk("support_ticket_id", "support_ticket"), col("score", I, lambda r, g: g.pick([1, 2, 3, 4, 5], [6, 6, 13, 35, 40]) if not r["@parent"]["sla_breached"] else g.pick([1, 2, 3, 4, 5], [18, 15, 22, 28, 17])),
                               col("comment", S(300), words(4, 14), null=0.55), col("responded_at", TS, lambda r, g: (r["@parent"]["resolved_at"] or r["@parent"]["opened_at"]) + dt.timedelta(hours=g.int(1, 72)))],
          per=("support_ticket", lambda p, g: 1 if p["resolved_at"] and g.chance(0.42) else 0)),
    Table("kb_article", 420, [col("title", S(200), lambda r, g: g.pick(["How to", "Troubleshooting:", "FAQ:", "Release note:"]) + " " + g.faker("US").sentence(nb_words=6).rstrip(".")),
                              fk("ticket_category_id", "ticket_category"), fk("author_id", "employee", declare=False), col("published_on", D, when(dt.date(2020, 1, 1))),
                              col("views", I, lambda r, g: int(g.normal(900, 1500, 0, 40000))), col("is_public", B, yes(0.7))]),
    Table("kb_feedback", 7000, [fk("kb_article_id", "kb_article", skew=0.8), col("helpful", B, yes(0.74)), col("given_on", D, when(dt.date(2022, 1, 1)))]),
    Table("escalation", 2100, [fk("support_ticket_id", "support_ticket"), col("level", S(6), ch(["L2", "L3", "Mgmt"], [65, 25, 10])),
                               col("escalated_at", TS, lambda r, g: r["@support_ticket_id"]["opened_at"] + dt.timedelta(hours=g.int(1, 96))),
                               col("reason", S(40), ch(["SLA risk", "Customer VIP", "Technical complexity", "Repeat issue", "Legal threat"], [40, 20, 25, 12, 3]))]),
]
