#!/usr/bin/env python3
# server.py — EliteKits backend: receives orders and sends confirmation emails
# Usage: set SMTP_* env vars, then:  python server.py
# Required env vars: SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, SELLER_EMAIL

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from flask import Flask, request, jsonify
from flask_cors import CORS

SMTP_HOST    = os.getenv('SMTP_HOST',    'smtp.mail.yahoo.com')
SMTP_PORT    = int(os.getenv('SMTP_PORT', '587'))
SMTP_USER    = os.getenv('SMTP_USER',    '')
SMTP_PASS    = os.getenv('SMTP_PASS',    '')
SELLER_EMAIL = os.getenv('SELLER_EMAIL', 'cornictitouan@yahoo.com')
FROM_EMAIL   = os.getenv('FROM_EMAIL',   SMTP_USER or SELLER_EMAIL)

app = Flask(__name__, static_folder='.', static_url_path='/')
CORS(app, resources={r'/api/*': {'origins': '*'}})

PRICES = {
    'fan':      25,
    'pro':      30,
    'long':     30,
    'pro_long': 35,
    'enfant':   25,
    'retro':    30,
    'flocage':  5,
    'delivery': 5,
}


@app.get('/')
def root():
    return app.send_static_file('index.html')


@app.post('/api/order')
def order():
    data = request.get_json(force=True)
    if not data:
        return jsonify({'error': 'invalid json'}), 400

    ig             = (data.get('instagram') or '').strip()
    customer_email = (data.get('customerEmail') or '').strip()
    items          = data.get('items', [])
    totals         = data.get('totals', {})

    if not ig or not items:
        return jsonify({'error': 'missing instagram or items'}), 400

    offer_applied = bool(totals.get('offerApplied')) or len(items) >= 2

    # ── Build email body ──────────────────────────────────────────────────────
    lines = [
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '       NOUVELLE COMMANDE ELITEKITS',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
        '',
        f'Instagram   : {ig}',
    ]
    if customer_email:
        lines.append(f'Email client: {customer_email}')
    lines.append('')

    for i, it in enumerate(items, 1):
        team = it.get('team') or 'Maillot'
        typ  = it.get('type') or 'fan'
        size = it.get('size') or '—'
        base = PRICES.get(typ, PRICES['fan'])
        floc_cost = 0 if offer_applied else (PRICES['flocage'] if it.get('flocage') else 0)

        lines.append(f'  #{i}  {team} | {typ.upper()} | Taille {size}')
        if it.get('flocage'):
            label = 'offert ✓' if offer_applied else f'+{PRICES["flocage"]}€'
            lines.append(f'       Flocage : {it.get("flocName") or "—"} #{it.get("flocNumber") or "—"} ({label})')
        lines.append(f'       Photo   : {request.host_url.rstrip("/")}/{it.get("src", "")}')
        lines.append(f'       Prix    : {base + floc_cost}€')
        lines.append('')

    lines += [
        '──────────────────────────────',
        f'Sous-total : {totals.get("subtotal", 0)}€',
        f'Flocage    : {totals.get("flocageTotal", 0)}€' + (' (offert ✓)' if offer_applied else ''),
        f'Livraison  : {totals.get("delivery", 0)}€',
        f'TOTAL      : {totals.get("total", 0)}€',
        '━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━',
    ]
    body = '\n'.join(lines)

    errors = []

    # ── Email to seller ───────────────────────────────────────────────────────
    try:
        send_email(
            to_email=SELLER_EMAIL,
            subject=f'[EliteKits] Nouvelle commande — @{ig}',
            body=body,
        )
    except Exception as exc:
        errors.append(f'seller: {exc}')

    # ── Confirmation email to customer ────────────────────────────────────────
    if customer_email:
        customer_body_lines = [
            'Bonjour !',
            '',
            'Merci pour votre commande EliteKits. Voici le récapitulatif :',
            '',
        ] + lines[4:] + [
            '',
            'Nous vous recontacterons très rapidement sur Instagram pour',
            'confirmer les détails et les modalités de paiement.',
            '',
            'Instagram : @elitekits.jersey',
            '',
            'Merci de votre confiance !',
            '— L\'équipe EliteKits',
        ]
        try:
            send_email(
                to_email=customer_email,
                subject='Confirmation de votre commande EliteKits',
                body='\n'.join(customer_body_lines),
            )
        except Exception as exc:
            errors.append(f'customer: {exc}')

    if errors and not customer_email:
        # If only seller email failed, return error
        return jsonify({'error': '; '.join(errors)}), 500

    return jsonify({'ok': True, 'warnings': errors if errors else None})


def send_email(to_email: str, subject: str, body: str):
    if not (SMTP_HOST and SMTP_PORT and FROM_EMAIL and to_email):
        raise RuntimeError('SMTP configuration incomplete — set SMTP_* env vars')
    msg = MIMEMultipart()
    msg['From']    = FROM_EMAIL
    msg['To']      = to_email
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
