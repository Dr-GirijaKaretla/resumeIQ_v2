"""
API Routes — All JSON endpoints
"""
import io
import re
import json
import urllib.request
import urllib.error
import urllib.parse
from flask import Blueprint, request, jsonify, current_app
from flask_login import login_required, current_user
from models import db, KnowledgeGraph, Analysis
from knowledge_graph import (
    extract_knowledge_graph,
    keyword_pre_check,
    ai_pre_score,
    run_full_analysis,
    generate_resume_rewrite,
    generate_cover_letter,
    generate_recruiter_email,
    analyze_keyword_gaps,
    analyze_project_suggestions,
)

api_bp = Blueprint('api', __name__, url_prefix='/api')

ALLOWED_EXTENSIONS = {'pdf', 'txt', 'doc', 'docx'}
BLOCKED_SITES = ['linkedin.com']
JS_HEAVY_SITES = ['workday.com', 'myworkdayjobs.com', 'taleo.net',
                   'icims.com', 'greenhouse.io']


# ── HELPERS ───────────────────────────────────────────────────────────────────
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def extract_text_from_file(file) -> str:
    from werkzeug.utils import secure_filename
    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    file_bytes = file.read()
    if ext == 'pdf':
        try:
            import pdfplumber
            with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
                return '\n'.join(p.extract_text() or '' for p in pdf.pages).strip()
        except Exception as e:
            return f'[PDF extraction error: {e}]'
    if ext in ('doc', 'docx'):
        try:
            import docx2txt
            return docx2txt.process(io.BytesIO(file_bytes)).strip()
        except Exception as e:
            return f'[DOCX extraction error: {e}]'
    return file_bytes.decode('utf-8', errors='ignore')


def check_tier(feature: str) -> bool:
    """Check if current user's tier supports a feature."""
    tier_features = {
        'resume_download':   ['job_hunter', 'career_pro'],
        'cover_letter':      ['job_hunter', 'career_pro'],
        'recruiter_email':   ['job_hunter', 'career_pro'],
        'docx_download':     ['career_pro'],
        'tone_selector':     ['career_pro'],
        'full_history':      ['career_pro'],
        'interview_prep':    ['career_pro'],
        'linkedin_optimizer':['career_pro'],
    }
    allowed_tiers = tier_features.get(feature, ['free', 'job_hunter', 'career_pro'])
    return current_user.tier in allowed_tiers


def error(msg, code=400):
    return jsonify({'success': False, 'error': msg}), code


def ok(data=None, **kwargs):
    resp = {'success': True}
    if data:
        resp['data'] = data
    resp.update(kwargs)
    return jsonify(resp)


# ── PROFILE ───────────────────────────────────────────────────────────────────
@api_bp.route('/profile', methods=['GET'])
@login_required
def get_profile():
    """Get current user profile and knowledge graph."""
    kg = current_user.knowledge_graph
    return ok({
        'user': {
            'id':         current_user.id,
            'name':       current_user.name,
            'email':      current_user.email,
            'avatar':     current_user.avatar_url,
            'tier':       current_user.tier,
            'tier_label': current_user.tier_label,
            'has_profile': current_user.has_profile,
        },
        'knowledge_graph': {
            'graph':        kg.graph if kg else None,
            'completeness': kg.completeness if kg else 0,
            'version':      kg.profile_version if kg else 0,
            'updated_at':   kg.updated_at.isoformat() if kg else None,
        }
    })


