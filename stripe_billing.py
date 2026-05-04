"""
Stripe Billing — Subscriptions, Webhooks, Portal
Sprint 3: Full monetization layer
"""
import stripe
from flask import Blueprint, request, jsonify, redirect, url_for, current_app
from flask_login import login_required, current_user
from models import db, User

billing_bp = Blueprint('billing', __name__, url_prefix='/billing')


def get_stripe():
    stripe.api_key = current_app.config['STRIPE_SECRET_KEY']
    return stripe


# ── CHECKOUT ──────────────────────────────────────────────────────────────────
@billing_bp.route('/checkout/<plan>', methods=['POST'])
@login_required
def checkout(plan):
    """
    Create a Stripe Checkout session for the given plan.
    plan: 'job_hunter' | 'career_pro'
    """
    s = get_stripe()

    price_map = {
        'job_hunter': current_app.config['STRIPE_JOB_HUNTER_PRICE'],
        'career_pro': current_app.config['STRIPE_CAREER_PRO_PRICE'],
    }

    price_id = price_map.get(plan)
    if not price_id:
        return jsonify({'error': 'Invalid plan.'}), 400

    app_url = current_app.config['APP_URL']

    try:
        # Get or create Stripe customer
        customer_id = current_user.stripe_customer_id
        if not customer_id:
            customer = s.Customer.create(
                email = current_user.email,
                name  = current_user.name,
                metadata = {'user_id': current_user.id}
            )
            current_user.stripe_customer_id = customer.id
            db.session.commit()
            customer_id = customer.id

        session = s.checkout.Session.create(
            customer            = customer_id,
            payment_method_types= ['card'],
            line_items          = [{'price': price_id, 'quantity': 1}],
            mode                = 'subscription',
            success_url         = f'{app_url}/billing/success?session_id={{CHECKOUT_SESSION_ID}}',
            cancel_url          = f'{app_url}/pricing',
            metadata            = {'user_id': current_user.id, 'plan': plan},
            subscription_data   = {
                'metadata': {'user_id': current_user.id, 'plan': plan}
            },
            allow_promotion_codes = True,
        )

        return jsonify({'success': True, 'checkout_url': session.url})

    except stripe.error.StripeError as e:
        current_app.logger.error(f'Stripe checkout error: {e}')
        return jsonify({'error': str(e)}), 500


# ── SUCCESS REDIRECT ──────────────────────────────────────────────────────────
@billing_bp.route('/success')
@login_required
def success():
    """Handle post-checkout redirect."""
    session_id = request.args.get('session_id')
    if session_id:
        s = get_stripe()
        try:
            session = s.checkout.Session.retrieve(session_id)
            if session.payment_status == 'paid':
                # Tier already updated via webhook, but do it here as fallback
                plan = session.metadata.get('plan', 'job_hunter')
                if current_user.tier == 'free':
                    current_user.tier = plan
                    db.session.commit()
        except Exception as e:
            current_app.logger.error(f'Success page error: {e}')

    from flask import render_template
    return render_template('billing_success.html', user=current_user)


# ── CUSTOMER PORTAL ───────────────────────────────────────────────────────────
@billing_bp.route('/portal')
@login_required
def portal():
    """Redirect to Stripe Customer Portal for subscription management."""
    s = get_stripe()

    if not current_user.stripe_customer_id:
        return redirect(url_for('pricing'))

    try:
        session = s.billing_portal.Session.create(
            customer   = current_user.stripe_customer_id,
            return_url = current_app.config['APP_URL'] + '/profile',
        )
        return redirect(session.url)

    except stripe.error.StripeError as e:
        current_app.logger.error(f'Portal error: {e}')
        from flask import render_template
        return render_template('error.html', code=500, message='Billing portal unavailable.'), 500


