"""
Application Tracker — Sprint 6
Tracks job applications with status, notes, follow-ups.
Also provides salary intelligence and JD red flag detection.
"""

# ── STATUS FLOW ────────────────────────────────────────────────────────────────
APPLICATION_STATUSES = [
    'saved',        # bookmarked, not yet applied
    'applied',      # application submitted
    'screening',    # recruiter phone screen scheduled/done
    'interview',    # technical/panel interview
    'offer',        # offer received
    'accepted',     # offer accepted
    'rejected',     # rejected at any stage
    'withdrawn',    # candidate withdrew
]

STATUS_LABELS = {
    'saved':      {'label': 'Saved',      'color': '#6b6b9a', 'icon': '🔖'},
    'applied':    {'label': 'Applied',    'color': '#6c5ce7', 'icon': '📤'},
    'screening':  {'label': 'Screening',  'color': '#ffd166', 'icon': '📞'},
    'interview':  {'label': 'Interview',  'color': '#f0a500', 'icon': '🎤'},
    'offer':      {'label': 'Offer',      'color': '#00d9a0', 'icon': '🎉'},
    'accepted':   {'label': 'Accepted',   'color': '#00b382', 'icon': '✅'},
    'rejected':   {'label': 'Rejected',   'color': '#ff6b6b', 'icon': '❌'},
    'withdrawn':  {'label': 'Withdrawn',  'color': '#888888', 'icon': '↩'},
}


# ── SALARY INTELLIGENCE ────────────────────────────────────────────────────────
SALARY_SYSTEM = """You are a compensation analyst with deep knowledge of tech and
data science salary benchmarks globally.
Return ONLY valid JSON. No markdown. No explanation."""

SALARY_PROMPT = """Provide salary intelligence for this role.

ROLE: {role}
COMPANY: {company}
LOCATION: {location}
CANDIDATE PROFILE:
- Career level: {career_level}
- Years experience: {years_experience}
- Key skills: {top_skills}

Return ONLY this JSON:
{{
  "currency": "USD",
  "location_used": "city, country",
  "base_salary": {{
    "min": 0,
    "mid": 0,
    "max": 0,
    "unit": "annual"
  }},
  "total_comp": {{
    "min": 0,
    "mid": 0,
    "max": 0,
    "note": "includes bonus/equity estimate"
  }},
  "market_position": "below market | at market | above market",
  "negotiation_room": "Low | Medium | High",
  "factors": [
    "factor that affects this salary range"
  ],
  "negotiation_tips": [
    "specific tip for negotiating this role"
  ],
  "confidence": "Low | Medium | High",
  "data_note": "brief note on data sources/limitations"
}}

Rules:
- Use realistic market data for the location and role seniority
- If location unknown, use major US tech hub as default and note it
- confidence: High if well-known role, Medium if niche, Low if very specialized
- factors: max 4 items
- negotiation_tips: max 3 items"""


def get_salary_intelligence(graph: dict, role: str,
                            company: str) -> tuple[dict, int]:
    """Get market salary range for a role."""
    from knowledge_graph import call_claude, extract_json
    import json

    identity   = graph.get('identity', {})
    skills     = graph.get('skills', {}).get('technical', {})
    top_skills = skills.get('expert', [])[:5] + skills.get('proficient', [])[:3]

    prompt = SALARY_PROMPT.format(
        role            = role,
        company         = company,
        location        = identity.get('location', 'Not specified'),
        career_level    = identity.get('career_level', 'mid'),
        years_experience= identity.get('years_experience', 0),
        top_skills      = ', '.join(top_skills) or 'Not specified',
    )

    raw, tokens = call_claude(
        messages   = [{'role': 'user', 'content': prompt}],
        system     = SALARY_SYSTEM,
        max_tokens = 800,
    )
    result = extract_json(raw)
    return result, tokens