@api_bp.route('/profile/upload', methods=['POST'])
@login_required
def upload_resume():
    """
    Upload resume → extract knowledge graph → save to DB.
    This is the one-time onboarding step.
    """
    resume_text = ''

    # File upload
    f = request.files.get('resume_file')
    if f and f.filename and allowed_file(f.filename):
        resume_text = extract_text_from_file(f)

    # Text paste fallback
    if not resume_text:
        resume_text = (request.form.get('resume_text') or '').strip()

    if not resume_text:
        return error('Please provide your resume via file upload or text paste.')
    if len(resume_text) < 100:
        return error('Resume text too short. Please check your input.')

    try:
        # Extract knowledge graph (one-time API call)
        graph, tokens = extract_knowledge_graph(resume_text)

        # Save or update knowledge graph
        kg = current_user.knowledge_graph
        if kg:
            kg.graph           = graph
            kg.resume_raw      = resume_text[:50000]
            kg.profile_version += 1
            kg.completeness    = KnowledgeGraph(graph=graph).compute_completeness()
        else:
            kg = KnowledgeGraph(
                user_id         = current_user.id,
                graph           = graph,
                resume_raw      = resume_text[:50000],
                completeness    = 0,
            )
            kg.completeness = kg.compute_completeness()
            db.session.add(kg)

        db.session.commit()

        return ok({
            'graph':        graph,
            'completeness': kg.completeness,
            'tokens_used':  tokens,
            'message':      'Profile created successfully.'
        })

    except Exception as e:
        current_app.logger.error(f'Resume upload error: {e}')
        return error(f'Failed to process resume: {str(e)}', 500)


@api_bp.route('/profile/update', methods=['PUT'])
@login_required
def update_profile():
    """Update a specific field in the knowledge graph."""
    data = request.get_json(silent=True) or {}
    field = data.get('field')
    value = data.get('value')

    if not field or value is None:
        return error('field and value are required.')

    allowed_fields = [
        'identity', 'education', 'certifications',
        'experience', 'projects', 'skills'
    ]
    if field not in allowed_fields:
        return error(f'Invalid field. Must be one of: {allowed_fields}')

    kg = current_user.knowledge_graph
    if not kg:
        return error('Profile not found. Please upload your resume first.')

    graph = dict(kg.graph)
    graph[field] = value
    kg.graph = graph
    kg.profile_version += 1
    kg.completeness = kg.compute_completeness()
    db.session.commit()

    return ok({'completeness': kg.completeness, 'version': kg.profile_version})


# ── JD FETCH ──────────────────────────────────────────────────────────────────
@api_bp.route('/fetch-jd', methods=['POST'])
@login_required
def fetch_jd():
    """Fetch and extract job description text from a URL."""
    data = request.get_json(silent=True) or {}
    url = (data.get('url') or '').strip()

    if not url:
        return error('URL is required.')

    try:
        result = _fetch_jd_from_url(url)
        return ok(result)
    except ValueError as e:
        return error(str(e), 422)
    except Exception as e:
        return error(f'Unexpected error: {e}', 500)


def _fetch_jd_from_url(url: str) -> dict:
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception:
        raise ValueError('Invalid URL format.')

    if parsed.scheme not in ('http', 'https'):
        raise ValueError('URL must start with http:// or https://')

    domain = parsed.netloc.lower().replace('www.', '')

    for blocked in BLOCKED_SITES:
        if blocked in domain:
            raise ValueError(
                f'{blocked} requires login and cannot be scraped. '
                'Please copy the job description text and paste it instead.'
            )

    js_warning = None
    for js_site in JS_HEAVY_SITES:
        if js_site in domain:
            js_warning = (
                f'{domain} uses JavaScript rendering — content may be incomplete. '
                'If results look wrong, paste the JD text directly.'
            )
            break

    headers = {
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept': 'text/html,application/xhtml+xml,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.9',
    }

    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            html = resp.read(500_000).decode('utf-8', errors='replace')
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise ValueError(
                'This site blocked the request (403). '
                'Please paste the job description text instead.'
            )
        raise ValueError(f'HTTP {e.code} error fetching the URL.')
    except urllib.error.URLError as e:
        raise ValueError(f'Could not reach URL: {e.reason}')

    from bs4 import BeautifulSoup
    soup = BeautifulSoup(html, 'lxml')

    for tag in soup(['script', 'style', 'nav', 'header',
                     'footer', 'aside', 'iframe', 'noscript']):
        tag.decompose()

    title = ''
    title_tag = soup.find('title')
    if title_tag:
        title = title_tag.get_text(strip=True)[:120]

    JD_SELECTORS = [
        'job-description', 'jobDescription', 'job_description',
        'description', 'jobDetails', 'job-details',
        'posting-description', 'job-body', 'jobBody',
        'job-content', 'jobContent',
    ]

    jd_text = ''
    for sel in JD_SELECTORS:
        node = soup.find(id=re.compile(sel, re.I)) or \
               soup.find(class_=re.compile(sel, re.I))
        if node:
            jd_text = node.get_text(separator='\n', strip=True)
            if len(jd_text) > 200:
                break

    if len(jd_text) < 200:
        for tag_name in ['article', 'main', 'section']:
            node = soup.find(tag_name)
            if node:
                candidate = node.get_text(separator='\n', strip=True)
                if len(candidate) > len(jd_text):
                    jd_text = candidate
                    if len(jd_text) > 300:
                        break

    if len(jd_text) < 200:
        best, best_len = None, 0
        for div in soup.find_all('div'):
            t = div.get_text(separator=' ', strip=True)
            if len(t) > best_len:
                best, best_len = div, len(t)
        if best:
            jd_text = best.get_text(separator='\n', strip=True)

    jd_text = re.sub(r'\n{3,}', '\n\n', jd_text).strip()

    if len(jd_text) < 100:
        raise ValueError(
            'Could not extract job description from this page. '
            'Please paste the text directly.'
        )

    if len(jd_text) > 8000:
        jd_text = jd_text[:8000] + '\n[truncated]'

    return {'text': jd_text, 'title': title, 'warning': js_warning}


