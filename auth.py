"""
Google OAuth Authentication
Using Flask-Dance for OAuth flow.
Force HTTPS for redirect URI in production.
"""
import os
from flask import Blueprint, redirect, url_for, flash, session, current_app
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from datetime import datetime, timezone

auth_bp = Blueprint('auth', __name__)


def make_google_bp():
    """Create and return the Google OAuth blueprint."""
    app_url = os.environ.get('APP_URL', '').rstrip('/')

    # Build explicit https redirect URI
    redirect_url = f"{app_url}/auth/google/authorized"

    return make_google_blueprint(
        client_id     = os.environ.get('GOOGLE_CLIENT_ID'),
        client_secret = os.environ.get('GOOGLE_CLIENT_SECRET'),
        scope=[
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
        ],
        redirect_to  = 'auth.after_login',
        redirect_url = redirect_url,
    )


@auth_bp.route('/login')
def login():
    """Redirect to Google OAuth."""
    if current_user.is_authenticated:
        return redirect(url_for('dashboard'))
    return redirect(url_for('google.login'))


@auth_bp.route('/after-login')
def after_login():
    """Handle post-OAuth redirect."""
    if not google.authorized:
        flash('Login failed. Please try again.', 'error')
        return redirect(url_for('index'))

    try:
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            flash('Could not fetch your Google profile.', 'error')
            return redirect(url_for('index'))

        info      = resp.json()
        google_id = info.get('id')
        email     = info.get('email')
        name      = info.get('name', email.split('@')[0])
        avatar    = info.get('picture', '')

        # Find or create user
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
            if user:
                user.google_id  = google_id
                user.avatar_url = avatar
            else:
                user = User(
                    google_id  = google_id,
                    email      = email,
                    name       = name,
                    avatar_url = avatar,
                )
                db.session.add(user)

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()
        login_user(user, remember=True)

        # New user → send welcome email + go to setup
        if not user.has_profile:
            try:
                from email_service import send_welcome_email
                send_welcome_email(user)
            except Exception as e:
                current_app.logger.warning(f'Welcome email failed: {e}')
            return redirect(url_for('setup'))

        return redirect(url_for('dashboard'))

    except Exception as e:
        current_app.logger.error(f'Login error: {e}')
        flash('Something went wrong during login.', 'error')
        return redirect(url_for('index'))


@auth_bp.route('/logout')
@login_required
def logout():
    """Log out current user."""
    session.pop('google_oauth_token', None)
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@auth_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Permanently delete user account and all data."""
    user = current_user
    logout_user()
    db.session.delete(user)
    db.session.commit()
    flash('Your account and all data have been permanently deleted.', 'info')
    return redirect(url_for('index'))
