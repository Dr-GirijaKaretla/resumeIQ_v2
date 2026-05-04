"""
Weekly Job Digest — Sprint 6
Generates a personalised Monday morning email with
pre-scored job matches based on the user's knowledge graph.

Architecture:
- Scheduler calls send_weekly_digest_all_users() on Monday 8am UTC
- Uses Claude to find + pre-score relevant roles
- Sends via Resend email service
- Career Pro tier only
"""
import json


DIGEST_SYSTEM = """You are a job search assistant that finds relevant job
opportunities based on a candidate's profile.
Return ONLY valid JSON. No markdown. No explanation."""

DIGEST_PROMPT = """Based on this candidate's knowledge graph, generate 5 realistic
job opportunities they should apply to this week.

CANDIDATE KNOWLEDGE GRAPH:
{knowledge_graph}

Generate 5 REALISTIC job listings that match their profile.
These should be plausible roles at real companies in their likely location/remote.

Return ONLY this JSON:
{{
  "digest_date": "Monday date string",
  "candidate_name": "first name only",
  "jobs": [
    {{
      "title": "exact job title",
      "company": "real company name that hires for this type of role",
      "location": "city or Remote",
      "estimated_match": 0,
      "why_matched": "one sentence why this fits the profile",
      "key_requirements": ["req1", "req2", "req3"],
      "search_query": "exact search string to find this on LinkedIn/Indeed",
      "apply_tip": "one specific tip for this application"
    }}
  ],
  "skill_spotlight": {{
    "skill": "most in-demand skill from their profile this week",
    "trend": "why this skill is hot right now",
    "learning_tip": "one resource to deepen this skill"
  }},
  "weekly_goal": "one specific actionable goal for their job search this week",
  "motivation": "one genuine encouraging sentence personalised to their profile"
}}

Rules:
- estimated_match: realistic 65-95 based on how well profile fits
- companies: use real well-known companies that actually hire for these roles
- key_requirements: 3 items from what those companies typically require
- search_query: something they can paste directly into LinkedIn Jobs"""


def build_digest_content(graph: dict) -> tuple[dict, int]:
    """
    Build weekly digest content for a user.
    Returns (digest_dict, tokens_used).
    """
    from knowledge_graph import call_claude, extract_json

    focused = {
        'identity':      graph.get('identity', {}),
        'skills':        graph.get('skills', {}),
        'experience':    [
            {'role': e.get('role'), 'company': e.get('company'),
             'years': e.get('years'), 'keywords': e.get('keywords', [])[:5]}
            for e in graph.get('experience', [])[:3]
        ],
        'projects':      [
            {'name': p.get('name'), 'keywords': p.get('keywords', [])[:4],
             'transferable_to': p.get('transferable_to', [])[:3]}
            for p in graph.get('projects', [])[:3]
        ],
        'certifications': graph.get('certifications', [])[:3],
    }

    prompt = DIGEST_PROMPT.format(
        knowledge_graph=json.dumps(focused, indent=2)
    )
    raw, tokens = call_claude(
        messages   = [{'role': 'user', 'content': prompt}],
        system     = DIGEST_SYSTEM,
        max_tokens = 2000,
    )
    result = extract_json(raw)
    return result, tokens


def build_digest_email_html(digest: dict, app_url: str) -> str:
    """Build the weekly digest HTML email."""

    def sc(s):
        if s >= 80: return '#00d9a0'
        if s >= 65: return '#6c5ce7'
        return '#ffd166'

    name  = digest.get('candidate_name', 'there')
    jobs  = digest.get('jobs', [])
    spot  = digest.get('skill_spotlight', {})
    goal  = digest.get('weekly_goal', '')
    motiv = digest.get('motivation', '')

    jobs_html = ''
    for j in jobs:
        score = j.get('estimated_match', 75)
        color = sc(score)
        reqs  = ''.join(
            f'<span style="display:inline-block;background:#1a1a2e;color:#888;'
            f'font-size:11px;padding:2px 8px;border-radius:4px;margin:2px">'
            f'{r}</span>'
            for r in j.get('key_requirements', [])
        )
        jobs_html += f'''
        <div style="background:#0f0f1a;border:1px solid #252538;border-radius:10px;
                    padding:16px;margin-bottom:10px">
          <div style="display:flex;justify-content:space-between;
                      align-items:flex-start;gap:10px;flex-wrap:wrap">
            <div>
              <div style="font-size:14px;font-weight:700;color:#e8e8f5;margin-bottom:2px">
                {j.get("title","")}
              </div>
              <div style="font-size:12px;color:#6b6b9a">
                {j.get("company","")} · {j.get("location","")}
              </div>
            </div>
            <div style="text-align:center;flex-shrink:0">
              <div style="font-size:22px;font-weight:800;color:{color};line-height:1">
                {score}
              </div>
              <div style="font-size:9px;color:#6b6b9a;text-transform:uppercase;
                          letter-spacing:1px">match</div>
            </div>
          </div>
          <div style="font-size:12px;color:#6b6b9a;margin:8px 0;line-height:1.55">
            {j.get("why_matched","")}
          </div>
          <div style="margin-bottom:8px">{reqs}</div>
          <div style="font-size:11px;color:#6c5ce7;font-style:italic">
            💡 {j.get("apply_tip","")}
          </div>
          <div style="margin-top:10px">
            <a href="https://www.linkedin.com/jobs/search/?keywords={j.get('search_query','').replace(' ','+')}"
               style="background:#6c5ce7;color:#fff;text-decoration:none;
                      font-size:11px;padding:5px 12px;border-radius:6px;
                      font-weight:700;display:inline-block">
              Search on LinkedIn →
            </a>
          </div>
        </div>'''

    spotlight_html = ''
    if spot:
        spotlight_html = f'''
        <div style="background:#0f0f1a;border:1px solid #252538;border-radius:10px;
                    padding:16px;margin-bottom:20px">
          <div style="font-size:11px;color:#ffd166;font-family:monospace;
                      text-transform:uppercase;letter-spacing:1px;margin-bottom:6px">
            ⚡ Skill Spotlight
          </div>
          <div style="font-size:14px;font-weight:700;color:#e8e8f5;margin-bottom:4px">
            {spot.get("skill","")}
          </div>
          <div style="font-size:12px;color:#6b6b9a;margin-bottom:6px;line-height:1.55">
            {spot.get("trend","")}
          </div>
          <div style="font-size:11px;color:#6c5ce7">
            📚 {spot.get("learning_tip","")}
          </div>
        </div>'''

    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
