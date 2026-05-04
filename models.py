from datetime import datetime, timezone
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
import uuid

db = SQLAlchemy()


def utcnow():
    return datetime.now(timezone.utc)


# ── USERS ──────────────────────────────────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id                  = db.Column(db.String(36), primary_key=True,
                                    default=lambda: str(uuid.uuid4()))
    google_id           = db.Column(db.String(255), unique=True, nullable=False)
    email               = db.Column(db.String(255), unique=True, nullable=False)
    name                = db.Column(db.String(255), nullable=False)
    avatar_url          = db.Column(db.Text)
    tier                = db.Column(db.String(20), default='free')   # free | job_hunter | career_pro
    stripe_customer_id  = db.Column(db.String(255))
    stripe_sub_id       = db.Column(db.String(255))
    analyses_this_month = db.Column(db.Integer, default=0)
    analyses_reset_date = db.Column(db.Date)
    created_at          = db.Column(db.DateTime(timezone=True), default=utcnow)
    last_login          = db.Column(db.DateTime(timezone=True))

    # relationships
    knowledge_graph = db.relationship('KnowledgeGraph', backref='user',
                                       uselist=False, cascade='all, delete-orphan')
    analyses        = db.relationship('Analysis', backref='user',
                                       cascade='all, delete-orphan',
                                       order_by='Analysis.created_at.desc()')

    def __repr__(self):
        return f'<User {self.email}>'

    @property
    def has_profile(self):
        return self.knowledge_graph is not None

    @property
    def tier_label(self):
        return {'free': 'Free', 'job_hunter': 'Job Hunter',
                'career_pro': 'Career Pro'}.get(self.tier, 'Free')

    def can_analyze(self, app_config):
        """Check if user has analyses remaining this month."""
        from datetime import date
        limit = app_config['TIER_LIMITS'][self.tier]['analyses_per_month']
        if limit == 999:
            return True
        # Reset counter if new month
        today = date.today()
        if not self.analyses_reset_date or self.analyses_reset_date.month != today.month:
            self.analyses_this_month = 0
            self.analyses_reset_date = today
            db.session.commit()
        return self.analyses_this_month < limit

    def increment_analyses(self):
        self.analyses_this_month += 1
        db.session.commit()


# ── KNOWLEDGE GRAPH ────────────────────────────────────────────────────────────
class KnowledgeGraph(db.Model):
    __tablename__ = 'knowledge_graphs'

    id              = db.Column(db.String(36), primary_key=True,
                                default=lambda: str(uuid.uuid4()))
    user_id         = db.Column(db.String(36), db.ForeignKey('users.id',
                                ondelete='CASCADE'), nullable=False, unique=True)
    graph           = db.Column(db.JSON, nullable=False)    # structured knowledge graph
    resume_raw      = db.Column(db.Text)                    # original resume text backup
    profile_version = db.Column(db.Integer, default=1)
    completeness    = db.Column(db.Integer, default=0)      # 0-100
    created_at      = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at      = db.Column(db.DateTime(timezone=True), default=utcnow,
                                onupdate=utcnow)

    def __repr__(self):
        return f'<KnowledgeGraph user={self.user_id}>'

    @property
    def identity(self):
        return self.graph.get('identity', {})

    @property
    def projects(self):
        return self.graph.get('projects', [])

    @property
    def skills(self):
        return self.graph.get('skills', {})

    @property
    def global_keywords(self):
        """Flat list of all keywords for fast pre-matching."""
        kw = set()
        # From skills
        s = self.graph.get('skills', {})
        for level in ['expert', 'proficient', 'familiar']:
            kw.update(s.get('technical', {}).get(level, []))
        # From projects
        for p in self.graph.get('projects', []):
            kw.update(p.get('keywords', []))
        # From experience
        for e in self.graph.get('experience', []):
            kw.update(e.get('keywords', []))
        # From certifications (extract names)
        for cert in self.graph.get('certifications', []):
            words = cert.split()
            kw.update(words[:3])  # first 3 words of cert name
        return [k.lower() for k in kw if len(k) > 2]

    def compute_completeness(self):
        """Score profile completeness 0-100."""
        score = 0
        g = self.graph
        if g.get('identity', {}).get('name'):           score += 10
        if g.get('identity', {}).get('target_roles'):   score += 10
        if g.get('education', {}).get('degree'):        score += 10
        if g.get('certifications'):                     score += 10
        if g.get('experience'):                         score += 20
        if g.get('projects'):                           score += 20
        if g.get('skills', {}).get('technical'):        score += 20
        return score