# ── QUALITY GATE ──────────────────────────────────────────────────────────────
@api_bp.route('/pre-check', methods=['POST'])
@login_required
def pre_check():
    """
    Two-stage quality gate.
    Stage 1: keyword overlap (free, instant)
    Stage 2: AI pre-score (cheap, ~2 seconds)
    Returns gate result and whether full analysis is unlocked.
    """
    if not current_user.has_profile:
        return error('Please set up your profile first.')

    if not current_user.can_analyze(current_app.config):
        return error('Monthly analysis limit reached. Upgrade your plan to continue.')

    data = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()
    career_change = data.get('career_change', False)

    if not jd_text or len(jd_text) < 50:
        return error('Job description too short.')

    kg = current_user.knowledge_graph
    graph = kg.graph

    # Determine threshold
    career_level = graph.get('identity', {}).get('career_level', 'mid')
    thresholds = current_app.config['MATCH_THRESHOLDS']
    if career_change:
        threshold = thresholds['career_change']
    else:
        threshold = thresholds.get(career_level, thresholds['mid'])

    total_tokens = 0

    # ── Stage 1: Keyword check ────────────────────────────────────────────────
    user_keywords = kg.global_keywords
    keyword_overlap, matched_kw, missing_jd_terms = keyword_pre_check(
        user_keywords, jd_text
    )

    if keyword_overlap < 40:
        return ok({
            'gate': 'blocked',
            'stage': 1,
            'keyword_overlap': keyword_overlap,
            'threshold': threshold,
            'matched_keywords': matched_kw[:10],
            'missing_terms': missing_jd_terms[:8],
            'message': 'Keyword overlap too low for a successful application.',
            'tokens_used': 0,
        })

    # ── Stage 2: AI pre-score ─────────────────────────────────────────────────
    try:
        pre_result, tokens = ai_pre_score(graph, jd_text)
        total_tokens += tokens
        pre_score_val = pre_result.get('score', 0)
    except Exception as e:
        current_app.logger.error(f'Pre-score error: {e}')
        return error(f'Pre-score failed: {str(e)}', 500)

    if pre_score_val < threshold:
        return ok({
            'gate': 'blocked',
            'stage': 2,
            'pre_score': pre_score_val,
            'keyword_overlap': keyword_overlap,
            'threshold': threshold,
            'top_matches': pre_result.get('top_matches', []),
            'critical_gaps': pre_result.get('critical_gaps', []),
            'verdict': pre_result.get('verdict', ''),
            'points_away': threshold - pre_score_val,
            'message': f'Match score {pre_score_val}% is below the {threshold}% threshold.',
            'tokens_used': total_tokens,
        })

    # ── Unlocked ──────────────────────────────────────────────────────────────
    return ok({
        'gate': 'unlocked',
        'pre_score': pre_score_val,
        'keyword_overlap': keyword_overlap,
        'threshold': threshold,
        'top_matches': pre_result.get('top_matches', []),
        'verdict': pre_result.get('verdict', ''),
        'message': f'Great match at {pre_score_val}%! Running full analysis...',
        'tokens_used': total_tokens,
    })