</head>
<body style="margin:0;padding:0;background:#080810;font-family:-apple-system,Arial,sans-serif">
<div style="max-width:560px;margin:0 auto;padding:20px">

  <!-- Header -->
  <div style="background:#0f0f1a;border-radius:12px;padding:20px 24px;
              margin-bottom:16px;border:1px solid #252538">
    <div style="display:flex;justify-content:space-between;align-items:center">
      <div style="font-size:18px;font-weight:800;color:#e8e8f5">
        Resume<span style="color:#6c5ce7">IQ</span>
      </div>
      <div style="font-family:monospace;font-size:10px;color:#6b6b9a;
                  text-transform:uppercase;letter-spacing:1px">
        Weekly Digest
      </div>
    </div>
  </div>

  <!-- Greeting -->
  <div style="background:#0f0f1a;border-radius:12px;padding:20px 24px;
              margin-bottom:16px;border:1px solid #252538">
    <div style="font-size:16px;font-weight:700;color:#e8e8f5;margin-bottom:8px">
      Good Monday, {name}! 👋
    </div>
    <div style="font-size:13px;color:#6b6b9a;line-height:1.65">
      Here are 5 roles that match your profile this week —
      pre-scored and ready to apply.
    </div>
    {f'<div style="margin-top:10px;font-size:12px;color:#6c5ce7;font-style:italic">{motiv}</div>' if motiv else ''}
  </div>

  <!-- Weekly Goal -->
  {f'''<div style="background:rgba(108,92,231,.08);border:1px solid rgba(108,92,231,.25);
              border-radius:10px;padding:12px 16px;margin-bottom:16px">
    <div style="font-size:10px;color:#6c5ce7;font-family:monospace;
                text-transform:uppercase;letter-spacing:1px;margin-bottom:4px">
      🎯 This Week\'s Goal
    </div>
    <div style="font-size:13px;color:#e8e8f5">{goal}</div>
  </div>''' if goal else ''}

  <!-- Jobs -->
  <div style="font-size:11px;color:#6b6b9a;font-family:monospace;
              text-transform:uppercase;letter-spacing:1px;margin-bottom:8px">
    5 Matched Roles
  </div>
  {jobs_html}

  <!-- Skill Spotlight -->
  {spotlight_html}

  <!-- CTA -->
  <div style="text-align:center;margin-bottom:20px">
    <a href="{app_url}/app"
       style="background:linear-gradient(135deg,#6c5ce7,#9d8ef5);
              color:#fff;text-decoration:none;font-size:14px;font-weight:700;
              padding:13px 32px;border-radius:10px;display:inline-block">
      ✦ Open ResumeIQ Dashboard →
    </a>
  </div>

  <!-- Footer -->
  <div style="text-align:center;font-size:11px;color:#444;line-height:1.6">
    ResumeIQ Weekly Digest · Career Pro feature<br>
    <a href="{app_url}/profile" style="color:#6c5ce7">Manage preferences</a> ·
    <a href="{app_url}/billing/portal" style="color:#6c5ce7">Manage subscription</a>
  </div>
</div>
</body>
</html>'''


def send_digest_to_user(user, app_url: str) -> bool:
    """
    Build and send weekly digest to a single Career Pro user.
    Called by the scheduler.
    """
    from flask import current_app
    from email_service import send_email

    if user.tier != 'career_pro':
        return False
    if not user.knowledge_graph:
        return False

    try:
        digest, _ = build_digest_content(user.knowledge_graph.graph)
        html = build_digest_email_html(digest, app_url)

        name = user.name.split()[0]
        return send_email(
            to      = user.email,
            subject = f'Your 5 job matches this week, {name} 🎯',
            html    = html,
        )
    except Exception as e:
        current_app.logger.error(f'Digest error for {user.email}: {e}')
        return False


def send_weekly_digest_all_users():
    """
    Send digest to all Career Pro users.
    Call this from a cron endpoint on Monday mornings.
    """
    from flask import current_app
    from models import User

    app_url  = current_app.config.get('APP_URL', 'https://resumeiq.app')
    pro_users = User.query.filter_by(tier='career_pro').all()

    sent = failed = 0
    for user in pro_users:
        ok = send_digest_to_user(user, app_url)
        if ok:
            sent += 1
        else:
            failed += 1

    current_app.logger.info(
        f'Weekly digest: {sent} sent, {failed} failed '
        f'out of {len(pro_users)} Career Pro users'
    )
    return {'sent': sent, 'failed': failed, 'total': len(pro_users)}
