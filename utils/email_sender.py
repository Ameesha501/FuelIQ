# utils/email_sender.py
import smtplib
import io
import os
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders

SMTP_SERVER    = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
SMTP_PORT      = int(os.environ.get('SMTP_PORT', '587'))
EMAIL_USER     = os.environ.get('EMAIL_USER', 'bangeraameesha501@gmail.com')
EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD', 'erptribsbqfutxhf')
FROM_EMAIL     = os.environ.get('FROM_EMAIL', 'bangeraameesha501@gmail.com')


def _generate_pdf(bill_data: dict) -> bytes:
    """Generate a PDF bill using reportlab and return raw bytes."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.lib.units import mm
    from reportlab.platypus import (SimpleDocTemplate, Table, TableStyle,
                                    Paragraph, Spacer, HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.enums import TA_CENTER, TA_RIGHT

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4,
                            rightMargin=20*mm, leftMargin=20*mm,
                            topMargin=20*mm, bottomMargin=20*mm)

    styles  = getSampleStyleSheet()
    accent  = colors.HexColor('#6c63ff')
    dark    = colors.HexColor('#1c1f2e')
    muted   = colors.HexColor('#64748b')
    light_bg = colors.HexColor('#f8fafc')
    grid_c  = colors.HexColor('#e2e8f0')

    title_s = ParagraphStyle('t', parent=styles['Title'],
                             textColor=colors.white, fontSize=22,
                             spaceAfter=4, alignment=TA_CENTER)
    sub_s   = ParagraphStyle('s', parent=styles['Normal'],
                             textColor=colors.HexColor('#a5b4fc'),
                             fontSize=10, alignment=TA_CENTER)
    foot_s  = ParagraphStyle('f', parent=styles['Normal'],
                             textColor=muted, fontSize=8, alignment=TA_CENTER)

    ts_raw  = str(bill_data.get('timestamp', ''))[:19].replace('T', ' ')
    liters  = float(bill_data.get('liters', 0) or 0)
    rate    = float(bill_data.get('rate', 0) or 0)
    total   = float(bill_data.get('total_amount', 0) or 0)
    b_bef   = float(bill_data.get('balance_before', 0) or 0)
    b_aft   = float(bill_data.get('balance_after', 0) or 0)

    elements = []

    # ── Header banner ──────────────────────────────────────────────
    hdr = Table([[Paragraph('<b>FuelIQ</b>', title_s)],
                 [Paragraph('Smart Fueling System — Fuel Bill', sub_s)]],
                colWidths=[170*mm])
    hdr.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, -1), dark),
        ('TOPPADDING',    (0, 0), (-1, -1), 14),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 14),
    ]))
    elements += [hdr, Spacer(1, 8*mm)]

    # ── Bill meta ──────────────────────────────────────────────────
    meta = Table([
        ['Bill ID',       str(bill_data.get('bill_id', '')),
         'Date & Time',   ts_raw],
        ['Vehicle Plate', str(bill_data.get('number_plate_id', '')),
         'Wallet ID',     str(bill_data.get('wallet_id', ''))],
    ], colWidths=[35*mm, 55*mm, 35*mm, 45*mm])
    meta.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTNAME',      (2, 0), (2, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (0, 0), (0, -1), muted),
        ('TEXTCOLOR',     (2, 0), (2, -1), muted),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
        ('TOPPADDING',    (0, 0), (-1, -1), 6),
        ('BACKGROUND',    (0, 0), (-1, -1), light_bg),
        ('GRID',          (0, 0), (-1, -1), 0.5, grid_c),
    ]))
    elements += [meta, Spacer(1, 6*mm),
                 HRFlowable(width='100%', thickness=1, color=grid_c),
                 Spacer(1, 6*mm)]

    # ── Line items ─────────────────────────────────────────────────
    items = Table(
        [['Description', 'Quantity', 'Rate (/L)', 'Amount']] +
        [[str(bill_data.get('fuel_type', 'Fuel')),
          f'{liters:.2f} L', f'Rs.{rate:.2f}', f'Rs.{total:.2f}']],
        colWidths=[80*mm, 30*mm, 30*mm, 30*mm])
    items.setStyle(TableStyle([
        ('BACKGROUND',    (0, 0), (-1, 0), accent),
        ('TEXTCOLOR',     (0, 0), (-1, 0), colors.white),
        ('FONTNAME',      (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (0, 0), (-1, -1), 10),
        ('ALIGN',         (1, 0), (-1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('ROWBACKGROUNDS',(0, 1), (-1, -1), [colors.white, light_bg]),
        ('GRID',          (0, 0), (-1, -1), 0.5, grid_c),
    ]))
    elements += [items, Spacer(1, 4*mm)]

    # ── Total row ──────────────────────────────────────────────────
    tot_tbl = Table([['', '', 'Total Amount:', f'Rs.{total:.2f}']],
                    colWidths=[80*mm, 30*mm, 30*mm, 30*mm])
    tot_tbl.setStyle(TableStyle([
        ('FONTNAME',      (2, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE',      (2, 0), (-1, 0), 12),
        ('TEXTCOLOR',     (3, 0), (3, 0), accent),
        ('ALIGN',         (2, 0), (-1, 0), 'RIGHT'),
        ('TOPPADDING',    (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    elements += [tot_tbl, Spacer(1, 6*mm),
                 HRFlowable(width='100%', thickness=1, color=grid_c),
                 Spacer(1, 4*mm)]

    # ── Balance summary ────────────────────────────────────────────
    bal = Table([
        ['Balance Before:', f'Rs.{b_bef:.2f}'],
        ['Amount Deducted:', f'Rs.{total:.2f}'],
        ['Balance After:',  f'Rs.{b_aft:.2f}'],
    ], colWidths=[60*mm, 40*mm])
    bal.setStyle(TableStyle([
        ('FONTNAME',      (0, 0), (0, -1), 'Helvetica-Bold'),
        ('TEXTCOLOR',     (0, 0), (0, -1), muted),
        ('FONTSIZE',      (0, 0), (-1, -1), 9),
        ('ALIGN',         (1, 0), (1, -1), 'RIGHT'),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING',    (0, 0), (-1, -1), 4),
    ]))
    elements += [bal, Spacer(1, 10*mm)]

    # ── Footer ─────────────────────────────────────────────────────
    elements.append(Paragraph('Thank you for using FuelIQ Smart Fueling System', foot_s))
    elements.append(Paragraph('This is a computer-generated bill. No signature required.', foot_s))

    doc.build(elements)
    return buf.getvalue()


def send_bill_email(bill_data: dict, recipient_email: str) -> bool:
    """
    Send fuel bill email with PDF attachment to recipient_email.
    Returns True on success (or demo mode), False on failure.
    """
    if not recipient_email:
        print("[Email] No recipient email provided")
        return False

    bill_id = bill_data.get('bill_id', 'N/A')
    liters  = float(bill_data.get('liters', 0) or 0)
    rate    = float(bill_data.get('rate', 0) or 0)
    total   = float(bill_data.get('total_amount', 0) or 0)
    b_bef   = float(bill_data.get('balance_before', 0) or 0)
    b_aft   = float(bill_data.get('balance_after', 0) or 0)
    ts      = str(bill_data.get('timestamp', ''))[:19].replace('T', ' ')

    # ── Build email ────────────────────────────────────────────────
    msg = MIMEMultipart('mixed')
    msg['From']    = FROM_EMAIL
    msg['To']      = recipient_email
    msg['Subject'] = f"FuelIQ — Fuel Bill {bill_id}"

    html_body = f"""
    <html><head><style>
      body{{font-family:Arial,sans-serif;background:#f1f5f9;margin:0;padding:0}}
      .wrap{{max-width:560px;margin:30px auto;background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 4px 20px rgba(0,0,0,.08)}}
      .hdr{{background:#1c1f2e;padding:28px 24px;text-align:center}}
      .hdr h1{{color:#fff;margin:0;font-size:26px;letter-spacing:1px}}
      .hdr p{{color:#a5b4fc;margin:4px 0 0;font-size:13px}}
      .body{{padding:24px}}
      .row{{display:flex;justify-content:space-between;padding:9px 0;border-bottom:1px solid #e2e8f0;font-size:14px}}
      .row:last-child{{border:none}}
      .lbl{{color:#64748b;font-weight:600}}
      .val{{color:#1e293b}}
      .total-row{{background:#f8fafc;border-radius:8px;padding:12px 16px;margin-top:16px;display:flex;justify-content:space-between;align-items:center}}
      .total-row .lbl{{font-size:15px;color:#1e293b}}
      .total-row .val{{font-size:20px;font-weight:700;color:#6c63ff}}
      .note{{font-size:12px;color:#94a3b8;text-align:center;margin-top:20px}}
      .ftr{{background:#f8fafc;padding:16px;text-align:center;font-size:12px;color:#94a3b8;border-top:1px solid #e2e8f0}}
    </style></head><body>
    <div class="wrap">
      <div class="hdr"><h1>FuelIQ</h1><p>Smart Fueling System — Fuel Bill</p></div>
      <div class="body">
        <div class="row"><span class="lbl">Bill ID</span><span class="val">{bill_id}</span></div>
        <div class="row"><span class="lbl">Date &amp; Time</span><span class="val">{ts}</span></div>
        <div class="row"><span class="lbl">Vehicle Plate</span><span class="val">{bill_data.get('number_plate_id','N/A')}</span></div>
        <div class="row"><span class="lbl">Wallet ID</span><span class="val">{bill_data.get('wallet_id','N/A')}</span></div>
        <div class="row"><span class="lbl">Fuel Type</span><span class="val">{bill_data.get('fuel_type','N/A')}</span></div>
        <div class="row"><span class="lbl">Quantity</span><span class="val">{liters:.2f} L</span></div>
        <div class="row"><span class="lbl">Rate</span><span class="val">Rs.{rate:.2f}/L</span></div>
        <div class="row"><span class="lbl">Balance Before</span><span class="val">Rs.{b_bef:.2f}</span></div>
        <div class="row"><span class="lbl">Balance After</span><span class="val">Rs.{b_aft:.2f}</span></div>
        <div class="total-row">
          <span class="lbl">Total Amount</span>
          <span class="val">Rs.{total:.2f}</span>
        </div>
        <p class="note">The PDF bill is attached to this email.</p>
      </div>
      <div class="ftr">FuelIQ — Reducing Billing Errors, Saving Time<br>This is an automated email. Please do not reply.</div>
    </div>
    </body></html>
    """
    msg.attach(MIMEText(html_body, 'html'))

    # ── Attach PDF ─────────────────────────────────────────────────
    try:
        pdf_bytes = _generate_pdf(bill_data)
        part = MIMEBase('application', 'pdf')
        part.set_payload(pdf_bytes)
        encoders.encode_base64(part)
        part.add_header('Content-Disposition',
                        f'attachment; filename="FuelIQ-Bill-{bill_id}.pdf"')
        msg.attach(part)
    except Exception as e:
        print(f"[Email] PDF generation failed, sending without attachment: {e}")

    # ── Send ───────────────────────────────────────────────────────
    if not EMAIL_PASSWORD:
        print(f"[Email DEMO] Would send to {recipient_email} — Bill {bill_id} — Rs.{total:.2f}")
        return True   # demo mode: pretend success

    try:
        with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=10) as server:
            server.starttls()
            server.login(EMAIL_USER, EMAIL_PASSWORD)
            server.sendmail(FROM_EMAIL, recipient_email, msg.as_string())
        print(f"[Email] Sent to {recipient_email} — {bill_id}")
        return True
    except Exception as e:
        print(f"[Email] Send failed: {e}")
        return False