# ── FULL ANALYSIS ─────────────────────────────────────────────────────────────
@api_bp.route('/analyze', methods=['POST'])
@login_required
def analyze():
    """Full analysis — only called after gate is unlocked."""
    if not current_user.has_profile:
        return error('Please set up your profile first.')

    if not current_user.can_analyze(current_app.config):
        return error('Monthly analysis limit reached.')

    data = request.get_json(silent=True) or {}
    jd_text     = (data.get('jd_text') or '').strip()
    job_url     = (data.get('job_url') or '').strip()
    company     = (data.get('company') or 'the company').strip()
    role        = (data.get('role') or 'this role').strip()

    if not jd_text or len(jd_text) < 50:
        return error('Job description required.')

    kg = current_user.knowledge_graph
    graph = kg.graph
    total_tokens = 0

    try:
        analysis_result, tokens = run_full_analysis(graph, jd_text)
        total_tokens += tokens

        # Save analysis record
        record = Analysis(
            user_id       = current_user.id,
            job_url       = job_url or None,
            job_title     = role,
            company_name  = company,
            jd_text       = jd_text[:10000],
            overall_score = analysis_result.get('overall_score'),
            grade         = analysis_result.get('grade'),
            analysis_json = analysis_result,
            status        = 'completed',
            kg_version    = kg.profile_version,
            tokens_used   = total_tokens,
        )
        db.session.add(record)
        current_user.increment_analyses()
        db.session.commit()

        return ok({
            'analysis_id': record.id,
            'analysis':    analysis_result,
            'tokens_used': total_tokens,
        })

    except Exception as e:
        current_app.logger.error(f'Analysis error: {e}')
        return error(f'Analysis failed: {str(e)}', 500)


# ── RESUME REWRITE ────────────────────────────────────────────────────────────
@api_bp.route('/resume/generate', methods=['POST'])
@login_required
def generate_resume():
    """Generate tailored resume rewrite."""
    if not check_tier('resume_download'):
        return error('Resume rewrite is available on Job Hunter and Career Pro plans.', 403)

    data = request.get_json(silent=True) or {}
    jd_text     = (data.get('jd_text') or '').strip()
    company     = (data.get('company') or 'the company').strip()
    role        = (data.get('role') or 'this role').strip()
    analysis_id = data.get('analysis_id')

    if not jd_text:
        return error('Job description required.')

    graph = current_user.knowledge_graph.graph

    try:
        rewrite, tokens = generate_resume_rewrite(graph, jd_text, company, role)

        # Update analysis record if provided
        if analysis_id:
            record = Analysis.query.filter_by(
                id=analysis_id, user_id=current_user.id
            ).first()
            if record:
                record.resume_rewrite = json.dumps(rewrite)
                record.tokens_used = (record.tokens_used or 0) + tokens
                db.session.commit()

        return ok({'rewrite': rewrite, 'tokens_used': tokens})

    except Exception as e:
        current_app.logger.error(f'Resume rewrite error: {e}')
        return error(f'Resume generation failed: {str(e)}', 500)


# ── COVER LETTER ──────────────────────────────────────────────────────────────
@api_bp.route('/cover-letter', methods=['POST'])
@login_required
def cover_letter():
    """Generate STAR cover letter."""
    if not check_tier('cover_letter'):
        return error('Cover letter is available on Job Hunter and Career Pro plans.', 403)

    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()
    company = (data.get('company') or 'the company').strip()
    role    = (data.get('role') or 'this role').strip()
    manager = (data.get('manager') or 'Hiring Manager').strip()
    tone    = (data.get('tone') or 'formal').strip()

    # Tone selector only for Career Pro
    if tone != 'formal' and not check_tier('tone_selector'):
        tone = 'formal'

    if not jd_text:
        return error('Job description required.')

    graph = current_user.knowledge_graph.graph

    try:
        letter, tokens = generate_cover_letter(
            graph, jd_text, company, role, manager, tone
        )

        # Update analysis record
        analysis_id = data.get('analysis_id')
        if analysis_id:
            record = Analysis.query.filter_by(
                id=analysis_id, user_id=current_user.id
            ).first()
            if record:
                record.cover_letter = letter
                record.tokens_used = (record.tokens_used or 0) + tokens
                db.session.commit()

        return ok({'cover_letter': letter, 'tone': tone, 'tokens_used': tokens})

    except Exception as e:
        current_app.logger.error(f'Cover letter error: {e}')
        return error(f'Cover letter generation failed: {str(e)}', 500)


