"""
Knowledge Graph Engine
Handles extraction from resume text and matching against JD.
"""
import re
import json
import anthropic
from flask import current_app


# ── JSON EXTRACTION ────────────────────────────────────────────────────────────
def extract_json(raw: str) -> dict:
    """Multi-strategy JSON extractor — robust against any Claude output format."""
    text = re.sub(r'```(?:json)?', '', raw, flags=re.IGNORECASE).strip()
    try:
        return json.loads(text)
    except Exception:
        pass
    first, last = text.find('{'), text.rfind('}')
    if first != -1 and last > first:
        try:
            return json.loads(text[first:last + 1])
        except Exception:
            pass
    depth, start = 0, -1
    for i, ch in enumerate(text):
        if ch == '{':
            if depth == 0:
                start = i
            depth += 1
        elif ch == '}':
            depth -= 1
            if depth == 0 and start != -1:
                try:
                    return json.loads(text[start:i + 1])
                except Exception:
                    start = -1
    raise ValueError('Could not parse JSON from response.')


# ── CLAUDE CALL ────────────────────────────────────────────────────────────────
def call_claude(messages: list, system: str = None,
                max_tokens: int = 4000) -> tuple[str, int]:
    """Call Claude and return (response_text, tokens_used)."""
    client = anthropic.Anthropic(
        api_key=current_app.config['ANTHROPIC_API_KEY']
    )
    kwargs = dict(
        model=current_app.config['CLAUDE_MODEL'],
        max_tokens=max_tokens,
        messages=messages
    )
    if system:
        kwargs['system'] = system
    response = client.messages.create(**kwargs)
    text = ''.join(b.text for b in response.content if hasattr(b, 'text'))
    tokens = response.usage.input_tokens + response.usage.output_tokens
    return text, tokens


# ── KNOWLEDGE GRAPH EXTRACTION ─────────────────────────────────────────────────
EXTRACTION_SYSTEM = """You are a resume parsing API. 
Extract structured career data from the resume and return ONLY valid JSON.
No markdown, no explanation, no surrounding text.
Be accurate — only extract what is actually in the resume.
Never invent or infer information not present."""

EXTRACTION_PROMPT = """Extract the following structured knowledge graph from this resume.
Return ONLY a valid JSON object matching this exact schema.
Keep all string values under 200 characters. Arrays max 8 items each.

RESUME TEXT:
{resume_text}

JSON SCHEMA TO FILL:
{{
  "identity": {{
    "name": "full name",
    "location": "city, country",
    "email": "email if present",
    "career_level": "fresher|mid|senior",
    "years_experience": 0,
    "target_roles": ["role1", "role2"]
  }},
  "education": {{
    "degree": "highest degree name",
    "institution": "university name",
    "year": 2024,
    "relevant_coursework": []
  }},
  "certifications": [
    "Certification Name (Year)"
  ],
  "experience": [
    {{
      "company": "company name",
      "role": "job title",
      "duration": "2022-2025",
      "years": 3,
      "key_achievements": ["achievement with metric"],
      "keywords": ["skill1", "technology1"]
    }}
  ],
  "projects": [
    {{
      "name": "project name",
      "summary": "what was built and how, under 180 chars",
      "keywords": ["tech1", "method1"],
      "skills_demonstrated": ["skill1"],
      "impact": "measurable outcome",
      "impact_score": 7,
      "transferable_to": ["data scientist", "ml engineer"]
    }}
  ],
  "skills": {{
    "technical": {{
      "expert": ["skill1"],
      "proficient": ["skill2"],
      "familiar": ["skill3"]
    }},
    "soft": ["leadership"],
    "tools": ["tool1"]
  }}
}}

Rules:
- career_level: "fresher" if <2 years, "mid" if 2-8 years, "senior" if 8+ years
- impact_score: 1-10 based on clarity and magnitude of impact stated
- relevant_coursework: ONLY include if career_level is "fresher"
- If a field has no data in the resume, use empty string or empty array
- Extract target_roles from objective/summary section if present, otherwise infer from experience"""


