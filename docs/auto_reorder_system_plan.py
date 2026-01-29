#!/usr/bin/env python3
"""Generate PDF for Auto-Reorder System Plan"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT, TA_CENTER

def create_pdf():
    doc = SimpleDocTemplate(
        "/Users/dell/FIRINGup/docs/Auto_Reorder_System_Plan.pdf",
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    styles = getSampleStyleSheet()

    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        spaceAfter=30,
        textColor=colors.HexColor('#667eea'),
        alignment=TA_CENTER
    )

    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#1f2937')
    )

    subheading_style = ParagraphStyle(
        'CustomSubheading',
        parent=styles['Heading3'],
        fontSize=12,
        spaceBefore=15,
        spaceAfter=8,
        textColor=colors.HexColor('#4b5563')
    )

    body_style = ParagraphStyle(
        'CustomBody',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8,
        leading=14
    )

    code_style = ParagraphStyle(
        'Code',
        parent=styles['Normal'],
        fontSize=9,
        fontName='Courier',
        backColor=colors.HexColor('#f3f4f6'),
        leftIndent=20,
        spaceBefore=5,
        spaceAfter=5,
        leading=12
    )

    formula_style = ParagraphStyle(
        'Formula',
        parent=styles['Normal'],
        fontSize=11,
        fontName='Courier-Bold',
        backColor=colors.HexColor('#e0e7ff'),
        leftIndent=20,
        rightIndent=20,
        spaceBefore=10,
        spaceAfter=10,
        alignment=TA_CENTER
    )

    layer_title_style = ParagraphStyle(
        'LayerTitle',
        parent=styles['Heading2'],
        fontSize=14,
        spaceBefore=20,
        spaceAfter=10,
        textColor=colors.HexColor('#667eea'),
        borderColor=colors.HexColor('#667eea'),
        borderWidth=1,
        borderPadding=5
    )

    story = []

    # Title
    story.append(Paragraph("FIRINGup Auto-Reorder System", title_style))
    story.append(Paragraph("Intelligent Inventory Replenishment Planning Document",
                          ParagraphStyle('Subtitle', parent=body_style, alignment=TA_CENTER, textColor=colors.gray)))
    story.append(Spacer(1, 30))

    # Core Algorithm Section
    story.append(Paragraph("Core Algorithm: When to Reorder", heading_style))
    story.append(Paragraph("Reorder Point = (Daily Consumption Rate x Lead Time) + Safety Stock", formula_style))
    story.append(Spacer(1, 10))

    # Section 1: Consumption Rate
    story.append(Paragraph("1. Consumption Rate Calculation", subheading_style))
    story.append(Paragraph("Two primary data sources to work with:", body_style))
    story.append(Paragraph("<b>Invoices (receiving):</b> Know when X quantity arrived", body_style))
    story.append(Paragraph("<b>Counts (depletion):</b> Know when quantity dropped", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("Calculation approaches (simple to complex):", body_style))
    story.append(Paragraph("<b>Simple:</b> (qty_received) / (days_until_next_receive)", body_style))
    story.append(Paragraph("<b>Better:</b> Track count-to-count deltas with dates, weighted toward recent behavior", body_style))
    story.append(Paragraph("<b>Best:</b> If recipe data + sales exist, predict consumption from sales (more accurate than counting)", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>Consider:</b> Weekly patterns (weekends busier?), seasonality, trends", body_style))

    # Section 2: Supplier Lead Time
    story.append(Paragraph("2. Supplier Lead Time (User Input)", subheading_style))
    story.append(Paragraph("For each supplier, capture:", body_style))

    lead_time_items = [
        "Lead time in business days (order to delivery)",
        "Order cutoff time (e.g., 'order by 2pm for next-day')",
        "Delivery days (some only deliver Tue/Thu)",
        "Minimum order value/quantity"
    ]
    for item in lead_time_items:
        story.append(Paragraph(f"&bull; {item}", body_style))

    # Section 3: Safety Stock
    story.append(Paragraph("3. Safety Stock", subheading_style))
    story.append(Paragraph("Buffer for consumption variability. Two approaches:", body_style))
    story.append(Paragraph("<b>Fixed:</b> Always keep X days extra (e.g., 2-3 days)", body_style))
    story.append(Paragraph("<b>Dynamic:</b> Based on consumption variance (if flour usage swings wildly, keep more buffer)", body_style))

    # Section 4: Other Factors
    story.append(Paragraph("4. Additional Factors to Consider", subheading_style))

    factors_data = [
        ['Factor', 'Why It Matters'],
        ['Perishability', "Don't over-order items with short shelf life"],
        ['Case breaks', "Round up to orderable units (can't order 0.3 cases)"],
        ['Volume discounts', 'Maybe order more if hitting a price break'],
        ['Supplier grouping', 'Batch items from same supplier into one order'],
        ['Minimum order values', 'Add lower-priority items to hit supplier minimums'],
        ['Price trends', 'Optional: flag if current price is unusually high/low vs history']
    ]

    factors_table = Table(factors_data, colWidths=[1.8*inch, 4.5*inch])
    factors_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e5e7eb')),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f9fafb')]),
        ('PADDING', (0, 0), (-1, -1), 8),
    ]))
    story.append(factors_table)

    # Section 5: Notification Flow
    story.append(Paragraph("5. The Notification Flow", subheading_style))

    flow_text = """
    1. System detects: Ingredient will hit reorder point in X days<br/>
    2. Groups with other items from same supplier needing reorder<br/>
    3. Calculates suggested quantities (consumption rate x target days of stock)<br/>
    4. Sends notification to admin:<br/>
    <br/>
    &nbsp;&nbsp;&nbsp;&nbsp;"Sysco Order Suggested"<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;"3 items projected to run low"<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;"Est. total: $847"<br/>
    &nbsp;&nbsp;&nbsp;&nbsp;[Review & Approve] [Dismiss] [Snooze 1 Day]<br/>
    <br/>
    5. On approve: Sends pre-formatted order email to supplier (or logs for manual ordering)
    """
    story.append(Paragraph(flow_text, body_style))

    # Section 6: Data Requirements
    story.append(Paragraph("6. Data Requirements to Add", subheading_style))

    story.append(Paragraph("<b>Per Supplier:</b>", body_style))
    supplier_items = [
        "Lead time (business days)",
        "Order cutoff time",
        "Delivery days",
        "Contact email/phone for orders",
        "Minimum order value"
    ]
    for item in supplier_items:
        story.append(Paragraph(f"&bull; {item}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Per Ingredient (optional overrides):</b>", body_style))
    ingredient_items = [
        "Par level (manual override of algorithm)",
        "Reorder enabled (yes/no toggle)",
        "Preferred order quantity"
    ]
    for item in ingredient_items:
        story.append(Paragraph(f"&bull; {item}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>System Settings:</b>", body_style))
    system_items = [
        "Default safety stock days",
        "How far ahead to look (notify X days before reorder point)",
        "Notification preferences (email, SMS, both)"
    ]
    for item in system_items:
        story.append(Paragraph(f"&bull; {item}", body_style))

    # Section 7: Implementation Phases
    story.append(Paragraph("7. Implementation Phases", subheading_style))

    story.append(Paragraph("<b>Phase 1 - Practical MVP:</b>", body_style))
    phase1 = [
        "Simple moving average consumption",
        "Fixed lead times per supplier",
        "Fixed safety stock (e.g., 3 days)",
        "Email notification with order summary",
        "Manual approval triggers email to supplier"
    ]
    for item in phase1:
        story.append(Paragraph(f"&bull; {item}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Phase 2 - Smarter:</b>", body_style))
    phase2 = [
        "Weighted consumption (recent weeks matter more)",
        "Dynamic safety stock based on variance",
        "Supplier order batching with minimum value logic",
        "Recipe-based consumption prediction"
    ]
    for item in phase2:
        story.append(Paragraph(f"&bull; {item}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Phase 3 - Advanced:</b>", body_style))
    phase3 = [
        "Day-of-week consumption patterns",
        "Seasonal adjustments",
        "Price optimization suggestions",
        "Machine learning predictions"
    ]
    for item in phase3:
        story.append(Paragraph(f"&bull; {item}", body_style))

    # Modeled vs Actual Section
    story.append(PageBreak())
    story.append(Paragraph("Modeled vs Actual Inventory Tracking", heading_style))

    story.append(Paragraph("<b>Modeled (Theoretical) Inventory:</b>", body_style))
    story.append(Paragraph("&bull; Sales x Recipe ingredients = what <i>should</i> have been used", body_style))
    story.append(Paragraph("&bull; Updates in real-time with every sale", body_style))
    story.append(Paragraph("&bull; Great for continuous consumption rate tracking", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Actual Inventory:</b>", body_style))
    story.append(Paragraph("&bull; Physical counts = what's <i>really</i> there", body_style))
    story.append(Paragraph("&bull; Ground truth, but only at count moments", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>The Delta Tells a Story:</b>", body_style))
    story.append(Paragraph("Modeled says: 50 lbs flour remaining", code_style))
    story.append(Paragraph("Actual count: 42 lbs flour remaining", code_style))
    story.append(Paragraph("Variance: -8 lbs (16% loss)", code_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("This variance captures: waste/spillage, portion control drift, recipe inaccuracies, theft, recording errors", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>For Auto-Reorder:</b>", body_style))
    story.append(Paragraph("1. <b>Consumption Rate:</b> Use modeled (sales-driven) for predictions - it's real-time and granular", body_style))
    story.append(Paragraph("2. <b>Calibration Factor:</b> Apply correction based on historical modeled-vs-actual variance", body_style))
    story.append(Paragraph("3. <b>Dynamic Safety Stock:</b> High variance items need bigger buffers", body_style))
    story.append(Paragraph("4. <b>Reorder Trigger:</b> Projected Depletion = Current Actual + (Daily Modeled Consumption x Variance Factor)", body_style))

    # NEW SECTION: System Architecture Layers
    story.append(PageBreak())
    story.append(Paragraph("System Architecture: The Seven Layers", title_style))
    story.append(Spacer(1, 20))

    # Layer 1: Data Foundation
    story.append(Paragraph("Layer 1: Data Foundation", layer_title_style))
    story.append(Paragraph("<b>What exists (already in DB):</b>", body_style))
    existing_data = [
        "Invoices - receiving dates, quantities, costs, supplier",
        "Inventory counts - actual quantities at points in time",
        "Sales transactions - what was sold, when",
        "Recipes - ingredient requirements per product",
        "Suppliers - contact info, terms"
    ]
    for item in existing_data:
        story.append(Paragraph(f"&bull; {item}", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Database additions needed:</b>", body_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>suppliers table additions:</b>", body_style))
    story.append(Paragraph("lead_time_days (integer)", code_style))
    story.append(Paragraph("order_cutoff_time (e.g., '14:00')", code_style))
    story.append(Paragraph("delivery_days (e.g., 'tue,thu,sat')", code_style))
    story.append(Paragraph("order_email", code_style))
    story.append(Paragraph("minimum_order_value", code_style))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>ingredients table additions:</b>", body_style))
    story.append(Paragraph("reorder_enabled (boolean, default true)", code_style))
    story.append(Paragraph("par_level_override (nullable - manual override)", code_style))
    story.append(Paragraph("safety_stock_days (nullable - per-item override)", code_style))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>new table: reorder_settings</b>", body_style))
    story.append(Paragraph("default_safety_stock_days", code_style))
    story.append(Paragraph("lookahead_days (how far ahead to warn)", code_style))
    story.append(Paragraph("notification_email", code_style))
    story.append(Paragraph("notification_phone", code_style))

    # Layer 2: Consumption Engine
    story.append(Paragraph("Layer 2: Consumption Engine", layer_title_style))
    story.append(Paragraph("Runs periodically (or on-demand) to calculate consumption metrics per ingredient:", body_style))
    story.append(Spacer(1, 5))

    story.append(Paragraph("<b>1. MODELED CONSUMPTION (from sales)</b>", body_style))
    story.append(Paragraph("&bull; Query recent sales (e.g., last 30 days)", body_style))
    story.append(Paragraph("&bull; Join to recipes -> sum ingredient usage", body_style))
    story.append(Paragraph("&bull; Calculate: daily_modeled_consumption = total_used / days", body_style))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>2. ACTUAL CONSUMPTION (from counts)</b>", body_style))
    story.append(Paragraph("&bull; Query count history + invoice receipts", body_style))
    story.append(Paragraph("&bull; Calculate: actual_depleted = (starting + received - ending)", body_style))
    story.append(Paragraph("&bull; Calculate: daily_actual_consumption = actual_depleted / days", body_style))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>3. VARIANCE FACTOR</b>", body_style))
    story.append(Paragraph("&bull; variance = actual / modeled (e.g., 1.15 means 15% more actual)", body_style))
    story.append(Paragraph("&bull; Store rolling average variance", body_style))

    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>4. ADJUSTED CONSUMPTION RATE</b>", body_style))
    story.append(Paragraph("&bull; adjusted_daily = daily_modeled x variance_factor", body_style))
    story.append(Paragraph("&bull; This is your best predictor", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Output:</b> ingredient_consumption_metrics table", body_style))
    output_fields = ["ingredient_id", "daily_modeled_rate", "daily_actual_rate", "variance_factor",
                     "confidence_score (based on data quality/quantity)", "last_calculated"]
    for field in output_fields:
        story.append(Paragraph(f"&bull; {field}", body_style))

    # Layer 3: Reorder Point Calculator
    story.append(Paragraph("Layer 3: Reorder Point Calculator", layer_title_style))
    story.append(Paragraph("For each ingredient, determine when to reorder:", body_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("current_stock = latest count (or modeled current)", code_style))
    story.append(Paragraph("adjusted_daily_consumption = from Layer 2", code_style))
    story.append(Paragraph("lead_time = supplier.lead_time_days", code_style))
    story.append(Paragraph("safety_stock = ingredient.safety_stock_days OR settings.default", code_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("days_of_stock = current_stock / adjusted_daily_consumption", code_style))
    story.append(Paragraph("reorder_point_days = lead_time + safety_stock", code_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("<b>TRIGGER when:</b> days_of_stock &lt;= reorder_point_days + lookahead_days", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Output:</b> reorder_alerts table", body_style))
    alert_fields = ["ingredient_id", "current_stock", "days_remaining",
                    "suggested_order_qty (e.g., 2 weeks of stock)",
                    "urgency (critical/soon/upcoming)", "supplier_id", "created_at",
                    "status (pending/notified/approved/dismissed)"]
    for field in alert_fields:
        story.append(Paragraph(f"&bull; {field}", body_style))

    # Layer 4: Order Aggregator
    story.append(Paragraph("Layer 4: Order Aggregator", layer_title_style))
    story.append(Paragraph("Groups alerts into actionable supplier orders:", body_style))
    story.append(Spacer(1, 5))
    story.append(Paragraph("For each supplier with pending alerts:", body_style))
    story.append(Paragraph("1. Collect all ingredients needing reorder", body_style))
    story.append(Paragraph("2. Calculate quantities (round to case sizes)", body_style))
    story.append(Paragraph("3. Check against minimum order value", body_style))
    story.append(Paragraph("&nbsp;&nbsp;&nbsp;&nbsp;- If under minimum: flag lower-priority items to add", body_style))
    story.append(Paragraph("4. Calculate estimated total cost", body_style))
    story.append(Paragraph("5. Determine optimal order date (based on delivery days)", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Output:</b> draft_order", body_style))
    order_fields = ["supplier_id", "order_date", "delivery_date (estimated)",
                    "line_items: [{ingredient, qty, unit, est_cost}]",
                    "total_estimated", "status: draft"]
    for field in order_fields:
        story.append(Paragraph(f"&bull; {field}", body_style))

    # Layer 5: Notification Service
    story.append(PageBreak())
    story.append(Paragraph("Layer 5: Notification Service", layer_title_style))
    story.append(Paragraph("Sends alerts to admins when draft_order created or updated:", body_style))
    story.append(Spacer(1, 10))

    notification_example = """
    <b>Example Notification:</b><br/><br/>
    &nbsp;&nbsp;Sysco Order Recommended<br/>
    &nbsp;&nbsp;4 items need reordering<br/>
    &nbsp;&nbsp;Est. total: $1,247<br/>
    &nbsp;&nbsp;Order by: Tomorrow 2pm for Thu delivery<br/><br/>
    &nbsp;&nbsp;- Flour (50lb) x 2 cases - $89<br/>
    &nbsp;&nbsp;- Tomatoes (case) x 3 - $156<br/>
    &nbsp;&nbsp;- Cheese (block) x 5 - $423<br/>
    &nbsp;&nbsp;- Olive Oil (gal) x 2 - $67<br/><br/>
    &nbsp;&nbsp;[Approve] [Modify] [Snooze 1 Day] [Dismiss]
    """
    story.append(Paragraph(notification_example, body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Delivery channels:</b>", body_style))
    story.append(Paragraph("&bull; Email (with action links)", body_style))
    story.append(Paragraph("&bull; SMS (short version + link)", body_style))
    story.append(Paragraph("&bull; In-app notification", body_style))

    # Layer 6: Action Handler
    story.append(Paragraph("Layer 6: Action Handler", layer_title_style))
    story.append(Paragraph("Processes admin responses:", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>On APPROVE:</b>", body_style))
    story.append(Paragraph("1. Generate formal order (PDF or email body)", body_style))
    story.append(Paragraph("2. Send to supplier.order_email", body_style))
    story.append(Paragraph("3. Log order in purchase_orders table", body_style))
    story.append(Paragraph("4. Update reorder_alerts status", body_style))
    story.append(Paragraph("5. Set expected_delivery_date", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>On MODIFY:</b>", body_style))
    story.append(Paragraph("&bull; Open order editor UI", body_style))
    story.append(Paragraph("&bull; Allow qty changes, item removal", body_style))
    story.append(Paragraph("&bull; Re-approve when ready", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>On SNOOZE:</b>", body_style))
    story.append(Paragraph("&bull; Set alert.snooze_until = now + 1 day", body_style))
    story.append(Paragraph("&bull; Will re-notify tomorrow", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>On DISMISS:</b>", body_style))
    story.append(Paragraph("&bull; Mark alert dismissed", body_style))
    story.append(Paragraph("&bull; Optional: 'Don't suggest for X days'", body_style))

    # Layer 7: Learning Loop
    story.append(Paragraph("Layer 7: Learning Loop (Phase 2+)", layer_title_style))
    story.append(Paragraph("Improves predictions over time:", body_style))
    story.append(Spacer(1, 10))

    story.append(Paragraph("<b>After each count:</b>", body_style))
    story.append(Paragraph("1. Compare predicted vs actual", body_style))
    story.append(Paragraph("2. Adjust variance_factor", body_style))
    story.append(Paragraph("3. Flag recipes that may be wrong", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>After each delivery:</b>", body_style))
    story.append(Paragraph("1. Record actual lead time", body_style))
    story.append(Paragraph("2. Update supplier.lead_time_days (rolling avg)", body_style))

    story.append(Spacer(1, 10))
    story.append(Paragraph("<b>Weekly:</b>", body_style))
    story.append(Paragraph("1. Recalculate consumption patterns", body_style))
    story.append(Paragraph("2. Detect trend changes", body_style))
    story.append(Paragraph("3. Flag anomalies for review", body_style))

    # Visual Architecture Diagram
    story.append(PageBreak())
    story.append(Paragraph("Visual Architecture Overview", heading_style))
    story.append(Spacer(1, 20))

    # Create a visual table representing the architecture
    arch_data = [
        ['ADMIN DASHBOARD'],
        ['Notifications | Pending Orders | Settings'],
        [''],
        ['NOTIFICATION SERVICE'],
        ['Email / SMS / In-App Alerts'],
        [''],
        ['ORDER AGGREGATOR'],
        ['Group by supplier, check minimums, schedule'],
        [''],
        ['REORDER POINT CALCULATOR'],
        ['When to order? How much? How urgent?'],
        [''],
        ['CONSUMPTION ENGINE'],
        ['Modeled (sales x recipes) + Actual (counts) + Variance'],
        [''],
        ['DATA FOUNDATION'],
        ['Invoices | Counts | Sales | Recipes | Suppliers'],
    ]

    arch_table = Table(arch_data, colWidths=[6*inch])
    arch_table.setStyle(TableStyle([
        # Layer headers (odd rows starting from 0)
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#667eea')),
        ('BACKGROUND', (0, 3), (-1, 3), colors.HexColor('#764ba2')),
        ('BACKGROUND', (0, 6), (-1, 6), colors.HexColor('#667eea')),
        ('BACKGROUND', (0, 9), (-1, 9), colors.HexColor('#764ba2')),
        ('BACKGROUND', (0, 12), (-1, 12), colors.HexColor('#667eea')),
        ('BACKGROUND', (0, 15), (-1, 15), colors.HexColor('#764ba2')),
        # Layer descriptions
        ('BACKGROUND', (0, 1), (-1, 1), colors.HexColor('#e0e7ff')),
        ('BACKGROUND', (0, 4), (-1, 4), colors.HexColor('#ede9fe')),
        ('BACKGROUND', (0, 7), (-1, 7), colors.HexColor('#e0e7ff')),
        ('BACKGROUND', (0, 10), (-1, 10), colors.HexColor('#ede9fe')),
        ('BACKGROUND', (0, 13), (-1, 13), colors.HexColor('#e0e7ff')),
        ('BACKGROUND', (0, 16), (-1, 16), colors.HexColor('#ede9fe')),
        # Text colors
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('TEXTCOLOR', (0, 3), (-1, 3), colors.white),
        ('TEXTCOLOR', (0, 6), (-1, 6), colors.white),
        ('TEXTCOLOR', (0, 9), (-1, 9), colors.white),
        ('TEXTCOLOR', (0, 12), (-1, 12), colors.white),
        ('TEXTCOLOR', (0, 15), (-1, 15), colors.white),
        # Formatting
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTNAME', (0, 3), (-1, 3), 'Helvetica-Bold'),
        ('FONTNAME', (0, 6), (-1, 6), 'Helvetica-Bold'),
        ('FONTNAME', (0, 9), (-1, 9), 'Helvetica-Bold'),
        ('FONTNAME', (0, 12), (-1, 12), 'Helvetica-Bold'),
        ('FONTNAME', (0, 15), (-1, 15), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 10),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('PADDING', (0, 0), (-1, -1), 12),
        # Spacer rows
        ('BACKGROUND', (0, 2), (-1, 2), colors.white),
        ('BACKGROUND', (0, 5), (-1, 5), colors.white),
        ('BACKGROUND', (0, 8), (-1, 8), colors.white),
        ('BACKGROUND', (0, 11), (-1, 11), colors.white),
        ('BACKGROUND', (0, 14), (-1, 14), colors.white),
    ]))
    story.append(arch_table)

    # Key Questions
    story.append(Spacer(1, 30))
    story.append(Paragraph("Key Questions to Resolve", heading_style))
    questions = [
        "What communication method preferred for supplier orders (email, portal, phone)?",
        "Should the system auto-send orders or always require human approval?",
        "What level of safety stock is acceptable (cost of overstock vs risk of stockout)?",
        "Are there seasonal patterns that need to be accounted for?",
        "Which suppliers have API/portal ordering vs email-only?"
    ]
    for i, q in enumerate(questions, 1):
        story.append(Paragraph(f"{i}. {q}", body_style))

    # Build PDF
    doc.build(story)
    print("PDF created: /Users/dell/FIRINGup/docs/Auto_Reorder_System_Plan.pdf")

if __name__ == "__main__":
    create_pdf()