# ── RECRUITER EMAIL ───────────────────────────────────────────────────────────
@api_bp.route('/recruiter-email', methods=['POST'])
@login_required
def recruiter_email():
    """Generate short recruiter email / LinkedIn note."""
    if not check_tier('recruiter_email'):
        return error('Recruiter email is available on Job Hunter and Career Pro plans.', 403)

    data      = request.get_json(silent=True) or {}
    jd_text   = (data.get('jd_text') or '').strip()
    company   = (data.get('company') or 'the company').strip()
    role      = (data.get('role') or 'this role').strip()
    recruiter = (data.get('recruiter') or 'Hiring Team').strip()

    if not jd_text:
        return error('Job description required.')

    graph = current_user.knowledge_graph.graph

    try:
        email_text, tokens = generate_recruiter_email(
            graph, jd_text, company, role, recruiter
        )

        analysis_id = data.get('analysis_id')
        if analysis_id:
            record = Analysis.query.filter_by(
                id=analysis_id, user_id=current_user.id
            ).first()
            if record:
                record.recruiter_email = email_text
                record.tokens_used = (record.tokens_used or 0) + tokens
                db.session.commit()

        return ok({'email': email_text, 'tokens_used': tokens})

    except Exception as e:
        current_app.logger.error(f'Recruiter email error: {e}')
        return error(f'Email generation failed: {str(e)}', 500)


# ── KEYWORD INTELLIGENCE ──────────────────────────────────────────────────────
@api_bp.route('/keywords', methods=['POST'])
@login_required
def keywords():
    """Keyword gap analysis with placement guidance."""
    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()

    if not jd_text:
        return error('Job description required.')

    graph = current_user.knowledge_graph.graph

    try:
        result, tokens = analyze_keyword_gaps(graph, jd_text)
        return ok({'keywords': result, 'tokens_used': tokens})
    except Exception as e:
        return error(f'Keyword analysis failed: {str(e)}', 500)


# ── PROJECT SUGGESTIONS ───────────────────────────────────────────────────────
@api_bp.route('/suggest', methods=['POST'])
@login_required
def suggest():
    """Project improvement suggestions."""
    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()

    if not jd_text:
        return error('Job description required.')

    graph = current_user.knowledge_graph.graph

    try:
        result, tokens = analyze_project_suggestions(graph, jd_text)
        return ok({'suggestions': result, 'tokens_used': tokens})
    except Exception as e:
        return error(f'Project suggestions failed: {str(e)}', 500)


# ── HISTORY ───────────────────────────────────────────────────────────────────
@api_bp.route('/resume/download', methods=['POST'])
@login_required
def download_resume_pdf():
    """Generate and return resume PDF."""
    if not check_tier('resume_download'):
        return error('Resume PDF requires Job Hunter or Career Pro plan.', 403)

    data = request.get_json(silent=True) or {}
    analysis_id = data.get('analysis_id')
    rewrite_raw = data.get('rewrite')

    # Try to load from saved analysis first
    if analysis_id and not rewrite_raw:
        record = Analysis.query.filter_by(
            id=analysis_id, user_id=current_user.id
        ).first()
        if record and record.resume_rewrite:
            rewrite_raw = record.resume_rewrite

    if not rewrite_raw:
        return error('No resume rewrite found. Generate the rewrite first.')

    try:
        import json as _json
        from pdf_generator import resume_to_pdf
        from flask import Response

        rewrite = _json.loads(rewrite_raw) if isinstance(rewrite_raw, str) else rewrite_raw
        pdf_bytes = resume_to_pdf(rewrite, current_user.name)

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'attachment; filename="ResumeIQ_Resume.pdf"',
                'Content-Length': len(pdf_bytes),
            }
        )
    except Exception as e:
        current_app.logger.error(f'Resume PDF error: {e}')
        return error(f'PDF generation failed: {str(e)}', 500)


