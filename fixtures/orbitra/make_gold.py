"""Write fixtures/orbitra/gold.jsonl: business questions with a reference query each (PostgreSQL).

    uv run python fixtures/orbitra/make_gold.py

Questions name explicit periods (FY25-26 is April 2025 to March 2026) so answers do not drift with
today's date. `tables` is derived from the SQL. `note` records a known ambiguity the bot may fairly ask
about; the reference query takes the reading written in the question. tools/orbitra_check.py runs every
query through ReBo's guard and the database, no model.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "src"))

from rebo.safety import tables_in  # noqa: E402

FY = "'2025-04-01' AND '2026-03-31'"
CASES = [
    # ---- people ----
    ("or-01", "How many employees with status Active are there in each department?",
     "SELECT d.dept_name, COUNT(*) FROM employee e JOIN department d ON d.department_id = e.department_id WHERE e.status = 'Active' GROUP BY d.dept_name",
     None),
    ("or-02", "Headcount by office location for people still employed (no exit date).",
     "SELECT o.site_name, COUNT(*) FROM employee e JOIN office_location o ON o.office_location_id = e.office_location_id WHERE e.exit_date IS NULL GROUP BY o.site_name",
     None),
    ("or-03", "Who left the company in 2025, and what reason did they give in the exit interview?",
     "SELECT e.first_name, e.last_name, e.exit_date, x.reason FROM employee e LEFT JOIN exit_interview x ON x.employee_id = e.employee_id "
     "WHERE e.exit_date BETWEEN '2025-01-01' AND '2025-12-31'", "people may have more than one exit interview row"),
    ("or-04", "Total net pay paid by the Indian entity per month in FY25-26.",
     f"SELECT r.pay_month, SUM(p.net_pay) FROM payslip p JOIN payroll_run r ON r.payroll_run_id = p.payroll_run_id JOIN legal_entity l ON l.legal_entity_id = r.legal_entity_id "
     f"WHERE l.entity_code = 'OES-IN' AND r.pay_month BETWEEN {FY} GROUP BY r.pay_month", None),
    ("or-05", "Approved leave days taken in 2025, by leave type.",
     "SELECT t.name, SUM(l.days) FROM leave_request l JOIN leave_type t ON t.leave_type_id = l.leave_type_id WHERE l.status = 'Approved' "
     "AND l.from_date BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY t.name", None),
    ("or-06", "Completion rate of each mandatory training course (completed enrolments over all enrolments).",
     "SELECT c.course_title, ROUND(100.0 * SUM(CASE WHEN t.status = 'Completed' THEN 1 ELSE 0 END) / COUNT(*), 1) FROM training_enrollment t "
     "JOIN training_course c ON c.training_course_id = t.training_course_id WHERE c.is_mandatory GROUP BY c.course_title", None),
    ("or-07", "Average performance rating per department for the FY24-25 annual cycle.",
     "SELECT d.dept_name, ROUND(AVG(r.rating), 2) FROM performance_review r JOIN performance_cycle c ON c.performance_cycle_id = r.performance_cycle_id "
     "JOIN employee e ON e.employee_id = r.employee_id JOIN department d ON d.department_id = e.department_id WHERE c.cycle_name = 'FY24-25 Annual' GROUP BY d.dept_name",
     "department today, not at the time of the review"),
    # ---- sales and customers ----
    ("or-08", "Order value in rupees per month in FY25-26, leaving out cancelled orders.",
     f"SELECT to_char(order_date, 'YYYY-MM'), SUM(total_amount_inr) FROM sales_order WHERE order_date BETWEEN {FY} AND status <> 'Cancelled' GROUP BY 1",
     "total_amount_inr uses a fixed rate, not fx_rate"),
    ("or-09", "Top 10 products by units ordered in FY25-26 (not counting cancelled orders).",
     f"SELECT p.product_name, SUM(l.quantity) FROM sales_order_line l JOIN sales_order o ON o.sales_order_id = l.sales_order_id JOIN product p ON p.product_id = l.product_id "
     f"WHERE o.order_date BETWEEN {FY} AND o.status <> 'Cancelled' GROUP BY p.product_name ORDER BY 2 DESC LIMIT 10", None),
    ("or-10", "List our customers with a site in Karnataka, with their GSTIN.",
     "SELECT DISTINCT a.account_name, a.gstin FROM customer_account a JOIN customer_site s ON s.customer_account_id = a.customer_account_id WHERE s.state_name = 'Karnataka'",
     "GSTIN state code 29 gives the same list"),
    ("or-11", "Number of customer accounts per country and segment.",
     "SELECT a.country_code, s.name, COUNT(*) FROM customer_account a JOIN customer_segment s ON s.customer_segment_id = a.customer_segment_id GROUP BY a.country_code, s.name",
     None),
    ("or-12", "Win rate of opportunities closed in FY25-26, by the customer's sales territory.",
     f"SELECT t.name, ROUND(100.0 * SUM(CASE WHEN st.name = 'Closed won' THEN 1 ELSE 0 END) / COUNT(*), 1) FROM opportunity o "
     f"JOIN opportunity_stage st ON st.opportunity_stage_id = o.opportunity_stage_id JOIN customer_account a ON a.customer_account_id = o.customer_account_id "
     f"JOIN sales_territory t ON t.sales_territory_id = a.sales_territory_id WHERE st.name IN ('Closed won', 'Closed lost') AND o.closed_on BETWEEN {FY} GROUP BY t.name",
     "the rep's territory is the other reading"),
    ("or-13", "Which competitors did we lose the most deals to in FY25-26?",
     f"SELECT c.name, COUNT(DISTINCT o.opportunity_id) FROM opportunity o JOIN opportunity_stage st ON st.opportunity_stage_id = o.opportunity_stage_id "
     f"JOIN opportunity_competitor oc ON oc.opportunity_id = o.opportunity_id JOIN competitor c ON c.competitor_id = oc.competitor_id "
     f"WHERE st.name = 'Closed lost' AND o.closed_on BETWEEN {FY} GROUP BY c.name ORDER BY 2 DESC", None),
    ("or-14", "Total monthly recurring revenue of active subscriptions billed in INR, per plan.",
     "SELECT p.plan_name, p.billing_period, SUM(s.mrr) FROM subscription s JOIN subscription_plan p ON p.subscription_plan_id = s.subscription_plan_id "
     "WHERE s.status = 'Active' AND s.currency = 'INR' GROUP BY p.plan_name, p.billing_period", None),
    ("or-15", "Subscriptions cancelled in 2025, by churn reason.",
     "SELECT r.name, COUNT(*) FROM subscription s JOIN churn_reason r ON r.churn_reason_id = s.churn_reason_id WHERE s.cancelled_on BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY r.name",
     None),
    ("or-16", "Sales reps ranked by order value in rupees in FY25-26 (excluding cancelled orders), top 15.",
     f"SELECT e.first_name, e.last_name, SUM(o.total_amount_inr) FROM sales_order o JOIN sales_rep r ON r.sales_rep_id = o.sales_rep_id "
     f"JOIN employee e ON e.employee_id = r.employee_id WHERE o.order_date BETWEEN {FY} AND o.status <> 'Cancelled' GROUP BY e.first_name, e.last_name ORDER BY 3 DESC LIMIT 15",
     None),
    # ---- receivables ----
    ("or-17", "How many customer invoices are overdue, and what is their total in rupees?",
     "SELECT COUNT(*), SUM(total_amount_inr) FROM ar_invoice WHERE status = 'Overdue'", "partially paid invoices past due are the other reading"),
    ("or-18", "Top 10 customers by outstanding balance on unpaid and partly paid invoices, in rupees.",
     "SELECT a.account_name, SUM((i.total_amount - COALESCE(p.paid, 0)) * i.total_amount_inr / NULLIF(i.total_amount, 0)) FROM ar_invoice i "
     "JOIN customer_account a ON a.customer_account_id = i.customer_account_id LEFT JOIN (SELECT ar_invoice_id, SUM(amount) AS paid FROM ar_receipt GROUP BY ar_invoice_id) p "
     "ON p.ar_invoice_id = i.ar_invoice_id WHERE i.status <> 'Paid' GROUP BY a.account_name ORDER BY 2 DESC LIMIT 10", None),
    ("or-19", "On average, how many days after the due date do customers pay, by customer segment?",
     "SELECT s.name, ROUND(AVG(r.receipt_date - i.due_date), 1) FROM ar_receipt r JOIN ar_invoice i ON i.ar_invoice_id = r.ar_invoice_id "
     "JOIN customer_account a ON a.customer_account_id = i.customer_account_id JOIN customer_segment s ON s.customer_segment_id = a.customer_segment_id GROUP BY s.name",
     None),
    ("or-20", "Total invoiced in GBP to UK customers in calendar 2025.",
     "SELECT a.account_name, SUM(i.total_amount) FROM ar_invoice i JOIN customer_account a ON a.customer_account_id = i.customer_account_id "
     "WHERE a.country_code = 'GB' AND i.currency = 'GBP' AND i.invoice_date BETWEEN '2025-01-01' AND '2025-12-31' GROUP BY a.account_name", None),
    ("or-21", "Credit notes issued in FY25-26 by reason, with their count.",
     f"SELECT reason, COUNT(*) FROM credit_note WHERE issued_on BETWEEN {FY} GROUP BY reason", None),
    # ---- procurement, finance ----
    ("or-22", "Suppliers with overdue invoices we have not paid, and the amount due in their currency.",
     "SELECT s.supplier_name, i.currency, SUM(i.amount) FROM ap_invoice i JOIN supplier s ON s.supplier_id = i.supplier_id WHERE i.status = 'Overdue' GROUP BY s.supplier_name, i.currency",
     None),
    ("or-23", "Value of rupee purchase orders placed in FY25-26 by supplier category, excluding cancelled ones.",
     f"SELECT c.name, SUM(po.total_amount) FROM purchase_order po JOIN supplier s ON s.supplier_id = po.supplier_id JOIN supplier_category c ON c.supplier_category_id = s.supplier_category_id "
     f"WHERE po.currency = 'INR' AND po.status <> 'Cancelled' AND po.order_date BETWEEN {FY} GROUP BY c.name", None),
    ("or-24", "Purchase requisitions still pending approval, by department.",
     "SELECT d.dept_name, COUNT(*) FROM purchase_requisition r JOIN department d ON d.department_id = r.department_id WHERE r.status = 'Pending approval' GROUP BY d.dept_name", None),
    ("or-25", "GST paid in cash per registration (GSTIN) in FY25-26, from the GSTR-3B returns.",
     "SELECT gstin, SUM(cash_paid_inr) FROM gst_return WHERE return_type = 'GSTR-3B' AND tax_period BETWEEN '2025-04' AND '2026-03' GROUP BY gstin", None),
    ("or-26", "Expense claims reimbursed in FY25-26, total per expense category in rupees (INR claims only).",
     f"SELECT l.category, SUM(l.amount) FROM expense_line l JOIN expense_claim c ON c.expense_claim_id = l.expense_claim_id WHERE c.status = 'Reimbursed' AND c.currency = 'INR' "
     f"AND c.claim_date BETWEEN {FY} GROUP BY l.category", None),
    ("or-27", "Net book cost of fixed assets still in use, by asset category (cost only, before depreciation).",
     "SELECT c.name, SUM(f.cost_inr) FROM fixed_asset f JOIN asset_category c ON c.asset_category_id = f.asset_category_id WHERE f.status = 'In use' GROUP BY c.name",
     "net of depreciation is the other reading"),
    # ---- operations ----
    ("or-28", "Machine downtime hours per work center in FY25-26.",
     "SELECT w.wc_name, ROUND(SUM(d.duration_min) / 60.0, 1) FROM machine_downtime d JOIN machine m ON m.machine_id = d.machine_id JOIN work_center w ON w.work_center_id = m.work_center_id "
     "WHERE d.started_at BETWEEN '2025-04-01' AND '2026-04-01' GROUP BY w.wc_name", None),
    ("or-29", "Scrap rate per product category for work orders completed in 2026 (scrap over completed quantity).",
     "SELECT c.category_name, ROUND(100.0 * SUM(w.scrap_qty) / NULLIF(SUM(w.completed_qty), 0), 2) FROM work_order w JOIN product p ON p.product_id = w.product_id "
     "JOIN product_category c ON c.product_category_id = p.product_category_id WHERE w.status IN ('Completed', 'Closed') AND w.actual_end BETWEEN '2026-01-01' AND '2026-12-31' GROUP BY c.category_name",
     None),
    ("or-30", "Most frequent defect types found in quality inspections during 2026.",
     "SELECT t.name, COUNT(*) FROM defect d JOIN defect_type t ON t.defect_type_id = d.defect_type_id JOIN quality_inspection q ON q.quality_inspection_id = d.quality_inspection_id "
     "WHERE q.inspected_on >= '2026-01-01' GROUP BY t.name ORDER BY 2 DESC", None),
    ("or-31", "How many stock positions are below their reorder level (on hand minus reserved), per warehouse?",
     "SELECT w.warehouse_name, COUNT(*) FROM stock_balance b JOIN warehouse w ON w.warehouse_id = b.warehouse_id WHERE b.on_hand_qty - b.reserved_qty < b.reorder_level GROUP BY w.warehouse_name",
     None),
    ("or-32", "Freight cost per carrier for shipments delivered in 2026, with how many arrived after the expected date.",
     "SELECT c.carrier_name, SUM(s.freight_cost_inr), SUM(CASE WHEN s.delivered_on > s.expected_delivery THEN 1 ELSE 0 END) FROM shipment s JOIN carrier c ON c.carrier_id = s.carrier_id "
     "WHERE s.delivered_on BETWEEN '2026-01-01' AND '2026-12-31' GROUP BY c.carrier_name", None),
    ("or-33", "Customer returns by reason in FY25-26.",
     f"SELECT r.name, COUNT(*) FROM return_authorization a JOIN return_reason r ON r.return_reason_id = a.return_reason_id WHERE a.requested_on BETWEEN {FY} GROUP BY r.name", None),
    # ---- devices, service, support ----
    ("or-34", "The 20 customers with the most offline devices right now.",
     "SELECT a.account_name, COUNT(*) FROM device d JOIN customer_site s ON s.customer_site_id = d.customer_site_id "
     "JOIN customer_account a ON a.customer_account_id = s.customer_account_id WHERE d.status = 'Offline' GROUP BY a.account_name ORDER BY 2 DESC LIMIT 20", None),
    ("or-35", "EV charging sessions per month in 2026, with the energy delivered in kWh.",
     "SELECT to_char(started_at, 'YYYY-MM'), COUNT(*), SUM(energy_kwh) FROM charging_session WHERE started_at >= '2026-01-01' AND started_at < '2027-01-01' GROUP BY 1", None),
    ("or-36", "Which vehicle models charge at our chargers most often?",
     "SELECT vehicle_model, COUNT(*) FROM charging_session GROUP BY vehicle_model ORDER BY 2 DESC", None),
    ("or-37", "Support tickets opened in 2025 that breached their SLA, by priority.",
     "SELECT p.name, COUNT(*) FROM support_ticket t JOIN ticket_priority p ON p.ticket_priority_id = t.ticket_priority_id WHERE t.sla_breached "
     "AND t.opened_at >= '2025-01-01' AND t.opened_at < '2026-01-01' GROUP BY p.name", None),
    ("or-38", "Average CSAT score per support channel.",
     "SELECT c.name, ROUND(AVG(r.score), 2) FROM csat_response r JOIN support_ticket t ON t.support_ticket_id = r.support_ticket_id "
     "JOIN support_channel c ON c.support_channel_id = t.support_channel_id GROUP BY c.name", None),
    ("or-39", "Average hours to close service requests in 2025, by problem.",
     "SELECT problem, ROUND(AVG(EXTRACT(EPOCH FROM closed_at - reported_at) / 3600), 1) FROM service_request WHERE closed_at IS NOT NULL "
     "AND reported_at >= '2025-01-01' AND reported_at < '2026-01-01' GROUP BY problem", None),
    ("or-40", "Technicians with the most service visits in September 2026.",
     "SELECT e.first_name, e.last_name, COUNT(*) FROM service_visit v JOIN technician t ON t.technician_id = v.technician_id JOIN employee e ON e.employee_id = t.employee_id "
     "WHERE v.visit_date BETWEEN '2026-09-01' AND '2026-09-30' GROUP BY e.first_name, e.last_name ORDER BY 3 DESC", None),
    ("or-41", "Warranty claims approved and rejected, per product category.",
     "SELECT c.category_name, w.decision, COUNT(*) FROM warranty_claim w JOIN device d ON d.device_id = w.device_id JOIN product p ON p.product_id = d.product_id "
     "JOIN product_category c ON c.product_category_id = p.product_category_id WHERE w.decision IN ('Approved', 'Rejected') GROUP BY c.category_name, w.decision", None),
    # ---- projects, marketing, ESG ----
    ("or-42", "Projects whose health is Red, with the project manager and the customer.",
     "SELECT p.project_name, e.first_name, e.last_name, a.account_name FROM project p JOIN employee e ON e.employee_id = p.project_manager_id "
     "LEFT JOIN customer_account a ON a.customer_account_id = p.customer_account_id WHERE p.health = 'Red'", None),
    ("or-43", "The 20 projects with the most approved billable hours in September 2026.",
     "SELECT p.project_name, SUM(t.hours) FROM timesheet_entry t JOIN project p ON p.project_id = t.project_id WHERE t.is_billable AND t.approval_status = 'Approved' "
     "AND t.work_date BETWEEN '2026-09-01' AND '2026-09-30' GROUP BY p.project_name ORDER BY 2 DESC LIMIT 20", None),
    ("or-44", "Email open and click rates by campaign channel for emails sent in 2025.",
     "SELECT ch.name, ROUND(100.0 * AVG(CASE WHEN s.opened THEN 1 ELSE 0 END), 1), ROUND(100.0 * AVG(CASE WHEN s.clicked THEN 1 ELSE 0 END), 1) FROM email_send s "
     "JOIN campaign c ON c.campaign_id = s.campaign_id JOIN campaign_channel ch ON ch.campaign_channel_id = c.campaign_channel_id "
     "WHERE s.sent_at >= '2025-01-01' AND s.sent_at < '2026-01-01' GROUP BY ch.name", None),
    ("or-45", "Website sessions in 2026 that came from LinkedIn, by visitor country.",
     "SELECT country_code, COUNT(*) FROM web_session WHERE source = 'LinkedIn' AND started_at >= '2026-01-01' GROUP BY country_code", None),
    ("or-46", "Grid and solar electricity used at our plants in FY25-26, per plant.",
     f"SELECT o.site_name, SUM(e.grid_kwh), SUM(e.solar_kwh) FROM energy_consumption e JOIN office_location o ON o.office_location_id = e.office_location_id "
     f"WHERE o.site_type = 'plant' AND e.month BETWEEN {FY} GROUP BY o.site_name", None),
    ("or-47", "CSR spend by Schedule VII area in FY24-25.",
     "SELECT schedule_vii_area, SUM(spent_inr) FROM csr_activity WHERE activity_date BETWEEN '2024-04-01' AND '2025-03-31' GROUP BY schedule_vii_area", None),
    ("or-48", "Open audit findings rated High or Critical, with their owner and target date.",
     "SELECT a.audit_name, f.finding, f.risk_rating, e.first_name, e.last_name, f.target_date FROM audit_finding f JOIN internal_audit a ON a.internal_audit_id = f.internal_audit_id "
     "JOIN employee e ON e.employee_id = f.owner_id WHERE f.closed_on IS NULL AND f.risk_rating IN ('High', 'Critical')", None),
]


def main() -> None:
    out = HERE / "gold.jsonl"
    lines = []
    for cid, q, sql, note in CASES:
        row = {"id": cid, "question": q, "gold_sql": sql, "min_rows": 1, "tables": sorted(tables_in(sql, "postgres"))}
        if note:
            row["note"] = note
        lines.append(json.dumps(row, ensure_ascii=False))
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(lines)} cases -> {out}")


if __name__ == "__main__":
    main()