def extract_knowledge_graph(resume_text: str) -> tuple[dict, int]:
    """
    Extract structured knowledge graph from resume text.
    Returns (knowledge_graph_dict, tokens_used).
    One-time operation at profile creation.
    """
    prompt = EXTRACTION_PROMPT.format(resume_text=resume_text[:6000])
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=EXTRACTION_SYSTEM,
        max_tokens=2000
    )
    graph = extract_json(raw)
    return graph, tokens


# ── STAGE 1 — KEYWORD PRE-CHECK (FREE, NO API) ─────────────────────────────────
def keyword_pre_check(user_keywords: list, jd_text: str) -> tuple[int, list, list]:
    """
    Pure string matching — no API call, instant, free.
    Returns (overlap_percentage, matched_keywords, missing_common_terms).
    """
    jd_lower = jd_text.lower()
    jd_words = set(re.findall(r'\b[a-z][a-z0-9+#.-]{1,30}\b', jd_lower))

    matched = []
    for kw in user_keywords:
        if kw.lower() in jd_lower:
            matched.append(kw)

    if not user_keywords:
        return 0, [], []

    overlap = round(len(matched) / max(len(user_keywords), 1) * 100)

    # Find important JD terms not in user keywords
    important_jd_terms = [
        w for w in jd_words
        if len(w) > 4 and w not in [k.lower() for k in user_keywords]
        and w not in STOP_WORDS
    ][:10]

    return overlap, matched, important_jd_terms


# ── STAGE 2 — AI PRE-SCORE ────────────────────────────────────────────────────
PRE_SCORE_SYSTEM = """You are a resume matching API. 
Return ONLY a valid JSON object. No markdown, no explanation."""

PRE_SCORE_PROMPT = """Score how well this candidate profile matches this job description.

CANDIDATE PROFILE (compact):
{compact_profile}

JOB DESCRIPTION:
{jd_text}

Return ONLY this JSON:
{{
  "score": <integer 0-100>,
  "career_level_detected": "<fresher|mid|senior|career_change>",
  "top_matches": ["skill or experience that matches well"],
  "critical_gaps": ["important requirement clearly missing"],
  "verdict": "one sentence honest assessment under 100 chars"
}}"""


def ai_pre_score(graph: dict, jd_text: str) -> tuple[dict, int]:
    """
    Stage 2: AI pre-score using compact profile.
    Returns (pre_score_result, tokens_used).
    Cost: ~$0.0005 per call.
    """
    compact = _build_compact_profile(graph)
    prompt = PRE_SCORE_PROMPT.format(
        compact_profile=json.dumps(compact, indent=2),
        jd_text=jd_text[:2000]
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=PRE_SCORE_SYSTEM,
        max_tokens=300
    )
    result = extract_json(raw)
    return result, tokens


def _build_compact_profile(graph: dict) -> dict:
    """Build a token-efficient compact profile for pre-scoring (~300 tokens)."""
    identity = graph.get('identity', {})
    skills = graph.get('skills', {})
    return {
        'career_level':      identity.get('career_level', 'mid'),
        'years_experience':  identity.get('years_experience', 0),
        'target_roles':      identity.get('target_roles', []),
        'top_skills':        skills.get('technical', {}).get('expert', [])[:8],
        'proficient_skills': skills.get('technical', {}).get('proficient', [])[:6],
        'certifications':    graph.get('certifications', [])[:4],
        'recent_role':       graph.get('experience', [{}])[0].get('role', '') if graph.get('experience') else '',
        'recent_company':    graph.get('experience', [{}])[0].get('company', '') if graph.get('experience') else '',
        'project_count':     len(graph.get('projects', [])),
        'project_keywords':  list({kw for p in graph.get('projects', [])
                                   for kw in p.get('keywords', [])})[:12],
        'education':         graph.get('education', {}).get('degree', ''),
    }