@api_bp.route('/cover-letter/download', methods=['POST'])
@login_required
def download_cover_pdf():
    """Generate and return cover letter PDF."""
    if not check_tier('cover_letter'):
        return error('Cover letter PDF requires Job Hunter or Career Pro plan.', 403)

    data    = request.get_json(silent=True) or {}
    text    = data.get('text', '')
    company = data.get('company', 'the company')
    role    = data.get('role', 'this role')
    analysis_id = data.get('analysis_id')

    if not text and analysis_id:
        record = Analysis.query.filter_by(
            id=analysis_id, user_id=current_user.id
        ).first()
        if record and record.cover_letter:
            text = record.cover_letter

    if not text:
        return error('No cover letter found. Generate the cover letter first.')

    try:
        from pdf_generator import cover_letter_to_pdf
        from flask import Response
        pdf_bytes = cover_letter_to_pdf(text, current_user.name, company, role)

        return Response(
            pdf_bytes,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'attachment; filename="ResumeIQ_CoverLetter.pdf"',
                'Content-Length': len(pdf_bytes),
            }
        )
    except Exception as e:
        current_app.logger.error(f'Cover letter PDF error: {e}')
        return error(f'PDF generation failed: {str(e)}', 500)


@api_bp.route('/history/<analysis_id>/email', methods=['POST'])
@login_required
def email_analysis(analysis_id):
    """Send analysis summary email to user."""
    record = Analysis.query.filter_by(
        id=analysis_id, user_id=current_user.id
    ).first()
    if not record:
        return error('Analysis not found.', 404)

    try:
        from email_service import send_analysis_summary
        sent = send_analysis_summary(current_user, record)
        if sent:
            return ok({'message': 'Analysis summary sent to ' + current_user.email})
        else:
            return error('Email could not be sent. Check RESEND_API_KEY.')
    except Exception as e:
        return error(f'Email failed: {str(e)}', 500)


@api_bp.route('/interview-prep', methods=['POST'])
@login_required
def interview_prep_route():
    """Generate interview prep pack. Career Pro tier."""
    if not check_tier('interview_prep'):
        return error('Interview prep is a Career Pro feature. Upgrade to access.', 403)
    if not current_user.has_profile:
        return error('Please set up your profile first.')

    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()
    company = (data.get('company') or 'the company').strip()
    role    = (data.get('role') or 'this role').strip()

    if not jd_text:
        return error('Job description required.')

    graph = current_user.knowledge_graph.graph

    try:
        from interview_prep import generate_interview_prep
        result, tokens = generate_interview_prep(graph, jd_text, company, role)

        analysis_id = data.get('analysis_id')
        if analysis_id:
            import json as _json
            record = Analysis.query.filter_by(
                id=analysis_id, user_id=current_user.id
            ).first()
            if record:
                existing = dict(record.analysis_json or {})
                existing['interview_prep'] = result
                record.analysis_json = existing
                record.tokens_used = (record.tokens_used or 0) + tokens
                db.session.commit()

        return ok({'prep': result, 'tokens_used': tokens})
    except Exception as e:
        current_app.logger.error(f'Interview prep error: {e}')
        return error(f'Interview prep failed: {str(e)}', 500)


@api_bp.route('/linkedin-optimizer', methods=['POST'])
@login_required
def linkedin_optimizer_route():
    """Generate LinkedIn profile optimization. Career Pro tier."""
    if not check_tier('linkedin_optimizer'):
        return error('LinkedIn optimizer is a Career Pro feature. Upgrade to access.', 403)
    if not current_user.has_profile:
        return error('Please set up your profile first.')

    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()

    graph = current_user.knowledge_graph.graph

    try:
        from linkedin_optimizer import generate_linkedin_optimization
        result, tokens = generate_linkedin_optimization(graph, jd_text)
        return ok({'optimization': result, 'tokens_used': tokens})
    except Exception as e:
        current_app.logger.error(f'LinkedIn optimizer error: {e}')
        return error(f'LinkedIn optimization failed: {str(e)}', 500)


