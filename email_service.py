"""
Email Service — Sprint 4
Transactional emails via Resend.com
"""
import os
import json
from flask import current_app


def send_email(to: str, subject: str, html: str) -> bool:
    """
    Send an email via Resend API.
    Returns True on success, False on failure.
    """
    api_key = current_app.config.get('RESEND_API_KEY', '')
    from_email = current_app.config.get('FROM_EMAIL', 'hello@resumeiq.app')

    if not api_key:
        current_app.logger.warning('RESEND_API_KEY not set — email not sent')
        return False

    try:
        import resend
        resend.api_key = api_key
        resend.Emails.send({
            'from':    from_email,
            'to':      [to],
            'subject': subject,
            'html':    html,
        })
        return True
    except Exception as e:
        current_app.logger.error(f'Email send error: {e}')
        return False


# ── EMAIL TEMPLATES ───────────────────────────────────────────────────────────

def _base_html(content: str, preview: str = '') -> str:
    """Wrap content in base email HTML template."""
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ResumeIQ</title>
<style>
  body {{ margin: 0; padding: 0; background: #f5f5f7; font-family: -apple-system, Arial, sans-serif; }}
  .wrapper {{ max-width: 560px; margin: 32px auto; background: #ffffff; border-radius: 12px; overflow: hidden; box-shadow: 0 2px 12px rgba(0,0,0,.08); }}
  .header {{ background: #0f0f1a; padding: 24px 32px; }}
  .logo {{ font-size: 20px; font-weight: 800; color: #ffffff; letter-spacing: -0.5px; }}
  .logo span {{ color: #6c5ce7; }}
  .body {{ padding: 32px; color: #1a1a2e; }}
  .body h2 {{ font-size: 20px; font-weight: 700; margin: 0 0 12px; color: #1a1a2e; }}
  .body p {{ font-size: 14px; line-height: 1.65; color: #555; margin: 0 0 16px; }}
  .btn {{ display: inline-block; background: #6c5ce7; color: #ffffff !important; text-decoration: none; font-weight: 700; font-size: 14px; padding: 12px 28px; border-radius: 8px; margin: 8px 0; }}
  .highlight {{ background: #f0f4ff; border-left: 4px solid #6c5ce7; padding: 12px 16px; border-radius: 4px; font-size: 13px; color: #333; margin: 16px 0; }}
  .footer {{ background: #f9f9fb; padding: 20px 32px; font-size: 11px; color: #aaa; text-align: center; }}
  .footer a {{ color: #888; text-decoration: none; }}
</style>
</head>
<body>
{'<div style="display:none;max-height:0;overflow:hidden;">' + preview + '</div>' if preview else ''}
<div class="wrapper">
  <div class="header">
    <div class="logo">Resume<span>IQ</span></div>
  </div>
  <div class="body">{content}</div>
  <div class="footer">
    ResumeIQ · AI-Powered Career Intelligence<br>
    <a href="https://resumeiq.app/privacy">Privacy Policy</a> ·
    <a href="https://resumeiq.app/billing/portal">Manage Subscription</a>
  </div>
</div>
</body>
</html>'''


def send_welcome_email(user) -> bool:
    """Send welcome email to new users after Google sign-in."""
    app_url = current_app.config.get('APP_URL', 'https://resumeiq.app')
    content = f'''
    <h2>Welcome to ResumeIQ, {user.name.split()[0]}! 🎉</h2>
    <p>You're all set. Here's how to get your first application pack in under 2 minutes:</p>
    <div class="highlight">
      <strong>Step 1:</strong> Upload your resume once — we build your knowledge graph<br>
      <strong>Step 2:</strong> Paste any job URL — we fetch the description automatically<br>
      <strong>Step 3:</strong> Get your tailored resume, STAR cover letter, and recruiter email
    </div>
    <p>We only help you apply when you have a genuine chance — our 65% match gate protects you from wasted applications.</p>
    <a href="{app_url}/setup" class="btn">Build My Profile →</a>
    <p style="margin-top:20px;font-size:12px;color:#aaa;">
      Questions? Just reply to this email.
    </p>'''
    return send_email(
        to      = user.email,
        subject = 'Welcome to ResumeIQ — let\'s get you the interview',
        html    = _base_html(content, 'Your AI career intelligence platform is ready.')
    )


def send_upgrade_confirmation(user) -> bool:
    """Send confirmation after successful subscription upgrade."""
    app_url = current_app.config.get('APP_URL', 'https://resumeiq.app')

    features = {
        'job_hunter': [
            'Unlimited analyses per month',
            'Resume rewrite — tailored PDF for every job',
            'STAR cover letter — Situation Task Action Result',
            'Recruiter email / LinkedIn note',
            'Full keyword intelligence with placement guidance',
        ],
        'career_pro': [
            'Everything in Job Hunter',
            'PDF + DOCX download',
            'Cover letter tone selector',
            'Interview prep pack',
            'LinkedIn profile optimizer',
            'Unlimited application history',
        ]
    }

    tier_label = user.tier_label
    feature_list = ''.join(
        f'<li style="margin-bottom:4px">{f}</li>'
        for f in features.get(user.tier, features['job_hunter'])
    )

    content = f'''
    <h2>You're now on {tier_label}! 🚀</h2>
    <p>Your subscription is active. Here's what's now unlocked:</p>
    <div class="highlight">
      <ul style="margin:0;padding-left:16px;font-size:13px;color:#333;line-height:1.7">
        {feature_list}
      </ul>
    </div>
    <a href="{app_url}/app" class="btn">Start Applying →</a>
    <p style="margin-top:20px;font-size:12px;color:#aaa;">
      To manage or cancel your subscription, visit
      <a href="{app_url}/billing/portal" style="color:#6c5ce7">Billing Portal</a>.
    </p>'''
    return send_email(
        to      = user.email,
        subject = f'You\'re on ResumeIQ {tier_label} — welcome!',
        html    = _base_html(content, f'Your {tier_label} subscription is now active.')
    )


def send_analysis_summary(user, analysis) -> bool:
    """
    Send a brief analysis summary email after a successful analysis.
    Only sent if user is on Job Hunter or Career Pro.
    """
    if user.tier == 'free':
        return False

    app_url  = current_app.config.get('APP_URL', 'https://resumeiq.app')
    score    = analysis.overall_score or 0
    grade    = analysis.grade or '—'
    company  = analysis.display_company
    role     = analysis.display_title
    ana_id   = analysis.id

    score_color = (
        '#00d9a0' if score >= 80 else
        '#6c5ce7' if score >= 60 else
        '#ffd166' if score >= 40 else '#ff6b6b'
    )

    content = f'''
    <h2>Analysis complete — {role} at {company}</h2>
    <div style="text-align:center;margin:20px 0">
      <div style="font-size:52px;font-weight:800;color:{score_color};line-height:1">{score}</div>
      <div style="font-size:14px;color:#888;margin-top:4px">Match Score · Grade {grade}</div>
    </div>
    <p>Your application pack is ready — tailored resume, STAR cover letter, and recruiter email are waiting in your dashboard.</p>
    <a href="{app_url}/history/{ana_id}" class="btn">View Full Analysis →</a>
    <p style="margin-top:16px;font-size:12px;color:#aaa;">
      Remember: Every word in your resume can be defended in an interview.
      ResumeIQ never fabricates skills or experience.
    </p>'''
    return send_email(
        to      = user.email,
        subject = f'Your match score: {score}/100 — {role} at {company}',
        html    = _base_html(content, f'Match score {score}/100 · {grade} · {company}')
    )


def send_downgrade_notice(user) -> bool:
    """Send notice when subscription is cancelled/downgraded."""
    app_url = current_app.config.get('APP_URL', 'https://resumeiq.app')
    content = f'''
    <h2>Subscription cancelled</h2>
    <p>Hi {user.name.split()[0]}, your ResumeIQ subscription has been cancelled.</p>
    <p>You've been moved to the Free plan — you can still run 3 analyses per month and access your knowledge graph.</p>
    <div class="highlight">
      Your profile and analysis history are safely stored. If you decide to resubscribe, everything will be exactly where you left it.
    </div>
    <a href="{app_url}/pricing" class="btn">Resubscribe →</a>
    <p style="margin-top:16px;font-size:12px;color:#aaa;">
      We'd love to know why you cancelled — just reply to this email.
    </p>'''
    return send_email(
        to      = user.email,
        subject = 'Your ResumeIQ subscription has been cancelled',
        html    = _base_html(content, 'You\'ve been moved to the free plan.')
    )