# ── FULL ANALYSIS ─────────────────────────────────────────────────────────────
ANALYSIS_SYSTEM = """You are a senior technical recruiter and data scientist.
Analyze resume vs job description with honesty and precision.
Return ONLY valid JSON. No markdown, no explanation."""

ANALYSIS_PROMPT = """Analyze this candidate's profile against the job description.

CANDIDATE KNOWLEDGE GRAPH:
{knowledge_graph}

JOB DESCRIPTION:
{jd_text}

Return ONLY this JSON (strings under 120 chars, arrays max 6 items):
{{
  "overall_score": 0,
  "grade": "B+",
  "summary": "concise honest 2-sentence assessment",
  "sections": {{
    "skills_match": {{
      "score": 0,
      "matched": ["skill"],
      "missing": ["skill"],
      "bonus": ["skill"]
    }},
    "experience_match": {{
      "score": 0,
      "years_required": "X years",
      "years_candidate": "Y years",
      "relevance_notes": "brief note"
    }},
    "education_match": {{
      "score": 0,
      "required": "degree",
      "candidate": "degree",
      "notes": "note"
    }},
    "keywords_match": {{
      "score": 0,
      "found": ["kw"],
      "missing": ["kw"]
    }},
    "culture_fit": {{
      "score": 0,
      "signals": ["signal"],
      "notes": "note"
    }}
  }},
  "strengths": ["strength1", "strength2", "strength3"],
  "gaps": ["gap1", "gap2"],
  "recommendations": ["rec1", "rec2", "rec3"],
  "ats_score": 0,
  "interview_likelihood": "High"
}}

interview_likelihood must be: Very Low | Low | Moderate | High | Very High"""


def run_full_analysis(graph: dict, jd_text: str) -> tuple[dict, int]:
    """
    Full analysis using knowledge graph (~500 tokens input).
    Returns (analysis_result, tokens_used).
    """
    prompt = ANALYSIS_PROMPT.format(
        knowledge_graph=json.dumps(graph, indent=2),
        jd_text=jd_text[:2500]
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=ANALYSIS_SYSTEM,
        max_tokens=1500
    )
    result = extract_json(raw)
    return result, tokens


# ── RESUME REWRITE ─────────────────────────────────────────────────────────────
REWRITE_SYSTEM = """You are an expert resume writer with strict honesty principles.
RULES YOU MUST NEVER BREAK:
1. Never add skills or technologies not present in the knowledge graph
2. Never invent projects, metrics, or achievements
3. Never change employment dates or durations
4. Never exaggerate impact beyond what the candidate described
5. Only translate existing experience into clearer, more precise language
Return ONLY valid JSON."""

REWRITE_PROMPT = """Rewrite this candidate's resume tailored to the job description.
Present their REAL experience with precision and the right keywords.

KNOWLEDGE GRAPH:
{knowledge_graph}

JOB DESCRIPTION:
{jd_text}

COMPANY: {company}
ROLE: {role}

Return ONLY this JSON:
{{
  "authenticity_checks": {{
    "all_skills_verified": true,
    "no_fabricated_metrics": true,
    "keywords_legitimate": true,
    "dates_unchanged": true,
    "gaps_acknowledged": true
  }},
  "contact_section": "Name | Email | Location | LinkedIn",
  "professional_summary": "3-4 sentences. Specific to this role. No forbidden phrases.",
  "experience": [
    {{
      "company": "company name",
      "role": "job title",
      "duration": "dates",
      "bullets": [
        "Strong action verb + specific task + quantified result using JD keywords"
      ]
    }}
  ],
  "projects": [
    {{
      "name": "project name",
      "bullets": ["action + tech used + impact metric"]
    }}
  ],
  "skills": {{
    "technical": ["skill1 (Expert)", "skill2 (Proficient)"],
    "tools": ["tool1"],
    "certifications": ["cert (year)"]
  }},
  "education": "Degree — Institution (Year)",
  "gaps_section": "Optional: honest 1-sentence note on gap if significant"
}}

FORBIDDEN PHRASES — never use:
passionate about | quick learner | works well in teams | 
excited to apply | great fit | please find attached | 
thank you for your consideration"""