# ── SALARY INTELLIGENCE ───────────────────────────────────────────────────────
@api_bp.route('/salary', methods=['POST'])
@login_required
def salary_intelligence():
    """Get market salary range for a role."""
    if not current_user.has_profile:
        return error('Please set up your profile first.')

    data    = request.get_json(silent=True) or {}
    role    = (data.get('role')    or '').strip()
    company = (data.get('company') or '').strip()

    if not role:
        return error('Role is required.')

    graph = current_user.knowledge_graph.graph

    try:
        from tracker import get_salary_intelligence
        result, tokens = get_salary_intelligence(graph, role, company)
        return ok({'salary': result, 'tokens_used': tokens})
    except Exception as e:
        return error(f'Salary lookup failed: {str(e)}', 500)


# ── RED FLAG DETECTOR ─────────────────────────────────────────────────────────
@api_bp.route('/red-flags', methods=['POST'])
@login_required
def red_flags():
    """Detect red flags in a job description."""
    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()
    company = (data.get('company') or '').strip()
    role    = (data.get('role')    or '').strip()

    if not jd_text:
        return error('Job description required.')

    try:
        from tracker import detect_red_flags
        result, tokens = detect_red_flags(jd_text, company, role)
        return ok({'flags': result, 'tokens_used': tokens})
    except Exception as e:
        return error(f'Red flag detection failed: {str(e)}', 500)


# ── COMPANY INTELLIGENCE ──────────────────────────────────────────────────────
@api_bp.route('/company-intel', methods=['POST'])
@login_required
def company_intel():
    """Get company intelligence card for a job posting."""
    data    = request.get_json(silent=True) or {}
    jd_text = (data.get('jd_text') or '').strip()
    company = (data.get('company') or '').strip()
    role    = (data.get('role')    or '').strip()

    if not company:
        return error('Company name required.')

    try:
        from tracker import get_company_intelligence
        result, tokens = get_company_intelligence(jd_text, company, role)
        return ok({'intel': result, 'tokens_used': tokens})
    except Exception as e:
        return error(f'Company intelligence failed: {str(e)}', 500)


# ── APPLICATION TRACKER ───────────────────────────────────────────────────────
@api_bp.route('/tracker', methods=['GET'])
@login_required
def get_tracker():
    """Get all tracked applications for current user."""
    from models import ApplicationTracker
    apps = ApplicationTracker.query.filter_by(
        user_id=current_user.id
    ).order_by(ApplicationTracker.updated_at.desc()).all()
    return ok({'applications': [a.to_dict() for a in apps]})


@api_bp.route('/tracker', methods=['POST'])
@login_required
def create_tracker():
    """Add a new application to the tracker."""
    from models import ApplicationTracker
    from datetime import date as _date

    data = request.get_json(silent=True) or {}

    app_entry = ApplicationTracker(
        user_id      = current_user.id,
        analysis_id  = data.get('analysis_id'),
        job_title    = (data.get('job_title')    or '').strip()[:255],
        company      = (data.get('company')      or '').strip()[:255],
        job_url      = (data.get('job_url')      or '').strip(),
        location     = (data.get('location')     or '').strip()[:255],
        salary_range = (data.get('salary_range') or '').strip()[:100],
        status       = data.get('status', 'saved'),
        match_score  = data.get('match_score'),
        notes        = (data.get('notes') or '').strip(),
    )

    # Parse dates
    for field in ('applied_date', 'follow_up_date'):
        val = data.get(field)
        if val:
            try:
                from datetime import datetime
                setattr(app_entry, field,
                        datetime.strptime(val, '%Y-%m-%d').date())
            except Exception:
                pass

    db.session.add(app_entry)
    db.session.commit()
    return ok({'application': app_entry.to_dict()})


