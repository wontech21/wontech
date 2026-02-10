"""
Share Routes - Email and SMS sharing functionality
"""

from flask import Blueprint, request, jsonify, send_file, current_app, g
import os
import base64
import secrets
import json
from datetime import datetime, timedelta
from functools import wraps

share_bp = Blueprint('share', __name__, url_prefix='/api/share')

# In-memory store for temporary share links (use Redis/DB in production)
# Format: { token: { 'file_data': ..., 'file_name': ..., 'expires': datetime, 'file_type': ... } }
temp_shares = {}

# Cleanup expired shares
def cleanup_expired_shares():
    now = datetime.now()
    expired = [token for token, data in temp_shares.items() if data['expires'] < now]
    for token in expired:
        del temp_shares[token]


def get_email_service():
    """Get configured email service"""
    # Check for SendGrid
    sendgrid_key = current_app.config.get('SENDGRID_API_KEY')
    if sendgrid_key:
        try:
            import sendgrid
            return 'sendgrid', sendgrid_key
        except ImportError:
            pass

    # Check for SMTP config
    smtp_host = current_app.config.get('SMTP_HOST')
    if smtp_host:
        return 'smtp', {
            'host': smtp_host,
            'port': current_app.config.get('SMTP_PORT', 587),
            'user': current_app.config.get('SMTP_USER'),
            'password': current_app.config.get('SMTP_PASSWORD'),
            'from_email': current_app.config.get('SMTP_FROM', 'noreply@wontech.app')
        }

    return None, None


def get_sms_service():
    """Get configured SMS service"""
    twilio_sid = current_app.config.get('TWILIO_ACCOUNT_SID')
    twilio_token = current_app.config.get('TWILIO_AUTH_TOKEN')
    twilio_phone = current_app.config.get('TWILIO_PHONE_NUMBER')

    if twilio_sid and twilio_token and twilio_phone:
        try:
            from twilio.rest import Client
            return 'twilio', {
                'sid': twilio_sid,
                'token': twilio_token,
                'from_phone': twilio_phone
            }
        except ImportError:
            pass

    return None, None


# ==========================================
# EMAIL SHARING
# ==========================================

@share_bp.route('/email', methods=['POST'])
def send_email():
    """
    Send email with file attachment

    Body: {
        "to": "email@example.com",
        "subject": "Your Report",
        "message": "Please find attached...",
        "file_data": "base64_encoded_file",
        "file_name": "report.csv",
        "file_type": "text/csv"
    }
    """
    data = request.get_json()

    to_email = data.get('to')
    subject = data.get('subject', 'Your Report from WONTECH')
    message = data.get('message', '')
    file_data_b64 = data.get('file_data')
    file_name = data.get('file_name', 'report.csv')
    file_type = data.get('file_type', 'text/csv')

    if not to_email:
        return jsonify({'error': 'Recipient email is required'}), 400

    if not file_data_b64:
        return jsonify({'error': 'File data is required'}), 400

    # Decode file data
    try:
        file_data = base64.b64decode(file_data_b64)
    except Exception as e:
        return jsonify({'error': 'Invalid file data'}), 400

    # Get email service
    service_type, config = get_email_service()

    if not service_type:
        return jsonify({'error': 'Email service not configured. Add SENDGRID_API_KEY or SMTP settings.'}), 400

    try:
        if service_type == 'sendgrid':
            result = send_via_sendgrid(config, to_email, subject, message, file_data, file_name, file_type)
        elif service_type == 'smtp':
            result = send_via_smtp(config, to_email, subject, message, file_data, file_name, file_type)

        return jsonify({'success': True, 'message': 'Email sent successfully'})

    except Exception as e:
        return jsonify({'error': f'Failed to send email: {str(e)}'}), 500


def send_via_sendgrid(api_key, to_email, subject, message, file_data, file_name, file_type):
    """Send email via SendGrid"""
    import sendgrid
    from sendgrid.helpers.mail import Mail, Attachment, FileContent, FileName, FileType, Disposition

    sg = sendgrid.SendGridAPIClient(api_key=api_key)

    from_email = current_app.config.get('EMAIL_FROM', 'reports@wontech.app')

    html_content = f"""
    <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); padding: 20px; text-align: center;">
            <h1 style="color: white; margin: 0;">WONTECH</h1>
        </div>
        <div style="padding: 30px; background: #f8f9fa;">
            <p>{message or 'Please find your report attached.'}</p>
            <p style="color: #666; font-size: 14px; margin-top: 30px;">
                This report was shared from WONTECH.
            </p>
        </div>
    </div>
    """

    mail = Mail(
        from_email=from_email,
        to_emails=to_email,
        subject=subject,
        html_content=html_content
    )

    # Add attachment
    encoded_file = base64.b64encode(file_data).decode()
    attachment = Attachment(
        FileContent(encoded_file),
        FileName(file_name),
        FileType(file_type),
        Disposition('attachment')
    )
    mail.attachment = attachment

    response = sg.send(mail)
    return response.status_code == 202