# ── ANALYSES ───────────────────────────────────────────────────────────────────
class Analysis(db.Model):
    __tablename__ = 'analyses'

    id              = db.Column(db.String(36), primary_key=True,
                                default=lambda: str(uuid.uuid4()))
    user_id         = db.Column(db.String(36), db.ForeignKey('users.id',
                                ondelete='CASCADE'), nullable=False)
    job_url         = db.Column(db.Text)
    job_title       = db.Column(db.String(255))
    company_name    = db.Column(db.String(255))
    jd_text         = db.Column(db.Text)
    overall_score   = db.Column(db.Integer)
    grade           = db.Column(db.String(5))
    analysis_json   = db.Column(db.JSON)
    resume_rewrite  = db.Column(db.Text)
    cover_letter    = db.Column(db.Text)
    recruiter_email = db.Column(db.Text)
    status          = db.Column(db.String(20), default='pending')
    # pending | pre_check_failed | completed | error
    pre_score       = db.Column(db.Integer)    # stage 2 pre-score
    kg_version      = db.Column(db.Integer)    # which profile version used
    tokens_used     = db.Column(db.Integer, default=0)
    created_at      = db.Column(db.DateTime(timezone=True), default=utcnow)

    def __repr__(self):
        return f'<Analysis {self.job_title} score={self.overall_score}>'

    @property
    def display_company(self):
        return self.company_name or 'Unknown Company'

    @property
    def display_title(self):
        return self.job_title or 'Untitled Role'


# ── APPLICATION TRACKER ────────────────────────────────────────────────────────
class ApplicationTracker(db.Model):
    __tablename__ = 'application_tracker'

    id           = db.Column(db.String(36), primary_key=True,
                             default=lambda: str(uuid.uuid4()))
    user_id      = db.Column(db.String(36),
                             db.ForeignKey('users.id', ondelete='CASCADE'),
                             nullable=False)
    analysis_id  = db.Column(db.String(36),
                             db.ForeignKey('analyses.id', ondelete='SET NULL'),
                             nullable=True)

    # Job details
    job_title    = db.Column(db.String(255))
    company      = db.Column(db.String(255))
    job_url      = db.Column(db.Text)
    location     = db.Column(db.String(255))
    salary_range = db.Column(db.String(100))  # e.g. "$90k–$120k"

    # Status tracking
    status       = db.Column(db.String(30), default='saved')
    # saved | applied | screening | interview | offer | accepted | rejected | withdrawn

    # Scores
    match_score  = db.Column(db.Integer)

    # Dates
    applied_date   = db.Column(db.Date)
    follow_up_date = db.Column(db.Date)

    # Notes
    notes        = db.Column(db.Text)

    # Metadata
    created_at   = db.Column(db.DateTime(timezone=True), default=utcnow)
    updated_at   = db.Column(db.DateTime(timezone=True), default=utcnow,
                             onupdate=utcnow)

    def __repr__(self):
        return f'<Tracker {self.job_title} @ {self.company} [{self.status}]>'

    def to_dict(self):
        from tracker import STATUS_LABELS
        sl = STATUS_LABELS.get(self.status, {})
        return {
            'id':           self.id,
            'job_title':    self.job_title or 'Untitled',
            'company':      self.company   or 'Unknown',
            'job_url':      self.job_url,
            'location':     self.location,
            'salary_range': self.salary_range,
            'status':       self.status,
            'status_label': sl.get('label', self.status),
            'status_color': sl.get('color', '#888'),
            'status_icon':  sl.get('icon', '•'),
            'match_score':  self.match_score,
            'applied_date': self.applied_date.isoformat() if self.applied_date else None,
            'follow_up_date': self.follow_up_date.isoformat() if self.follow_up_date else None,
            'notes':        self.notes,
            'analysis_id':  self.analysis_id,
            'created_at':   self.created_at.isoformat(),
            'updated_at':   self.updated_at.isoformat(),
        }
