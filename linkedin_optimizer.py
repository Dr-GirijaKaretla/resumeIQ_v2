"""
LinkedIn Optimizer — Sprint 5
Generates optimized LinkedIn profile sections
based on the user's knowledge graph and target roles.
"""


LINKEDIN_SYSTEM = """You are a LinkedIn profile expert and personal branding coach.
Generate optimized LinkedIn content using only the candidate's real experience.
NEVER fabricate claims, skills, or achievements.
Return ONLY valid JSON. No markdown, no explanation."""


LINKEDIN_PROMPT = """Optimize this candidate's LinkedIn profile for their target roles.

CANDIDATE KNOWLEDGE GRAPH:
{knowledge_graph}

TARGET ROLES: {target_roles}
CURRENT JD (for context): {jd_snippet}

Return ONLY this JSON (no markdown, no backticks):
{{
  "headline": {{
    "current_guess": "what their headline probably says now",
    "optimized": "powerful 120-char headline using | separators and top keywords",
    "formula": "Role | Specialization | Key Skill | Notable Achievement or Keyword",
    "alternatives": ["alt headline 1", "alt headline 2"]
  }},
  "about_summary": {{
    "script": "3-paragraph LinkedIn summary. Para 1: who they are + specialization. Para 2: biggest achievement with metric from their profile. Para 3: what they are looking for + call to action. Under 300 words. No generic phrases.",
    "keywords_woven_in": ["keyword1", "keyword2", "keyword3"]
  }},
  "experience_bullets": [
    {{
      "role": "job title from their experience",
      "company": "company name",
      "top_bullet": "strongest rewritten bullet with metric and keyword",
      "reasoning": "why this bullet is stronger"
    }}
  ],
  "skills_to_add": [
    {{
      "skill": "skill name",
      "priority": "High",
      "reason": "why adding this skill improves search visibility"
    }}
  ],
  "skills_to_pin": ["top 3 skills to pin for maximum endorsement visibility"],
  "featured_section": {{
    "recommendation": "what to put in Featured — project, article, or case study",
    "why": "why this specific item maximises profile impact"
  }},
  "connection_strategy": {{
    "who_to_connect": "what type of people to connect with for this target role",
    "connection_note": "short personalized note template for connection requests",
    "groups_to_join": ["relevant LinkedIn group type 1", "group type 2"]
  }},
  "seo_keywords": ["keyword that recruiters search for this role"],
  "profile_strength_score": 0,
  "quick_wins": ["action that takes under 5 minutes to improve profile"]
}}

Rules:
- headline must be under 120 characters
- about_summary.script must be under 300 words
- skills_to_add: max 6, priority = High | Medium | Low
- skills_to_pin: exactly 3
- seo_keywords: 8-10 keywords recruiters actually search
- quick_wins: 5 specific, actionable items
- profile_strength_score: 0-100 estimate of current profile vs ideal"""


def generate_linkedin_optimization(graph: dict,
                                   jd_text: str = '') -> tuple[dict, int]:
    """
    Generate LinkedIn profile optimization recommendations.
    Returns (optimization_dict, tokens_used).
    Career Pro tier feature.
    """
    from knowledge_graph import call_claude, extract_json
    import json

    identity = graph.get('identity', {})
    target_roles = ', '.join(identity.get('target_roles', ['your target role']))

    # Build focused profile
    focused = {
        'identity':      identity,
        'experience':    graph.get('experience', [])[:4],
        'projects':      graph.get('projects', [])[:3],
        'skills':        graph.get('skills', {}),
        'education':     graph.get('education', {}),
        'certifications': graph.get('certifications', [])[:4],
    }

    prompt = LINKEDIN_PROMPT.format(
        knowledge_graph = json.dumps(focused, indent=2),
        target_roles    = target_roles,
        jd_snippet      = jd_text[:800] if jd_text else 'Not provided',
    )

    raw, tokens = call_claude(
        messages   = [{'role': 'user', 'content': prompt}],
        system     = LINKEDIN_SYSTEM,
        max_tokens = 4000,
    )
    result = extract_json(raw)
    return result, tokens
