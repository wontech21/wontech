#!/usr/bin/env python3
"""
Generate Voice AI Phone Ordering System PDF
Matches the style of Auto_Reorder_System_Plan.pdf
"""

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
    Preformatted, PageBreak, ListFlowable, ListItem
)
from reportlab.lib.enums import TA_CENTER, TA_LEFT
import os

# Colors matching the existing PDF
HEADER_BLUE = HexColor('#4A6FA5')
SECTION_BLUE = HexColor('#6B8DD6')
LAYER_PURPLE = HexColor('#7C5CBF')
TABLE_HEADER = HexColor('#5B7BC0')
LIGHT_GRAY = HexColor('#F5F5F5')
CODE_BG = HexColor('#F0F0F0')

def create_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        name='MainTitle',
        parent=styles['Heading1'],
        fontSize=28,
        textColor=HEADER_BLUE,
        alignment=TA_CENTER,
        spaceAfter=6
    ))

    styles.add(ParagraphStyle(
        name='Subtitle',
        parent=styles['Normal'],
        fontSize=12,
        textColor=HexColor('#666666'),
        alignment=TA_CENTER,
        spaceAfter=30
    ))

    styles.add(ParagraphStyle(
        name='SectionHeader',
        parent=styles['Heading2'],
        fontSize=18,
        textColor=HEADER_BLUE,
        spaceBefore=20,
        spaceAfter=12
    ))

    styles.add(ParagraphStyle(
        name='LayerHeader',
        parent=styles['Heading2'],
        fontSize=14,
        textColor=LAYER_PURPLE,
        spaceBefore=16,
        spaceAfter=8,
        borderWidth=1,
        borderColor=LAYER_PURPLE,
        borderPadding=6,
        backColor=HexColor('#F8F6FF')
    ))

    styles.add(ParagraphStyle(
        name='SubHeader',
        parent=styles['Heading3'],
        fontSize=12,
        textColor=HexColor('#333333'),
        spaceBefore=12,
        spaceAfter=6,
        fontName='Helvetica-Bold'
    ))

    styles.add(ParagraphStyle(
        name='Body',
        parent=styles['Normal'],
        fontSize=10,
        spaceAfter=8
    ))

    styles.add(ParagraphStyle(
        name='BulletText',
        parent=styles['Normal'],
        fontSize=10,
        leftIndent=20,
        spaceAfter=4
    ))

    styles.add(ParagraphStyle(
        name='CodeStyle',
        fontName='Courier',
        fontSize=8,
        leftIndent=10,
        backColor=CODE_BG,
        spaceAfter=8
    ))

    return styles


def create_table(data, col_widths=None):
    """Create a styled table"""
    table = Table(data, colWidths=col_widths)
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), TABLE_HEADER),
        ('TEXTCOLOR', (0, 0), (-1, 0), HexColor('#FFFFFF')),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 9),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('GRID', (0, 0), (-1, -1), 0.5, HexColor('#CCCCCC')),
        ('BACKGROUND', (0, 1), (-1, -1), HexColor('#FFFFFF')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [HexColor('#FFFFFF'), LIGHT_GRAY]),
        ('TOPPADDING', (0, 0), (-1, -1), 6),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('LEFTPADDING', (0, 0), (-1, -1), 8),
    ]))
    return table


