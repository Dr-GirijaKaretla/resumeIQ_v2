import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # ── CORE ──────────────────────────────────────────────────────────────────
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')
    DEBUG = os.environ.get('DEBUG', 'false').lower() == 'true'

    # ── DATABASE ──────────────────────────────────────────────────────────────
    DATABASE_URL = os.environ.get('DATABASE_URL', '')
    # Railway uses postgres:// but SQLAlchemy needs postgresql://
    if DATABASE_URL.startswith('postgres://'):
        DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://', 1)
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 300,
    }

    # ── GOOGLE OAUTH ──────────────────────────────────────────────────────────
    GOOGLE_CLIENT_ID     = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    OAUTHLIB_INSECURE_TRANSPORT = os.environ.get('OAUTHLIB_INSECURE_TRANSPORT', '0')

    # ── ANTHROPIC ─────────────────────────────────────────────────────────────
    ANTHROPIC_API_KEY = os.environ.get('ANTHROPIC_API_KEY', '')
    CLAUDE_MODEL      = 'claude-sonnet-4-20250514'

    # ── STRIPE ───────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY       = os.environ.get('STRIPE_SECRET_KEY', '')
    STRIPE_PUBLISHABLE_KEY  = os.environ.get('STRIPE_PUBLISHABLE_KEY', '')
    STRIPE_WEBHOOK_SECRET   = os.environ.get('STRIPE_WEBHOOK_SECRET', '')
    STRIPE_JOB_HUNTER_PRICE = os.environ.get('STRIPE_JOB_HUNTER_PRICE', '')
    STRIPE_CAREER_PRO_PRICE = os.environ.get('STRIPE_CAREER_PRO_PRICE', '')

    # ── EMAIL ─────────────────────────────────────────────────────────────────
    RESEND_API_KEY   = os.environ.get('RESEND_API_KEY', '')
    FROM_EMAIL       = os.environ.get('FROM_EMAIL', 'hello@resumeiq.app')

    # ── APP ───────────────────────────────────────────────────────────────────
    APP_URL          = os.environ.get('APP_URL', 'http://localhost:5000')
    MAX_CONTENT_LENGTH = 10 * 1024 * 1024   # 10 MB

    # ── TIER LIMITS ───────────────────────────────────────────────────────────
    TIER_LIMITS = {
        'free':        {'analyses_per_month': 3,   'history': 0},
        'job_hunter':  {'analyses_per_month': 999, 'history': 10},
        'career_pro':  {'analyses_per_month': 999, 'history': 999},
    }

    # ── MATCH THRESHOLDS ──────────────────────────────────────────────────────
    MATCH_THRESHOLDS = {
        'fresher':       50,
        'mid':           65,
        'senior':        70,
        'career_change': 55,
    }


class DevelopmentConfig(Config):
    DEBUG = True
    OAUTHLIB_INSECURE_TRANSPORT = '1'


class ProductionConfig(Config):
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production':  ProductionConfig,
    'default':     DevelopmentConfig,
}
