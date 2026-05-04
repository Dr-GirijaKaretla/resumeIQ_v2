"""
PDF Generator — Sprint 4
Generates print-ready PDF for resume and cover letter using WeasyPrint.
"""
import io
import json
from datetime import datetime


def _html_escape(text: str) -> str:
    return (text or '').replace('&','&amp;').replace('<','&lt;').replace('>','&gt;').replace('"','&quot;')


def build_resume_html(rewrite: dict, user_name: str = '') -> str:
    """Build clean, ATS-friendly resume HTML from rewrite dict."""

    contact  = _html_escape(rewrite.get('contact_section', user_name))
    summary  = _html_escape(rewrite.get('professional_summary', ''))
    edu      = _html_escape(rewrite.get('education', ''))
    gaps     = _html_escape(rewrite.get('gaps_section', ''))
    exp      = rewrite.get('experience', [])
    projs    = rewrite.get('projects', [])
    skills   = rewrite.get('skills', {})

    def section(title, content):
        return f'''
        <div class="section">
          <div class="section-title">{_html_escape(title)}</div>
          <div class="section-line"></div>
          {content}
        </div>'''

    # Experience
    exp_html = ''
    for e in exp:
        bullets = ''.join(f'<li>{_html_escape(b)}</li>' for b in e.get('bullets', []))
        exp_html += f'''
        <div class="exp-block">
          <div class="exp-header">
            <span class="exp-role">{_html_escape(e.get("role",""))}</span>
            <span class="exp-company">— {_html_escape(e.get("company",""))}</span>
            <span class="exp-dates">{_html_escape(e.get("duration",""))}</span>
          </div>
          <ul class="bullet-list">{bullets}</ul>
        </div>'''

    # Projects
    proj_html = ''
    for p in projs:
        bullets = ''.join(f'<li>{_html_escape(b)}</li>' for b in p.get('bullets', []))
        proj_html += f'''
        <div class="exp-block">
          <div class="exp-header">
            <span class="exp-role">{_html_escape(p.get("name",""))}</span>
          </div>
          <ul class="bullet-list">{bullets}</ul>
        </div>'''

    # Skills
    tech  = ' · '.join(skills.get('technical', []))
    tools = ' · '.join(skills.get('tools', []))
    certs = ' · '.join(skills.get('certifications', []))
    skills_html = ''
    if tech:  skills_html += f'<div class="skill-row"><span class="skill-label">Technical</span>{_html_escape(tech)}</div>'
    if tools: skills_html += f'<div class="skill-row"><span class="skill-label">Tools</span>{_html_escape(tools)}</div>'
    if certs: skills_html += f'<div class="skill-row"><span class="skill-label">Certifications</span>{_html_escape(certs)}</div>'

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Georgia', serif;
    font-size: 10.5pt;
    color: #1a1a2e;
    line-height: 1.45;
    padding: 32pt 40pt;
  }}
  .header {{ text-align: center; margin-bottom: 16pt; border-bottom: 2pt solid #2e4057; padding-bottom: 10pt; }}
  .header h1 {{ font-size: 18pt; font-weight: bold; letter-spacing: 1pt; color: #2e4057; }}
  .header .contact {{ font-size: 9pt; color: #555; margin-top: 4pt; }}
  .summary {{ margin-bottom: 14pt; font-style: italic; color: #333; border-left: 3pt solid #048A81; padding-left: 8pt; line-height: 1.55; }}
  .section {{ margin-bottom: 14pt; }}
  .section-title {{ font-size: 11pt; font-weight: bold; color: #2e4057; text-transform: uppercase; letter-spacing: 1pt; margin-bottom: 3pt; }}
  .section-line {{ height: 1pt; background: #2e4057; margin-bottom: 8pt; opacity: 0.3; }}
  .exp-block {{ margin-bottom: 10pt; }}
  .exp-header {{ display: flex; flex-wrap: wrap; gap: 4pt; align-items: baseline; margin-bottom: 3pt; }}
  .exp-role {{ font-weight: bold; font-size: 10.5pt; color: #1a1a2e; }}
  .exp-company {{ font-size: 10pt; color: #444; }}
  .exp-dates {{ margin-left: auto; font-size: 9.5pt; color: #666; font-style: italic; }}
  .bullet-list {{ margin-left: 16pt; }}
  .bullet-list li {{ margin-bottom: 2pt; font-size: 10pt; color: #333; }}
  .skill-row {{ margin-bottom: 4pt; font-size: 9.5pt; }}
  .skill-label {{ font-weight: bold; color: #2e4057; margin-right: 6pt; min-width: 80pt; display: inline-block; }}
  .gaps {{ font-size: 9.5pt; color: #666; font-style: italic; border-left: 2pt solid #ffd166; padding-left: 8pt; margin-top: 8pt; }}
  .footer {{ text-align: center; font-size: 8pt; color: #aaa; margin-top: 20pt; border-top: 1pt solid #eee; padding-top: 6pt; }}
</style>
</head>
<body>

<div class="header">
  <h1>{_html_escape(contact.split('|')[0].strip()) if '|' in contact else _html_escape(contact)}</h1>
  <div class="contact">{_html_escape(' | '.join([p.strip() for p in contact.split('|')[1:]]) if '|' in contact else '')}</div>
</div>

{f'<div class="summary">{summary}</div>' if summary else ''}

{section("Experience", exp_html) if exp_html else ''}
{section("Projects", proj_html) if proj_html else ''}
{section("Skills", skills_html) if skills_html else ''}
{f'{section("Education", f"<div style=\'font-size:10pt;color:#333\'>{edu}</div>")}' if edu else ''}
{f'<div class="gaps">{gaps}</div>' if gaps else ''}

<div class="footer">Generated by ResumeIQ · {datetime.now().strftime("%B %Y")} · resumeiq.app</div>
</body>
</html>'''


def build_cover_letter_html(text: str, user_name: str,
                             company: str, role: str) -> str:
    """Build professional cover letter HTML."""
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    paras_html = ''.join(
        f'<p class="para">{_html_escape(p)}</p>'
        for p in paragraphs
    )
    today = datetime.now().strftime('%B %d, %Y')

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Georgia', serif;
    font-size: 11pt;
    color: #1a1a2e;
    line-height: 1.65;
    padding: 40pt 48pt;
    max-width: 540pt;
    margin: 0 auto;
  }}
  .date {{ color: #666; font-size: 10pt; margin-bottom: 20pt; }}
  .to {{ margin-bottom: 20pt; }}
  .to .company {{ font-weight: bold; color: #2e4057; }}
  .to .role {{ font-size: 10pt; color: #555; }}
  .para {{ margin-bottom: 14pt; color: #333; }}
  .para:first-of-type {{ color: #1a1a2e; }}
  .sign-off {{ margin-top: 24pt; }}
  .sign-off .name {{ font-weight: bold; color: #2e4057; margin-top: 12pt; font-size: 12pt; }}
  .footer {{ text-align: center; font-size: 8pt; color: #bbb; margin-top: 32pt; border-top: 1pt solid #eee; padding-top: 6pt; }}
  .accent-bar {{ width: 40pt; height: 3pt; background: #048A81; margin-bottom: 20pt; }}
</style>
</head>
<body>

<div class="accent-bar"></div>
<div class="date">{today}</div>

<div class="to">
  <div class="company">{_html_escape(company)}</div>
  <div class="role">Re: {_html_escape(role)}</div>
</div>

{paras_html}

<div class="sign-off">
  Sincerely,
  <div class="name">{_html_escape(user_name)}</div>
</div>

<div class="footer">Generated by ResumeIQ · resumeiq.app</div>
</body>
</html>'''


def generate_pdf_bytes(html: str) -> bytes:
    """Convert HTML string to PDF bytes using WeasyPrint."""
    try:
        from weasyprint import HTML, CSS
        pdf_bytes = HTML(string=html).write_pdf()
        return pdf_bytes
    except ImportError:
        raise RuntimeError(
            'WeasyPrint not installed. '
            'Add weasyprint to requirements.txt.'
        )
    except Exception as e:
        raise RuntimeError(f'PDF generation failed: {e}')


def resume_to_pdf(rewrite, user_name: str = '') -> bytes:
    """Generate resume PDF from rewrite dict or string."""
    if isinstance(rewrite, str):
        try:
            import json
            rewrite = json.loads(rewrite)
        except Exception:
            # Plain text fallback
            html = f'''<!DOCTYPE html><html><head><meta charset="UTF-8">
            <style>body{{font-family:Georgia,serif;font-size:11pt;padding:36pt 44pt;line-height:1.6;color:#1a1a2e;}}
            pre{{white-space:pre-wrap;font-family:inherit;}}</style></head>
            <body><pre>{_html_escape(rewrite)}</pre></body></html>'''
            return generate_pdf_bytes(html)
    html = build_resume_html(rewrite, user_name)
    return generate_pdf_bytes(html)


def cover_letter_to_pdf(text: str, user_name: str,
                        company: str, role: str) -> bytes:
    """Generate cover letter PDF from text."""
    html = build_cover_letter_html(text, user_name, company, role)
    return generate_pdf_bytes(html)