def generate_resume_rewrite(graph: dict, jd_text: str,
                             company: str, role: str) -> tuple[dict, int]:
    """
    Generate tailored resume rewrite.
    Returns (rewrite_dict, tokens_used).
    """
    prompt = REWRITE_PROMPT.format(
        knowledge_graph=json.dumps(graph, indent=2),
        jd_text=jd_text[:2000],
        company=company,
        role=role
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=REWRITE_SYSTEM,
        max_tokens=2500
    )
    result = extract_json(raw)
    return result, tokens


# ── COVER LETTER — STAR TECHNIQUE ─────────────────────────────────────────────
COVER_LETTER_SYSTEM = """You are an expert career coach who writes cover letters 
using the STAR technique (Situation, Task, Action, Result).
Your cover letters are specific, honest, and compelling.
Every claim must be traceable to the candidate's actual knowledge graph.
NEVER fabricate experience or exaggerate impact.
Return ONLY the cover letter text — no JSON, no commentary."""

COVER_LETTER_PROMPT = """Write a STAR-technique cover letter for this candidate.

KNOWLEDGE GRAPH:
{knowledge_graph}

JOB DESCRIPTION:
{jd_text}

COMPANY: {company}
ROLE: {role}
HIRING MANAGER: {manager}
TONE: {tone}

STRUCTURE (follow exactly):
1. PARAGRAPH 1 — HOOK (3-4 sentences)
   Why THIS role at THIS company specifically. Reference something real.
   One sentence on strongest qualification match.
   No generic opener.

2. PARAGRAPH 2 — STAR STORY 1 (most relevant project to THIS JD)
   S: The situation/challenge faced
   T: What the candidate was specifically responsible for
   A: Exactly what was done — name the tools, method, decision
   R: Measurable outcome — use the exact metric from knowledge graph
      If no metric: "significant improvement in [outcome]" — never invent numbers

3. PARAGRAPH 3 — STAR STORY 2 (second most relevant, different JD requirement)
   Condensed STAR — 3-4 sentences
   Must address a DIFFERENT requirement than paragraph 2

4. PARAGRAPH 4 — GAP BRIDGE (ONLY if significant gap exists)
   Honest acknowledgment: "While I have not used X in production..."
   Transfer: "...my experience with Y directly translates because..."
   Closure: "I am currently completing Z to fully bridge this gap."
   SKIP this paragraph entirely if no significant gap

5. PARAGRAPH 5 — CONFIDENT CLOSE (2-3 sentences)
   Specific ask: "I would welcome a conversation about how..."
   Cultural fit signal — one genuine sentence
   Never: "Thank you for your consideration" or "I look forward to hearing from you"

TONE GUIDE:
- formal: traditional corporate, structured, professional
- startup: energetic, direct, ownership language, first-person active
- creative: narrative-led, memorable opening image, personality-forward
- warm: relationship-focused, genuine human connection, empathetic

FORBIDDEN PHRASES — NEVER USE:
"I am passionate about" | "I am a quick learner" | "I work well in teams"
"I am excited to apply" | "I believe I would be a great fit"
"Please find my resume attached" | "Thank you for your time and consideration"
"Responsible for" | "Worked on" | "Helped with"

Length: 3-5 paragraphs. Every sentence must earn its place."""


def generate_cover_letter(graph: dict, jd_text: str, company: str,
                          role: str, manager: str = 'Hiring Manager',
                          tone: str = 'formal') -> tuple[str, int]:
    """
    Generate STAR cover letter.
    Returns (cover_letter_text, tokens_used).
    """
    prompt = COVER_LETTER_PROMPT.format(
        knowledge_graph=json.dumps(graph, indent=2),
        jd_text=jd_text[:2000],
        company=company,
        role=role,
        manager=manager,
        tone=tone
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=COVER_LETTER_SYSTEM,
        max_tokens=1200
    )
    return raw.strip(), tokens