@api_bp.route('/tracker/<app_id>', methods=['PUT'])
@login_required
def update_tracker(app_id):
    """Update status, notes, or dates on a tracked application."""
    from models import ApplicationTracker
    from tracker import APPLICATION_STATUSES

    entry = ApplicationTracker.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first()
    if not entry:
        return error('Application not found.', 404)

    data = request.get_json(silent=True) or {}

    if 'status' in data:
        if data['status'] not in APPLICATION_STATUSES:
            return error(f'Invalid status. Must be one of: {APPLICATION_STATUSES}')
        entry.status = data['status']

    for field in ('job_title', 'company', 'job_url', 'location',
                  'salary_range', 'notes'):
        if field in data:
            setattr(entry, field, (data[field] or '').strip())

    for field in ('applied_date', 'follow_up_date'):
        if field in data:
            val = data[field]
            if val:
                try:
                    from datetime import datetime
                    setattr(entry, field,
                            datetime.strptime(val, '%Y-%m-%d').date())
                except Exception:
                    pass
            else:
                setattr(entry, field, None)

    db.session.commit()
    return ok({'application': entry.to_dict()})


@api_bp.route('/tracker/<app_id>', methods=['DELETE'])
@login_required
def delete_tracker(app_id):
    """Delete a tracked application."""
    from models import ApplicationTracker
    entry = ApplicationTracker.query.filter_by(
        id=app_id, user_id=current_user.id
    ).first()
    if not entry:
        return error('Application not found.', 404)
    db.session.delete(entry)
    db.session.commit()
    return ok({'deleted': True})


# ── WEEKLY DIGEST (manual trigger + cron endpoint) ────────────────────────────
@api_bp.route('/digest/preview', methods=['POST'])
@login_required
def digest_preview():
    """Generate a digest preview for the current user."""
    if current_user.tier != 'career_pro':
        return error('Weekly digest is a Career Pro feature.', 403)
    if not current_user.has_profile:
        return error('Please set up your profile first.')

    try:
        from job_digest import build_digest_content
        result, tokens = build_digest_content(
            current_user.knowledge_graph.graph
        )
        return ok({'digest': result, 'tokens_used': tokens})
    except Exception as e:
        return error(f'Digest generation failed: {str(e)}', 500)


@api_bp.route('/digest/send-all', methods=['POST'])
def digest_send_all():
    """
    Cron endpoint — send weekly digest to all Career Pro users.
    Secured with a shared secret header.
    Call this every Monday at 8am UTC from Railway cron or external scheduler.
    """
    token = request.headers.get('X-Cron-Secret', '')
    expected = current_app.config.get('SECRET_KEY', '')
    if token != expected:
        return jsonify({'error': 'Unauthorized'}), 401

    try:
        from job_digest import send_weekly_digest_all_users
        result = send_weekly_digest_all_users()
        return ok(result)
    except Exception as e:
        return error(f'Digest send failed: {str(e)}', 500)


@api_bp.route('/history', methods=['GET'])
@login_required
def get_history():
    """Get analysis history for current user."""
    limit = current_app.config['TIER_LIMITS'][current_user.tier]['history']
    if limit == 0:
        return ok({'analyses': [], 'message': 'Upgrade to save analysis history.'})

    query = Analysis.query.filter_by(
        user_id=current_user.id,
        status='completed'
    ).order_by(Analysis.created_at.desc())

    if limit != 999:
        query = query.limit(limit)

    analyses = query.all()
    return ok({
        'analyses': [{
            'id':           a.id,
            'job_title':    a.display_title,
            'company':      a.display_company,
            'score':        a.overall_score,
            'grade':        a.grade,
            'created_at':   a.created_at.isoformat(),
            'has_resume':   bool(a.resume_rewrite),
            'has_cover':    bool(a.cover_letter),
            'has_email':    bool(a.recruiter_email),
        } for a in analyses]
    })


@api_bp.route('/history/<analysis_id>', methods=['GET'])
@login_required
def get_analysis(analysis_id):
    """Get full detail for a single past analysis."""
    record = Analysis.query.filter_by(
        id=analysis_id, user_id=current_user.id
    ).first()

    if not record:
        return error('Analysis not found.', 404)

    return ok({
        'id':             record.id,
        'job_title':      record.display_title,
        'company':        record.display_company,
        'job_url':        record.job_url,
        'score':          record.overall_score,
        'grade':          record.grade,
        'analysis':       record.analysis_json,
        'resume_rewrite': json.loads(record.resume_rewrite) if record.resume_rewrite else None,
        'cover_letter':   record.cover_letter,
        'recruiter_email':record.recruiter_email,
        'created_at':     record.created_at.isoformat(),
    })
