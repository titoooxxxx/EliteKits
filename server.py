#!/usr/bin/env python3
# server.py - Minimal backend to receive orders and send an email to the seller
# Run: set SELLER_EMAIL, SMTP_* env vars, then:  python server.py

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify

SMTP_HOST = os.getenv('SMTP_HOST', 'smtp.mail.yahoo.com')
SMTP_PORT = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER = os.getenv('SMTP_USER', 'cornictitouan@yahoo.com')
SMTP_PASS = os.getenv('SMTP_PASS', 'ltmdqedcjzxfdztk')
SELLER_EMAIL = os.getenv('SELLER_EMAIL', 'cornictitouan@yahoo.com')
FROM_EMAIL = os.getenv('FROM_EMAIL', SMTP_USER or SELLER_EMAIL)

app = Flask(__name__, static_folder='.', static_url_path='/')

@app.get('/')
def root():
    return app.send_static_file('index.html')

@app.post('/api/order')
def order():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'invalid json'}), 400
    ig = data.get('instagram')
    items = data.get('items', [])
    totals = data.get('totals', {})
    if not ig or not items:
        return jsonify({'error': 'missing instagram or items'}), 400

    PRICES = {
        'fan': 25,
        'pro': 30,
        'long': 30,
        'pro_long': 35,
        'enfant': 25,
        'retro': 30,
        'flocage': 5,
        'delivery': 5,
    }

    def price_for_type(t: str) -> int:
        return PRICES.get(t or 'fan', PRICES['fan'])

    offer_applied = bool(totals.get('offerApplied')) or len(items) >= 2

    subject = 'Nouvelle commande EliteKits'
    body_lines = [f'Instagram: {ig}', '']
    for i, it in enumerate(items, 1):
        team = it.get('team') or 'Maillot'
        typ = it.get('type') or 'fan'
        size = it.get('size') or '-'
        base = price_for_type(typ)
        floc = 0
        if it.get('flocage'):
            floc = 0 if offer_applied else PRICES['flocage']
        title = f"#{i} {team} | {typ} | {size}"
        body_lines.append(title)
        if it.get('flocage'):
            label = 'offert' if offer_applied else '+5€'
            body_lines.append(f"  Flocage: {it.get('flocName') or '-'} #{it.get('flocNumber') or '-'} ({label})")
        src = it.get('src', '')
        body_lines.append(f"  Photo: {request.host_url.rstrip('/')}/{src}")
        body_lines.append(f"  Prix article: {base + floc}€ (base {base}€{', flocage offert' if (it.get('flocage') and offer_applied) else (', +5€ flocage' if it.get('flocage') else '')})")
    body_lines += [
        '',
        f"Sous-total: {totals.get('subtotal', 0)}€",
        f"Flocage: {totals.get('flocageTotal', 0)}€{' (offert)' if offer_applied else ''}",
        f"Livraison: {totals.get('delivery', 0)}€",
        f"TOTAL: {totals.get('total', 0)}€",
    ]
    body = "\n".join(body_lines)

    try:
        send_email(SELLER_EMAIL, subject, body)
        return jsonify({'ok': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


def send_email(to_email: str, subject: str, body: str):
    if not (SMTP_HOST and SMTP_PORT and FROM_EMAIL and to_email):
        raise RuntimeError('SMTP configuration missing')
    msg = MIMEMultipart()
    msg['From'] = FROM_EMAIL
    msg['To'] = to_email
    msg['Subject'] = subject
    msg.attach(MIMEText(body, 'plain', 'utf-8'))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        if SMTP_USER and SMTP_PASS:
            server.login(SMTP_USER, SMTP_PASS)
        server.send_message(msg)


if __name__ == '__main__':
    port = int(os.getenv('PORT', '5000'))
    app.run(host='0.0.0.0', port=port)