# ── WEBHOOK ───────────────────────────────────────────────────────────────────
@billing_bp.route('/webhook', methods=['POST'])
def webhook():
    """
    Handle Stripe webhook events.
    Keeps subscription tiers in sync with Stripe.
    """
    payload    = request.get_data(as_text=True)
    sig_header = request.headers.get('Stripe-Signature')
    webhook_secret = current_app.config['STRIPE_WEBHOOK_SECRET']

    s = get_stripe()

    try:
        event = s.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        current_app.logger.error('Webhook: Invalid payload')
        return jsonify({'error': 'Invalid payload'}), 400
    except stripe.error.SignatureVerificationError:
        current_app.logger.error('Webhook: Invalid signature')
        return jsonify({'error': 'Invalid signature'}), 400

    # ── Handle events ─────────────────────────────────────────────────────
    event_type = event['type']
    current_app.logger.info(f'Stripe webhook: {event_type}')

    if event_type == 'checkout.session.completed':
        _handle_checkout_completed(event['data']['object'])

    elif event_type == 'customer.subscription.updated':
        _handle_subscription_updated(event['data']['object'])

    elif event_type == 'customer.subscription.deleted':
        _handle_subscription_deleted(event['data']['object'])

    elif event_type == 'invoice.payment_failed':
        _handle_payment_failed(event['data']['object'])

    return jsonify({'received': True}), 200


def _handle_checkout_completed(session):
    """Subscription started — upgrade user tier."""
    user_id = session.get('metadata', {}).get('user_id')
    plan    = session.get('metadata', {}).get('plan', 'job_hunter')
    sub_id  = session.get('subscription')

    if not user_id:
        # Try to find by customer ID
        customer_id = session.get('customer')
        user = User.query.filter_by(stripe_customer_id=customer_id).first()
    else:
        user = User.query.get(user_id)

    if user:
        user.tier           = plan
        user.stripe_sub_id  = sub_id
        if session.get('customer'):
            user.stripe_customer_id = session['customer']
        db.session.commit()
        current_app.logger.info(f'User {user.email} upgraded to {plan}')
        # Send upgrade confirmation email
        try:
            from email_service import send_upgrade_confirmation
            send_upgrade_confirmation(user)
        except Exception as e:
            current_app.logger.warning(f'Upgrade email failed: {e}')


def _handle_subscription_updated(subscription):
    """Subscription changed — update tier accordingly."""
    user = User.query.filter_by(stripe_sub_id=subscription['id']).first()
    if not user:
        user = User.query.filter_by(
            stripe_customer_id=subscription['customer']
        ).first()

    if not user:
        return

    status = subscription['status']

    if status in ('active', 'trialing'):
        # Determine plan from price ID
        items = subscription.get('items', {}).get('data', [])
        if items:
            price_id = items[0]['price']['id']
            job_hunter_price = current_app.config['STRIPE_JOB_HUNTER_PRICE']
            career_pro_price = current_app.config['STRIPE_CAREER_PRO_PRICE']

            if price_id == career_pro_price:
                user.tier = 'career_pro'
            elif price_id == job_hunter_price:
                user.tier = 'job_hunter'

    elif status in ('canceled', 'unpaid', 'past_due', 'incomplete_expired'):
        user.tier          = 'free'
        user.stripe_sub_id = None

    db.session.commit()
    current_app.logger.info(f'User {user.email} subscription updated: {status} → tier={user.tier}')


def _handle_subscription_deleted(subscription):
    """Subscription cancelled — downgrade to free."""
    user = User.query.filter_by(stripe_sub_id=subscription['id']).first()
    if not user:
        user = User.query.filter_by(
            stripe_customer_id=subscription['customer']
        ).first()

    if user:
        user.tier          = 'free'
        user.stripe_sub_id = None
        db.session.commit()
        current_app.logger.info(f'User {user.email} downgraded to free')
        try:
            from email_service import send_downgrade_notice
            send_downgrade_notice(user)
        except Exception as e:
            current_app.logger.warning(f'Downgrade email failed: {e}')


def _handle_payment_failed(invoice):
    """Payment failed — log it. Stripe handles retry/cancellation."""
    customer_id = invoice.get('customer')
    user = User.query.filter_by(stripe_customer_id=customer_id).first()
    if user:
        current_app.logger.warning(f'Payment failed for user {user.email}')
        # Could send an email here via Resend
