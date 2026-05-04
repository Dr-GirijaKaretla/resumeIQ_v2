# Sprint 3 — Stripe Setup Guide

## Step 1 — Create Stripe Account
Go to stripe.com and create an account if you don't have one.
Start in TEST MODE (toggle in top left of dashboard).

---

## Step 2 — Create Products & Prices

In Stripe Dashboard → Products → Add Product:

### Product 1: Job Hunter
- Name: Job Hunter
- Pricing: Recurring · $9.00 USD · Monthly
- Copy the **Price ID** (looks like: price_1ABC...)
→ This goes in Railway as: STRIPE_JOB_HUNTER_PRICE

### Product 2: Career Pro
- Name: Career Pro
- Pricing: Recurring · $19.00 USD · Monthly
- Copy the **Price ID**
→ This goes in Railway as: STRIPE_CAREER_PRO_PRICE

---

## Step 3 — Get API Keys

Stripe Dashboard → Developers → API Keys:

- **Publishable key** (pk_test_...) → STRIPE_PUBLISHABLE_KEY
- **Secret key** (sk_test_...) → STRIPE_SECRET_KEY

---

## Step 4 — Set Up Webhook

Stripe Dashboard → Developers → Webhooks → Add Endpoint:

**Endpoint URL:**
```
https://your-app.up.railway.app/billing/webhook
```

**Events to listen for:**
- checkout.session.completed
- customer.subscription.updated
- customer.subscription.deleted
- invoice.payment_failed

Click **Add Endpoint** → copy the **Signing Secret** (whsec_...)
→ This goes in Railway as: STRIPE_WEBHOOK_SECRET

---

## Step 5 — Add All Variables to Railway

In Railway → your Flask service → Variables tab:

```
STRIPE_SECRET_KEY        = sk_test_...
STRIPE_PUBLISHABLE_KEY   = pk_test_...
STRIPE_WEBHOOK_SECRET    = whsec_...
STRIPE_JOB_HUNTER_PRICE  = price_...
STRIPE_CAREER_PRO_PRICE  = price_...
```

---

## Step 6 — Test the Flow

1. Go to /pricing on your live URL
2. Click "Start Job Hunter"
3. Use Stripe test card: **4242 4242 4242 4242** · Any future date · Any CVV
4. Complete checkout
5. You should be redirected to /billing/success
6. Your tier in the nav should now show "Job Hunter"
7. Check Railway logs — should see webhook event received

---

## Step 7 — Test Cancellation

1. Go to /profile → Manage Subscription
2. Cancel in the Stripe portal
3. Tier should revert to "Free" after the billing period

---

## Go Live Checklist

- [ ] Switch Stripe from Test Mode to Live Mode
- [ ] Replace test keys with live keys in Railway
- [ ] Update webhook URL (same URL, just live mode webhook)
- [ ] Test a real $9 charge with a real card
- [ ] Set up Stripe email receipts (Stripe Dashboard → Settings → Emails)

---

## Subscription Tier Logic

| Stripe Event | Action |
|---|---|
| checkout.session.completed | Upgrade user tier to purchased plan |
| customer.subscription.updated (active) | Keep/update tier |
| customer.subscription.deleted | Downgrade to free |
| invoice.payment_failed | Log warning (Stripe handles retry) |

Everything is handled automatically via webhooks in stripe_billing.py.