def build_pdf():
    output_path = os.path.join(os.path.dirname(__file__), 'Voice_AI_Phone_Ordering_Plan.pdf')
    doc = SimpleDocTemplate(
        output_path,
        pagesize=letter,
        rightMargin=0.75*inch,
        leftMargin=0.75*inch,
        topMargin=0.75*inch,
        bottomMargin=0.75*inch
    )

    styles = create_styles()
    story = []

    # Title
    story.append(Paragraph("Voice AI Phone Ordering System", styles['MainTitle']))
    story.append(Paragraph("Intelligent Phone-Based Order Taking", styles['Subtitle']))
    story.append(Spacer(1, 20))

    # Overview
    story.append(Paragraph("Overview", styles['SectionHeader']))
    story.append(Paragraph(
        "An AI-powered voice assistant that answers incoming phone calls, takes food orders "
        "conversationally, answers customer questions, and submits orders directly to the POS system. "
        "Uses Twilio for telephony and OpenAI Realtime API for natural speech-to-speech conversation.",
        styles['Body']
    ))
    story.append(Spacer(1, 10))

    # Architecture Diagram (as text box)
    story.append(Paragraph("System Architecture", styles['SectionHeader']))
    arch_text = """
    CUSTOMER CALL
         │
         ▼
    TWILIO VOICE (receives call, opens Media Stream)
         │ WebSocket (audio stream)
         ▼
    YOUR SERVER (WebSocket bridge, tool calls, order state)
         │                    │
         ▼                    ▼
    OPENAI REALTIME      YOUR POS DATABASE
    API (GPT-4o)         • Menu & pricing
    Speech-to-Speech     • Inventory availability
    Tool calling         • Order creation
    """
    story.append(Preformatted(arch_text, styles['CodeStyle']))
    story.append(Spacer(1, 10))

    # Core Components
    story.append(Paragraph("Core Components", styles['SectionHeader']))

    story.append(Paragraph("1. Twilio Voice + Media Streams", styles['LayerHeader']))
    story.append(Paragraph("<b>Purpose:</b> Telephony infrastructure - receives calls, streams audio", styles['Body']))
    story.append(Paragraph("Configuration needed:", styles['SubHeader']))
    story.append(Paragraph("• Twilio phone number", styles['BulletText']))
    story.append(Paragraph("• Webhook URL for incoming calls", styles['BulletText']))
    story.append(Paragraph("• Media Stream WebSocket endpoint", styles['BulletText']))
    story.append(Spacer(1, 6))
    story.append(Paragraph("How it works:", styles['SubHeader']))
    story.append(Paragraph("1. Customer dials your Twilio number", styles['BulletText']))
    story.append(Paragraph("2. Twilio sends webhook to your server", styles['BulletText']))
    story.append(Paragraph("3. Server responds with TwiML to open Media Stream", styles['BulletText']))
    story.append(Paragraph("4. Bidirectional audio flows over WebSocket", styles['BulletText']))

    story.append(Paragraph("2. OpenAI Realtime API", styles['LayerHeader']))
    story.append(Paragraph("<b>Purpose:</b> Conversational AI with native voice", styles['Body']))
    story.append(Paragraph("<b>Key features:</b>", styles['Body']))
    story.append(Paragraph("• Direct speech-to-speech (no intermediate transcription)", styles['BulletText']))
    story.append(Paragraph("• Sub-second response latency", styles['BulletText']))
    story.append(Paragraph("• Function/tool calling mid-conversation", styles['BulletText']))
    story.append(Paragraph("• Natural interruption handling", styles['BulletText']))
    story.append(Paragraph("<b>Model:</b> GPT-4o Realtime", styles['Body']))

    story.append(Paragraph("3. WebSocket Bridge Server", styles['LayerHeader']))
    story.append(Paragraph("<b>Purpose:</b> Connects Twilio audio stream to OpenAI, handles business logic", styles['Body']))
    story.append(Paragraph("Responsibilities:", styles['SubHeader']))
    story.append(Paragraph("• Audio format conversion (Twilio μ-law ↔ OpenAI PCM)", styles['BulletText']))
    story.append(Paragraph("• Tool call execution (query menu, create orders)", styles['BulletText']))
    story.append(Paragraph("• Session state management", styles['BulletText']))
    story.append(Paragraph("• Error handling and escalation", styles['BulletText']))

    # Page break
    story.append(PageBreak())

    # Tool Definitions
    story.append(Paragraph("Tool Definitions", styles['SectionHeader']))
    story.append(Paragraph("The AI assistant needs tools to interact with your POS system:", styles['Body']))

    story.append(Paragraph("Menu & Pricing Tools", styles['SubHeader']))
    menu_tools = [
        ['Tool', 'Parameters', 'Returns'],
        ['get_menu', 'category (optional)', 'List of items with descriptions'],
        ['get_item_details', 'item_name', 'Price, sizes, modifiers, description'],
        ['get_specials', 'none', "Today's specials"],
        ['check_availability', 'item_name', 'In stock (yes/no), alternatives'],
    ]
    story.append(create_table(menu_tools, col_widths=[1.5*inch, 1.8*inch, 2.5*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Order Management Tools", styles['SubHeader']))
    order_tools = [
        ['Tool', 'Parameters', 'Returns'],
        ['start_order', 'order_type (pickup/delivery)', 'order_session_id'],
        ['add_item', 'item, quantity, size, modifiers', 'Updated order summary'],
        ['remove_item', 'item', 'Updated order summary'],
        ['get_order_summary', 'none', 'Items, subtotal, tax, total'],
        ['submit_order', 'customer_name, phone, (address)', 'Order number, wait time'],
    ]
    story.append(create_table(order_tools, col_widths=[1.5*inch, 2.2*inch, 2.1*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Business Info Tools", styles['SubHeader']))
    biz_tools = [
        ['Tool', 'Parameters', 'Returns'],
        ['get_hours', 'day (optional)', 'Open/close times'],
        ['get_wait_time', 'order_type', 'Estimated minutes'],
        ['get_location', 'none', 'Address, directions hint'],
        ['transfer_to_human', 'reason', 'Transfers call to staff'],
    ]
    story.append(create_table(biz_tools, col_widths=[1.5*inch, 1.8*inch, 2.5*inch]))
    story.append(Spacer(1, 15))

    # Conversation Flow
    story.append(Paragraph("Conversation Flow", styles['SectionHeader']))
    story.append(Paragraph("Standard Order Flow:", styles['SubHeader']))

    flow_text = """
1. GREETING
   AI: "Thanks for calling [Restaurant]. This is our AI assistant.
        Are you calling to place an order?"

2. ORDER TYPE
   Customer: "Yeah, I want to do a pickup"
   AI: [calls start_order("pickup")]
   AI: "Great, pickup order! What can I get for you?"

3. ITEM COLLECTION
   Customer: "Can I get a large pepperoni pizza"
   AI: [calls get_item_details("pepperoni pizza")]
   AI: [calls check_availability("pepperoni pizza")]
   AI: [calls add_item("pepperoni pizza", 1, "large")]
   AI: "I've got a large pepperoni for $18.99. Anything else?"

4. ORDER REVIEW
   Customer: "That's it"
   AI: [calls get_order_summary()]
   AI: "Your total is $20.68 including tax. Name for the order?"

5. SUBMIT
   Customer: "Mike, 555-123-4567"
   AI: [calls submit_order("Mike", "555-123-4567")]
   AI: "Thanks Mike! Order #47, ready in about 20 minutes!"
"""
    story.append(Preformatted(flow_text, styles['CodeStyle']))

    # Page break
    story.append(PageBreak())

    # Escalation Triggers
    story.append(Paragraph("Escalation Triggers", styles['SectionHeader']))
    story.append(Paragraph("The AI should transfer to human staff when:", styles['Body']))

    escalation_data = [
        ['Trigger', 'Action'],
        ['Customer explicitly requests human', 'Immediate transfer'],
        ['Complaint or angry tone detected', 'Transfer with context'],
        ['Complex catering/large order', 'Transfer with order so far'],
        ['Question AI cannot answer (2 attempts)', 'Transfer'],
        ['Payment issue or refund request', 'Transfer'],
        ['Allergy concern requiring confirmation', 'Transfer'],
        ['Technical failure (API error, etc.)', 'Transfer with apology'],
    ]
    story.append(create_table(escalation_data, col_widths=[3*inch, 2.8*inch]))
    story.append(Spacer(1, 15))

    # Database Integration
    story.append(Paragraph("Database Integration", styles['SectionHeader']))
    story.append(Paragraph("New Tables Required:", styles['SubHeader']))

    story.append(Paragraph("<b>voice_calls</b>", styles['Body']))
    db_text = """
CREATE TABLE voice_calls (
    id INTEGER PRIMARY KEY,
    call_sid TEXT UNIQUE,        -- Twilio call identifier
    phone_from TEXT,
    phone_to TEXT,
    started_at TIMESTAMP,
    ended_at TIMESTAMP,
    duration_seconds INTEGER,
    disposition TEXT,            -- completed/transferred/abandoned
    order_id INTEGER,            -- FK to orders if order placed
    transcript TEXT,             -- Full conversation log
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
    story.append(Preformatted(db_text, styles['CodeStyle']))

    story.append(Paragraph("<b>voice_call_events</b>", styles['Body']))
    db_text2 = """
CREATE TABLE voice_call_events (
    id INTEGER PRIMARY KEY,
    call_id INTEGER REFERENCES voice_calls(id),
    event_type TEXT,             -- tool_call/transfer/error
    event_data JSON,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""
    story.append(Preformatted(db_text2, styles['CodeStyle']))

    story.append(Paragraph("Integration with Existing Tables:", styles['SubHeader']))
    story.append(Paragraph("The voice system uses existing POS tables:", styles['Body']))
    story.append(Paragraph("• <b>products</b> - menu items, prices", styles['BulletText']))
    story.append(Paragraph("• <b>ingredients</b> - for availability checks", styles['BulletText']))
    story.append(Paragraph("• <b>orders</b> - created via submit_order tool", styles['BulletText']))
    story.append(Paragraph("• <b>order_items</b> - line items", styles['BulletText']))
    story.append(Paragraph("• <b>customers</b> - lookup/create by phone", styles['BulletText']))

    # Page break
    story.append(PageBreak())

    # Concurrency & Scaling
    story.append(Paragraph("Concurrency & Multi-Line Support", styles['SectionHeader']))

    story.append(Paragraph(
        "The system supports multiple simultaneous phone calls. Each incoming call gets its own "
        "isolated session with independent state management.",
        styles['Body']
    ))
    story.append(Spacer(1, 8))

    concurrency_diagram = """
    Call 1 ──► Twilio ──► WebSocket 1 ──► OpenAI Session 1
    Call 2 ──► Twilio ──► WebSocket 2 ──► OpenAI Session 2
    Call 3 ──► Twilio ──► WebSocket 3 ──► OpenAI Session 3
         ...
    """
    story.append(Preformatted(concurrency_diagram, styles['CodeStyle']))

    story.append(Paragraph("Concurrency by Component:", styles['SubHeader']))
    concurrency_data = [
        ['Component', 'Handles Concurrency?', 'Notes'],
        ['Twilio', 'Yes, automatically', 'One number handles unlimited concurrent calls'],
        ['OpenAI Realtime', 'Yes, per-session', 'Each call = separate API session'],
        ['Your Server', 'Requires async design', 'Must handle multiple WebSocket connections'],
    ]
    story.append(create_table(concurrency_data, col_widths=[1.5*inch, 1.6*inch, 2.7*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Server Scaling Requirements:", styles['SubHeader']))
    scaling_data = [
        ['Concurrent Calls', 'Server Type', 'Specs', 'Monthly Cost'],
        ['1-10', 'Basic VPS', '2 CPU, 4GB RAM', '$20-40'],
        ['10-50', 'Mid-tier server', '4 CPU, 8GB RAM', '$80-150'],
        ['50+', 'Multi-instance + LB', 'Horizontal scaling', '$300-600'],
    ]
    story.append(create_table(scaling_data, col_widths=[1.3*inch, 1.5*inch, 1.5*inch, 1.3*inch]))
    story.append(Spacer(1, 15))

    # Cost Analysis (Expanded)
    story.append(Paragraph("Quantitative Cost Analysis", styles['SectionHeader']))

    story.append(Paragraph("Fixed API Costs (Per Minute of Call):", styles['SubHeader']))
    story.append(Paragraph(
        "These costs are constant regardless of server infrastructure:",
        styles['Body']
    ))
    api_cost_data = [
        ['Component', 'Cost/Minute', '% of Total'],
        ['Twilio Voice (inbound)', '$0.0085', '2.7%'],
        ['Twilio Media Streams', 'Free', '0%'],
        ['OpenAI Realtime (audio in)', '$0.06', '19.4%'],
        ['OpenAI Realtime (audio out)', '$0.24', '77.4%'],
        ['Subtotal (API costs)', '$0.3085', '99.5%'],
    ]
    story.append(create_table(api_cost_data, col_widths=[2.2*inch, 1.5*inch, 1.3*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Infrastructure Costs (Per Minute):", styles['SubHeader']))
    story.append(Paragraph(
        "Server costs amortized over ~10,000 call-minutes/month:",
        styles['Body']
    ))
    infra_cost_data = [
        ['Scale', 'Server Monthly', 'Cost/Minute', '% of Total'],
        ['Small (1-10 concurrent)', '$30', '$0.003', '~1%'],
        ['Medium (10-50 concurrent)', '$120', '$0.012', '~4%'],
        ['Large (50+ concurrent)', '$450', '$0.045', '~13%'],
    ]
    story.append(create_table(infra_cost_data, col_widths=[1.8*inch, 1.2*inch, 1.1*inch, 1.1*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Total Cost Per Minute by Scale:", styles['SubHeader']))
    total_cost_data = [
        ['Scale', 'API Costs', 'Infrastructure', 'Total/Minute'],
        ['Small (1-10 calls)', '$0.3085', '$0.003', '$0.311'],
        ['Medium (10-50 calls)', '$0.3085', '$0.012', '$0.320'],
        ['Large (50+ calls)', '$0.3085', '$0.045', '$0.354'],
    ]
    story.append(create_table(total_cost_data, col_widths=[1.6*inch, 1.3*inch, 1.3*inch, 1.3*inch]))
    story.append(Spacer(1, 10))

    story.append(Paragraph(
        "<b>Key Insight:</b> Infrastructure is &lt;15% of total cost even at large scale. "
        "OpenAI Realtime audio output ($0.24/min) dominates at 77% of costs.",
        styles['Body']
    ))
    story.append(Spacer(1, 12))

    # Page break before monthly projections
    story.append(PageBreak())

    story.append(Paragraph("Monthly Cost Projections", styles['SectionHeader']))

    story.append(Paragraph("By Call Volume (assuming 3-min avg call):", styles['SubHeader']))
    monthly_data = [
        ['Monthly Calls', 'Total Minutes', 'API Costs', 'Infra (Med)', 'Total Cost'],
        ['100', '300', '$93', '$30', '$123'],
        ['500', '1,500', '$463', '$80', '$543'],
        ['1,000', '3,000', '$925', '$120', '$1,045'],
        ['2,500', '7,500', '$2,314', '$200', '$2,514'],
        ['5,000', '15,000', '$4,628', '$400', '$5,028'],
    ]
    story.append(create_table(monthly_data, col_widths=[1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch, 1.1*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Cost Per Order Analysis:", styles['SubHeader']))
    order_analysis = [
        ['Monthly Calls', 'Est. Orders (70% conv.)', 'Cost/Order', 'Avg Order Value', 'Cost as % of Order'],
        ['100', '70', '$1.76', '$30', '5.9%'],
        ['500', '350', '$1.55', '$30', '5.2%'],
        ['1,000', '700', '$1.49', '$30', '5.0%'],
        ['2,500', '1,750', '$1.44', '$30', '4.8%'],
        ['5,000', '3,500', '$1.44', '$30', '4.8%'],
    ]
    story.append(create_table(order_analysis, col_widths=[1.1*inch, 1.4*inch, 1*inch, 1.2*inch, 1.3*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Break-Even Analysis:", styles['SubHeader']))
    story.append(Paragraph(
        "Assuming the voice AI replaces one part-time employee during peak hours:",
        styles['Body']
    ))
    breakeven_data = [
        ['Metric', 'Value'],
        ['Part-time wage (phone duty)', '$15/hour'],
        ['Hours replaced per day', '4 hours (lunch + dinner rush)'],
        ['Monthly labor savings', '$1,800 (30 days × 4 hrs × $15)'],
        ['Break-even call volume', '~1,700 calls/month'],
        ['Additional benefit', 'No missed calls, 24/7 capability'],
    ]
    story.append(create_table(breakeven_data, col_widths=[2.5*inch, 3*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("ROI Considerations:", styles['SubHeader']))
    story.append(Paragraph("• <b>Labor offset:</b> Each call handled = 3-5 min staff time saved", styles['BulletText']))
    story.append(Paragraph("• <b>Missed call recovery:</b> AI answers during rush when staff can't", styles['BulletText']))
    story.append(Paragraph("• <b>Upselling consistency:</b> AI always offers drinks/sides (humans forget)", styles['BulletText']))
    story.append(Paragraph("• <b>Extended hours:</b> Take orders before open / after close", styles['BulletText']))
    story.append(Paragraph("• <b>Order accuracy:</b> No mishearing, automatic logging", styles['BulletText']))
    story.append(Spacer(1, 15))

    # Implementation Phases
    story.append(Paragraph("Implementation Phases", styles['SectionHeader']))

    story.append(Paragraph("Phase 1 - Basic MVP", styles['LayerHeader']))
    story.append(Paragraph("• Twilio number + webhook setup", styles['BulletText']))
    story.append(Paragraph("• WebSocket bridge server", styles['BulletText']))
    story.append(Paragraph("• OpenAI Realtime integration", styles['BulletText']))
    story.append(Paragraph("• Basic tools: get_menu, add_item, submit_order", styles['BulletText']))
    story.append(Paragraph("• Simple order flow (pickup only)", styles['BulletText']))
    story.append(Paragraph("• Transfer to human fallback", styles['BulletText']))

    story.append(Paragraph("Phase 2 - Full Features", styles['LayerHeader']))
    story.append(Paragraph("• Delivery orders with address capture", styles['BulletText']))
    story.append(Paragraph("• Inventory availability checks", styles['BulletText']))
    story.append(Paragraph("• Customer lookup by phone", styles['BulletText']))
    story.append(Paragraph("• Rewards points integration", styles['BulletText']))
    story.append(Paragraph("• Order modifications mid-call", styles['BulletText']))
    story.append(Paragraph("• Specials and upselling", styles['BulletText']))

    story.append(Paragraph("Phase 3 - Advanced", styles['LayerHeader']))
    story.append(Paragraph("• Call analytics dashboard", styles['BulletText']))
    story.append(Paragraph("• Sentiment detection", styles['BulletText']))
    story.append(Paragraph("• Multi-language support", styles['BulletText']))
    story.append(Paragraph("• Outbound calls (order ready notifications)", styles['BulletText']))
    story.append(Paragraph("• Voice authentication for repeat customers", styles['BulletText']))

    # Page break
    story.append(PageBreak())

    # Implementation Steps
    story.append(Paragraph("Implementation Steps", styles['SectionHeader']))

    story.append(Paragraph("Step 1: Twilio Setup", styles['SubHeader']))
    story.append(Paragraph("1. Create Twilio account and purchase phone number", styles['BulletText']))
    story.append(Paragraph("2. Install Twilio SDK: pip install twilio", styles['BulletText']))
    story.append(Paragraph("3. Configure webhook URLs in Twilio console:", styles['BulletText']))
    story.append(Paragraph("   • Voice webhook: https://yourserver.com/voice/incoming", styles['BulletText']))
    story.append(Paragraph("   • Status callback: https://yourserver.com/voice/status", styles['BulletText']))

    story.append(Paragraph("Step 2: OpenAI Realtime Setup", styles['SubHeader']))
    story.append(Paragraph("1. Get OpenAI API key with Realtime API access", styles['BulletText']))
    story.append(Paragraph("2. Install SDK: pip install openai", styles['BulletText']))
    story.append(Paragraph("3. Configure model and tools in session setup", styles['BulletText']))

    story.append(Paragraph("Step 3: WebSocket Server", styles['SubHeader']))
    story.append(Paragraph("Create /routes/voice_routes.py:", styles['Body']))

    code_text = """
@voice_bp.route('/voice/incoming', methods=['POST'])
def incoming_call():
    response = VoiceResponse()
    response.say("Please wait while I connect you.")

    connect = Connect()
    connect.stream(url='wss://yourserver.com/voice/stream')
    response.append(connect)

    return str(response)
"""
    story.append(Preformatted(code_text, styles['CodeStyle']))

    story.append(Paragraph("Step 4: Register Routes", styles['SubHeader']))
    story.append(Paragraph("In app.py:", styles['Body']))
    code_text2 = """
from routes.voice_routes import voice_bp
app.register_blueprint(voice_bp)
"""
    story.append(Preformatted(code_text2, styles['CodeStyle']))
    story.append(Spacer(1, 15))

    # Monitoring
    story.append(Paragraph("Monitoring & Analytics", styles['SectionHeader']))

    story.append(Paragraph("Key Metrics to Track:", styles['SubHeader']))
    metrics_data = [
        ['Metric', 'Target'],
        ['Call completion rate', '>85%'],
        ['Order conversion rate', '>70%'],
        ['Average call duration', '<4 min'],
        ['Transfer rate', '<15%'],
        ['Customer satisfaction', '>4.0/5'],
    ]
    story.append(create_table(metrics_data, col_widths=[2.5*inch, 2*inch]))
    story.append(Spacer(1, 12))

    story.append(Paragraph("Dashboard Elements:", styles['SubHeader']))
    story.append(Paragraph("• Calls today / this week / this month", styles['BulletText']))
    story.append(Paragraph("• Orders placed via voice", styles['BulletText']))
    story.append(Paragraph("• Revenue from voice orders", styles['BulletText']))
    story.append(Paragraph("• Common transfer reasons", styles['BulletText']))
    story.append(Paragraph("• Peak call times", styles['BulletText']))
    story.append(Paragraph("• Average order value (voice vs other channels)", styles['BulletText']))
    story.append(Spacer(1, 15))

    # Security
    story.append(Paragraph("Security Considerations", styles['SectionHeader']))
    story.append(Paragraph("• <b>No payment over phone:</b> Collect payment in-store or redirect to secure link", styles['BulletText']))
    story.append(Paragraph("• <b>Phone validation:</b> Verify caller ID when possible", styles['BulletText']))
    story.append(Paragraph("• <b>Rate limiting:</b> Prevent abuse of AI minutes", styles['BulletText']))
    story.append(Paragraph("• <b>PII handling:</b> Don't log sensitive data in transcripts", styles['BulletText']))
    story.append(Paragraph("• <b>Call recording consent:</b> Announce if calls are recorded (state laws vary)", styles['BulletText']))

    # Build PDF
    doc.build(story)
    print(f"PDF created: {output_path}")
    return output_path


if __name__ == '__main__':
    build_pdf()