def send_via_smtp(config, to_email, subject, message, file_data, file_name, file_type):
    """Send email via SMTP"""
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    from email.mime.base import MIMEBase
    from email import encoders

    msg = MIMEMultipart()
    msg['From'] = config['from_email']
    msg['To'] = to_email
    msg['Subject'] = subject

    # Body
    body = message or 'Please find your report attached.'
    msg.attach(MIMEText(body, 'plain'))

    # Attachment
    part = MIMEBase('application', 'octet-stream')
    part.set_payload(file_data)
    encoders.encode_base64(part)
    part.add_header('Content-Disposition', f'attachment; filename="{file_name}"')
    msg.attach(part)

    # Send
    with smtplib.SMTP(config['host'], config['port']) as server:
        server.starttls()
        if config.get('user') and config.get('password'):
            server.login(config['user'], config['password'])
        server.send_message(msg)

    return True


# ==========================================
# SMS/TEXT SHARING
# ==========================================

@share_bp.route('/text', methods=['POST'])
def send_text():
    """
    Send SMS with download link

    Body: {
        "to": "+15555555555",
        "message": "Your report is ready",
        "file_data": "base64_encoded_file",
        "file_name": "report.csv",
        "file_type": "text/csv"
    }
    """
    data = request.get_json()

    to_phone = data.get('to')
    message = data.get('message', 'Your report from WONTECH is ready.')
    file_data_b64 = data.get('file_data')
    file_name = data.get('file_name', 'report.csv')
    file_type = data.get('file_type', 'text/csv')

    if not to_phone:
        return jsonify({'error': 'Phone number is required'}), 400

    if not file_data_b64:
        return jsonify({'error': 'File data is required'}), 400

    # Clean phone number
    to_phone = ''.join(filter(str.isdigit, to_phone))
    if len(to_phone) == 10:
        to_phone = '+1' + to_phone
    elif not to_phone.startswith('+'):
        to_phone = '+' + to_phone

    # Get SMS service
    service_type, config = get_sms_service()

    if not service_type:
        return jsonify({'error': 'SMS service not configured. Add Twilio credentials.'}), 400

    try:
        # Decode and store file temporarily
        file_data = base64.b64decode(file_data_b64)

        # Generate secure download token
        token = secrets.token_urlsafe(32)
        expiry_hours = current_app.config.get('SHARE_LINK_EXPIRY_HOURS', 24)

        temp_shares[token] = {
            'file_data': file_data,
            'file_name': file_name,
            'file_type': file_type,
            'expires': datetime.now() + timedelta(hours=expiry_hours)
        }

        # Cleanup old shares
        cleanup_expired_shares()

        # Build download URL
        base_url = request.host_url.rstrip('/')
        download_url = f"{base_url}/api/share/download/{token}"

        # Send SMS
        full_message = f"{message}\n\nDownload: {download_url}\n\n(Link expires in {expiry_hours}h)"

        if service_type == 'twilio':
            send_via_twilio(config, to_phone, full_message)

        return jsonify({'success': True, 'message': 'Text sent successfully'})

    except Exception as e:
        return jsonify({'error': f'Failed to send text: {str(e)}'}), 500


def send_via_twilio(config, to_phone, message):
    """Send SMS via Twilio"""
    from twilio.rest import Client

    client = Client(config['sid'], config['token'])

    client.messages.create(
        body=message,
        from_=config['from_phone'],
        to=to_phone
    )

    return True


# ==========================================
# DOWNLOAD SHARED FILES
# ==========================================

@share_bp.route('/download/<token>', methods=['GET'])
def download_shared_file(token):
    """Download a temporarily shared file"""
    cleanup_expired_shares()

    if token not in temp_shares:
        return jsonify({'error': 'Link expired or invalid'}), 404

    share_data = temp_shares[token]

    if share_data['expires'] < datetime.now():
        del temp_shares[token]
        return jsonify({'error': 'Link has expired'}), 410

    # Create response with file
    from io import BytesIO
    file_buffer = BytesIO(share_data['file_data'])

    return send_file(
        file_buffer,
        mimetype=share_data['file_type'],
        as_attachment=True,
        download_name=share_data['file_name']
    )


# ==========================================
# SERVICE STATUS
# ==========================================

@share_bp.route('/status', methods=['GET'])
def share_status():
    """Check which sharing services are configured"""
    email_type, _ = get_email_service()
    sms_type, _ = get_sms_service()

    return jsonify({
        'email': {
            'configured': email_type is not None,
            'service': email_type
        },
        'sms': {
            'configured': sms_type is not None,
            'service': sms_type
        }
    })