# ── RED FLAG DETECTOR ──────────────────────────────────────────────────────────
RED_FLAG_SYSTEM = """You are an expert job seeker advocate who spots problematic
job postings that waste candidates' time or exploit them.
Return ONLY valid JSON. No markdown. No explanation."""

RED_FLAG_PROMPT = """Analyse this job description for red flags that a savvy job
seeker should know about before applying.

JOB DESCRIPTION:
{jd_text}

COMPANY: {company}
ROLE: {role}

Return ONLY this JSON:
{{
  "overall_rating": "Clean | Caution | Warning | Red Flag",
  "red_flags": [
    {{
      "flag": "short label",
      "detail": "what specifically triggered this concern",
      "severity": "Low | Medium | High",
      "advice": "what the candidate should do about it"
    }}
  ],
  "green_flags": [
    "positive signal found in the JD"
  ],
  "questions_to_ask": [
    "smart question to ask recruiter to clarify a concern"
  ],
  "posting_age_note": "comment on urgency language or if role seems stale",
  "summary": "one honest sentence about whether to apply"
}}

Red flag categories to check:
- Unrealistic requirements (10 yrs exp for junior role)
- Vague compensation ("competitive salary", no range)
- Too many responsibilities for one person (3+ roles in one)
- Urgency pressure ("must start immediately", "urgent hire")
- Exclusionary language (subtle bias indicators)
- Unpaid or exploitative elements
- Buzzword overload with no substance
- No mention of team size, reporting structure
- Generic copy-paste JD (not tailored to real role)
- Suspicious company signals

green_flags: positive things — specific team details, transparent comp, etc.
If no red flags found, return empty array and overall_rating = "Clean"."""


def detect_red_flags(jd_text: str, company: str,
                     role: str) -> tuple[dict, int]:
    """Detect red flags in a job description."""
    from knowledge_graph import call_claude, extract_json

    prompt = RED_FLAG_PROMPT.format(
        jd_text = jd_text[:3000],
        company = company,
        role    = role,
    )
    raw, tokens = call_claude(
        messages   = [{'role': 'user', 'content': prompt}],
        system     = RED_FLAG_SYSTEM,
        max_tokens = 1000,
    )
    result = extract_json(raw)
    return result, tokens


# ── COMPANY INTELLIGENCE ───────────────────────────────────────────────────────
COMPANY_SYSTEM = """You are a company research analyst helping job seekers.
Return ONLY valid JSON. No markdown. No explanation."""

COMPANY_PROMPT = """Provide a brief intelligence card for this company from
a job seeker's perspective.

COMPANY: {company}
ROLE BEING APPLIED TO: {role}
JD SNIPPET: {jd_snippet}

Return ONLY this JSON:
{{
  "company_type": "startup | scale-up | enterprise | agency | nonprofit | government",
  "estimated_size": "1-10 | 10-50 | 50-200 | 200-1000 | 1000-5000 | 5000+",
  "industry": "primary industry",
  "signals": {{
    "growth":       "growing | stable | declining | unknown",
    "culture_hint": "brief culture signal from JD language",
    "tech_stack":   ["technology mentioned or implied"]
  }},
  "what_to_research": [
    "specific thing to look up before interviewing"
  ],
  "glassdoor_tip": "what to search on Glassdoor for this company",
  "confidence": "High | Medium | Low"
}}

Base your analysis ONLY on what can be inferred from the JD and company name.
Do not invent specific financial data or headcount numbers.
confidence: High if well-known company, Medium if recognisable, Low if obscure."""


def get_company_intelligence(jd_text: str, company: str,
                             role: str) -> tuple[dict, int]:
    """Get company intelligence card."""
    from knowledge_graph import call_claude, extract_json

    prompt = COMPANY_PROMPT.format(
        company    = company,
        role       = role,
        jd_snippet = jd_text[:800],
    )
    raw, tokens = call_claude(
        messages   = [{'role': 'user', 'content': prompt}],
        system     = COMPANY_SYSTEM,
        max_tokens = 600,
    )
    result = extract_json(raw)
    return result, tokens