# ── RECRUITER EMAIL ────────────────────────────────────────────────────────────
RECRUITER_EMAIL_SYSTEM = """You are an expert at writing concise, 
compelling recruiter outreach messages.
Write compressed STAR — Result first, hint at Action.
Maximum 7 sentences total.
Return ONLY the email text — no JSON, no subject line, no commentary."""

RECRUITER_EMAIL_PROMPT = """Write a short recruiter outreach message/LinkedIn note.

CANDIDATE PROFILE (compact):
{compact_profile}

JOB TITLE: {role}
COMPANY: {company}
RECRUITER NAME: {recruiter}

STRUCTURE:
Line 1: Named greeting ("Hi [Name]," or "Hi Hiring Team,")
Lines 2-3: One STAR Result + hint at Action (the strongest match to this role)
Line 4: One sentence connecting their result directly to a JD requirement
Line 5: Specific ask — "10 minutes" or "brief call" — never "consideration"
Line 6: Name only

RULES:
- Maximum 7 sentences total — every word must earn its place
- Lead with a RESULT, not with "I am writing to apply"
- Name the specific role and company
- Sound like a confident professional, not a job seeker begging
- Never use: "I am passionate" | "quick learner" | "great opportunity"
- Never use: "Thank you for your time" | "I look forward to hearing from you"

Write the message now:"""


def generate_recruiter_email(graph: dict, jd_text: str, company: str,
                             role: str, recruiter: str = 'Hiring Team') -> tuple[str, int]:
    """
    Generate short recruiter email / LinkedIn note.
    Returns (email_text, tokens_used).
    """
    compact = _build_compact_profile(graph)
    # Add top project for STAR story
    projects = graph.get('projects', [])
    if projects:
        best = max(projects, key=lambda p: p.get('impact_score', 0))
        compact['best_project'] = {
            'name':    best.get('name', ''),
            'summary': best.get('summary', ''),
            'impact':  best.get('impact', ''),
        }
    prompt = RECRUITER_EMAIL_PROMPT.format(
        compact_profile=json.dumps(compact, indent=2),
        role=role,
        company=company,
        recruiter=recruiter
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=RECRUITER_EMAIL_SYSTEM,
        max_tokens=400
    )
    return raw.strip(), tokens


# ── KEYWORD INTELLIGENCE ───────────────────────────────────────────────────────
KEYWORD_SYSTEM = """You are a senior ATS optimization expert.
Return ONLY valid JSON. No markdown, no explanation."""

KEYWORD_PROMPT = """Analyze missing keywords from this JD that are absent from the candidate profile.

CANDIDATE PROFILE (compact):
{compact_profile}

JOB DESCRIPTION:
{jd_text}

Return ONLY this JSON (max 8 keywords, strings under 200 chars, arrays max 3 items):
{{
  "keyword_gaps": [
    {{
      "keyword": "missing keyword",
      "priority": "High",
      "jd_context": "where and how it appears in the JD",
      "resume_section": "Skills | Work Experience - Role | Projects",
      "placement_strategy": "how to naturally incorporate in one sentence",
      "example_sentence": "ready-to-use bullet they can add to resume",
      "impact": "why this keyword matters for ATS and recruiters"
    }}
  ],
  "quick_wins": ["keyword easy to add to Skills section in 30 seconds"],
  "ats_advice": "one paragraph on biggest change to improve ATS score",
  "keyword_density_score": 0
}}

priority must be: High | Medium | Low"""


def analyze_keyword_gaps(graph: dict, jd_text: str) -> tuple[dict, int]:
    """Analyze missing keywords with placement guidance."""
    compact = _build_compact_profile(graph)
    prompt = KEYWORD_PROMPT.format(
        compact_profile=json.dumps(compact, indent=2),
        jd_text=jd_text[:2000]
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=KEYWORD_SYSTEM,
        max_tokens=2000
    )
    result = extract_json(raw)
    return result, tokens


