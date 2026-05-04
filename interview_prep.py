"""
Interview Prep Engine — Sprint 5
Generates personalized interview questions + answers
from the user's knowledge graph and the target JD.
"""


INTERVIEW_SYSTEM = """You are a senior technical interviewer and career coach.
Generate realistic, role-specific interview questions with model answers
grounded entirely in the candidate's real experience.
NEVER fabricate experience. Every answer must be defensible in a real interview.
Return ONLY valid JSON. No markdown, no explanation."""


INTERVIEW_PROMPT = """Generate a comprehensive interview prep pack for this candidate.

CANDIDATE KNOWLEDGE GRAPH:
{knowledge_graph}

JOB DESCRIPTION:
{jd_text}

COMPANY: {company}
ROLE: {role}

Return ONLY this JSON (strings under 250 chars, arrays max 4 items each):
{{
  "tell_me_about_yourself": {{
    "script": "A 90-second personal pitch tailored to this exact role. Opens with current role/background, highlights the 2 most relevant experiences for this JD, closes with why THIS role at THIS company. No generic phrases.",
    "tips": ["tip1", "tip2"]
  }},
  "technical_questions": [
    {{
      "question": "realistic technical question for this role",
      "category": "Technical Skills",
      "difficulty": "Medium",
      "model_answer": "STAR-structured answer using candidate's REAL experience from knowledge graph",
      "follow_ups": ["likely follow-up question"],
      "watch_out": "common mistake candidates make on this question"
    }}
  ],
  "behavioural_questions": [
    {{
      "question": "Tell me about a time you...",
      "competency": "Leadership / Problem Solving / Communication etc",
      "model_answer": "Full STAR answer: Situation from their experience, Task they owned, Action taken with specifics, Result with metric",
      "star_breakdown": {{
        "situation": "specific context from their background",
        "task": "what they were responsible for",
        "action": "what they specifically did — name tools, decisions",
        "result": "quantified outcome from their profile"
      }},
      "follow_ups": ["follow-up"]
    }}
  ],
  "questions_to_ask": [
    {{
      "question": "insightful question candidate should ask interviewer",
      "why": "why this question shows intelligence and preparation"
    }}
  ],
  "gap_handling": [
    {{
      "gap": "skill gap from JD that candidate lacks",
      "honest_answer": "how to address it honestly without killing the application",
      "bridge": "how their existing skills transfer to partially cover this gap"
    }}
  ],
  "salary_negotiation": {{
    "opening_line": "confident opener when salary comes up",
    "range_strategy": "how to handle the salary range question",
    "tips": ["tip1", "tip2"]
  }},
  "company_research": [
    {{
      "area": "what to research about this company",
      "why": "why this matters in the interview"
    }}
  ],
  "red_flags_to_avoid": ["mistake1", "mistake2", "mistake3"]
}}

Rules:
- technical_questions: 4-5 questions specific to skills in the JD
- behavioural_questions: 4 questions targeting competencies the JD requires
- questions_to_ask: 4 intelligent questions (not about salary/benefits)
- gap_handling: cover the top 2-3 gaps identified from the JD vs profile
- Every model_answer must reference the candidate's REAL experience, not generic advice
- difficulty: Easy | Medium | Hard"""


def generate_interview_prep(graph: dict, jd_text: str,
                            company: str, role: str) -> tuple[dict, int]:
    """
    Generate full interview prep pack.
    Returns (prep_dict, tokens_used).
    Career Pro tier feature.
    """
    from knowledge_graph import call_claude, extract_json
    import json

    # Build focused profile — emphasise projects and experience
    focused = {
        'identity':      graph.get('identity', {}),
        'experience':    graph.get('experience', [])[:4],
        'projects':      graph.get('projects', [])[:4],
        'skills':        graph.get('skills', {}),
        'education':     graph.get('education', {}),
        'certifications': graph.get('certifications', [])[:4],
    }

    prompt = INTERVIEW_PROMPT.format(
        knowledge_graph = json.dumps(focused, indent=2),
        jd_text         = jd_text[:2000],
        company         = company,
        role            = role,
    )

    raw, tokens = call_claude(
        messages    = [{'role': 'user', 'content': prompt}],
        system      = INTERVIEW_SYSTEM,
        max_tokens  = 4000,
    )
    result = extract_json(raw)
    return result, tokens
