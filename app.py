"""
ResumeIQ v2 — Main Application
AI-Powered Career Intelligence Platform
Sprint 3: Auth + Knowledge Graph + Stripe Billing
"""
import os
from flask import Flask, render_template, redirect, url_for, jsonify
from flask_login import LoginManager, current_user
from flask_migrate import Migrate
from config import config
from models import db, User
from auth import auth_bp, make_google_bp
from api import api_bp
from stripe_billing import billing_bp


def create_app(config_name: str = None) -> Flask:
    """Application factory."""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'production')
        if config_name not in config:
            config_name = 'production'

    app = Flask(__name__)
    app.config.from_object(config[config_name])

    # ── EXTENSIONS ────────────────────────────────────────────────────────────
    db.init_app(app)
    Migrate(app, db)

    # ── LOGIN MANAGER ─────────────────────────────────────────────────────────
    login_manager = LoginManager()
    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'
    login_manager.login_message = 'Please sign in to continue.'
    login_manager.login_message_category = 'info'

    @login_manager.user_loader
    def load_user(user_id: str):
        return User.query.get(user_id)

    # ── OAUTH INSECURE TRANSPORT (dev only) ───────────────────────────────────
    if app.config.get('OAUTHLIB_INSECURE_TRANSPORT') == '1':
        os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

    # ── BLUEPRINTS ────────────────────────────────────────────────────────────
    google_bp = make_google_bp()
    app.register_blueprint(google_bp,  url_prefix='/auth')
    app.register_blueprint(auth_bp,    url_prefix='/auth')
    app.register_blueprint(api_bp)
    app.register_blueprint(billing_bp)

    # ── MAIN ROUTES ───────────────────────────────────────────────────────────
    @app.route('/')
    def index():
        if current_user.is_authenticated:
            if current_user.has_profile:
                return redirect(url_for('dashboard'))
            return redirect(url_for('setup'))
        return render_template('landing.html')

    @app.route('/app')
    def dashboard():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if not current_user.has_profile:
            return redirect(url_for('setup'))
        return render_template('dashboard.html', user=current_user)

    @app.route('/setup')
    def setup():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        if current_user.has_profile:
            return redirect(url_for('dashboard'))
        return render_template('setup.html', user=current_user)

    @app.route('/profile')
    def profile():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template('profile.html', user=current_user)

    @app.route('/history')
    def history():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template('history.html', user=current_user)

    @app.route('/tracker')
    def tracker():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template('tracker.html', user=current_user)

    @app.route('/digest')
    def digest():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template('digest.html', user=current_user)

    @app.route('/interview')
    def interview():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template('interview.html', user=current_user)

    @app.route('/linkedin')
    def linkedin():
        if not current_user.is_authenticated:
            return redirect(url_for('auth.login'))
        return render_template('linkedin.html', user=current_user)

    @app.route('/pricing')
    def pricing():
        return render_template('pricing.html', user=current_user)

    @app.route('/privacy')
    def privacy():
        return render_template('privacy.html')

    @app.route('/health')
    def health():
        return jsonify({'status': 'ok', 'version': '2.0'})

    # ── API: Usage status ─────────────────────────────────────────────────────
    @app.route('/api/usage')
    def usage():
        if not current_user.is_authenticated:
            return jsonify({'error': 'Unauthorized'}), 401
        limits = app.config['TIER_LIMITS'][current_user.tier]
        used   = current_user.analyses_this_month or 0
        cap    = limits['analyses_per_month']
        return jsonify({
            'tier':       current_user.tier,
            'tier_label': current_user.tier_label,
            'used':       used,
            'limit':      cap,
            'unlimited':  cap == 999,
            'remaining':  max(0, cap - used) if cap != 999 else 999,
        })

    # ── ERROR HANDLERS ────────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return render_template('error.html', code=404,
                               message='Page not found.'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('error.html', code=500,
                               message='Something went wrong.'), 500

    # ── DB INIT ───────────────────────────────────────────────────────────────
    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