# ── PROJECT SUGGESTIONS ────────────────────────────────────────────────────────
PROJECT_SYSTEM = """You are an elite resume coach.
Return ONLY valid JSON. No markdown, no explanation."""

PROJECT_PROMPT = """Analyze the candidate's projects against the JD and provide specific rewrites.

CANDIDATE PROJECTS:
{projects}

JOB DESCRIPTION:
{jd_text}

Return ONLY this JSON (max 5 projects, strings under 200 chars, arrays max 3 items):
{{
  "projects": [
    {{
      "name": "project name",
      "current_bullet": "existing description from profile",
      "issues": ["issue1", "issue2"],
      "improved_bullet": "Strong action verb + specific method + metric + JD keywords",
      "keywords_added": ["kw1", "kw2"],
      "impact": "why this rewrite is stronger"
    }}
  ],
  "general_tips": [
    {{"tip": "tip title", "detail": "one concrete sentence"}}
  ],
  "missing_projects": ["type of project that would strengthen this application"],
  "overall_advice": "two sentences on biggest resume improvement opportunity"
}}"""


def analyze_project_suggestions(graph: dict, jd_text: str) -> tuple[dict, int]:
    """Generate project-by-project improvement suggestions."""
    projects = graph.get('projects', [])
    if not projects:
        # Infer from experience if no explicit projects
        projects = [{'name': f"Work at {e.get('company', 'Previous Role')}",
                     'summary': ' '.join(e.get('key_achievements', [])[:2]),
                     'keywords': e.get('keywords', [])}
                    for e in graph.get('experience', [])[:3]]

    prompt = PROJECT_PROMPT.format(
        projects=json.dumps(projects, indent=2),
        jd_text=jd_text[:2000]
    )
    raw, tokens = call_claude(
        messages=[{'role': 'user', 'content': prompt}],
        system=PROJECT_SYSTEM,
        max_tokens=2000
    )
    result = extract_json(raw)
    return result, tokens


# ── STOP WORDS (for keyword pre-check filtering) ──────────────────────────────
STOP_WORDS = {
    'about', 'above', 'after', 'again', 'also', 'although', 'always', 'among',
    'and', 'another', 'any', 'are', 'around', 'been', 'before', 'being', 'below',
    'between', 'both', 'but', 'came', 'can', 'come', 'could', 'did', 'does',
    'doing', 'done', 'down', 'during', 'each', 'even', 'every', 'few', 'for',
    'from', 'further', 'get', 'got', 'had', 'has', 'have', 'having', 'here',
    'him', 'his', 'how', 'however', 'include', 'into', 'its', 'just', 'like',
    'more', 'most', 'must', 'need', 'new', 'not', 'now', 'off', 'often', 'once',
    'only', 'other', 'our', 'out', 'over', 'own', 'part', 'place', 'rather',
    'role', 'same', 'see', 'should', 'since', 'some', 'such', 'than', 'that',
    'the', 'their', 'them', 'then', 'there', 'these', 'they', 'this', 'those',
    'through', 'time', 'too', 'under', 'until', 'upon', 'use', 'used', 'using',
    'very', 'was', 'well', 'were', 'what', 'when', 'where', 'whether', 'which',
    'while', 'who', 'will', 'with', 'within', 'without', 'work', 'working',
    'would', 'you', 'your', 'able', 'across', 'along', 'already', 'apply',
    'based', 'best', 'company', 'drive', 'ensure', 'good', 'great', 'help',
    'high', 'join', 'key', 'lead', 'looking', 'make', 'manage', 'multiple',
    'opportunity', 'plus', 'provide', 'strong', 'support', 'team', 'tools',
    'type', 'various', 'wide', 'year', 'years',
}
