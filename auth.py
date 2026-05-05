"""
Google OAuth Authentication
Sprint Fix: Resolve redirect loop after OAuth callback.
"""
import os
from flask import Blueprint, redirect, url_for, flash, session, current_app, request
from flask_dance.contrib.google import make_google_blueprint, google
from flask_login import login_user, logout_user, login_required, current_user
from models import db, User
from datetime import datetime, timezone

auth_bp = Blueprint('auth', __name__)


def make_google_bp():
    """Create and return the Google OAuth blueprint."""
    app_url = os.environ.get('APP_URL', '').rstrip('/')
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
    """Redirect to Google OAuth — never redirect if already logged in here."""
    return redirect(url_for('google.login'))


@auth_bp.route('/after-login')
def after_login():
    """Handle post-OAuth redirect — called after Google approves login."""

    # If not authorized by Google yet, go home
    if not google.authorized:
        current_app.logger.warning('after_login called but google.authorized=False')
        return redirect('/')

    try:
        resp = google.get('/oauth2/v2/userinfo')
        if not resp.ok:
            current_app.logger.error(f'userinfo failed: {resp.status_code}')
            return redirect('/')

        info      = resp.json()
        google_id = info.get('id')
        email     = info.get('email', '')
        name      = info.get('name', email.split('@')[0] if email else 'User')
        avatar    = info.get('picture', '')

        if not google_id or not email:
            current_app.logger.error('Missing google_id or email in userinfo')
            return redirect('/')

        # Find or create user
        user = User.query.filter_by(google_id=google_id).first()
        if not user:
            user = User.query.filter_by(email=email).first()
            if user:
                # Existing user — link Google ID
                user.google_id  = google_id
                user.avatar_url = avatar
            else:
                # Brand new user
                user = User(
                    google_id  = google_id,
                    email      = email,
                    name       = name,
                    avatar_url = avatar,
                )
                db.session.add(user)

        user.last_login = datetime.now(timezone.utc)
        db.session.commit()

        # Log in and set session
        login_user(user, remember=True)

        current_app.logger.info(f'User logged in: {email}')

        # Decide where to send them
        if not user.has_profile:
            # New user — needs to set up profile
            try:
                from email_service import send_welcome_email
                send_welcome_email(user)
            except Exception as e:
                current_app.logger.warning(f'Welcome email failed: {e}')
            return redirect('/setup')

        # Existing user — go to dashboard
        return redirect('/app')

    except Exception as e:
        current_app.logger.error(f'Login error: {e}', exc_info=True)
        return redirect('/')


@auth_bp.route('/logout')
def logout():
    """Log out current user."""
    try:
        session.clear()
        logout_user()
    except Exception:
        pass
    return redirect('/')


@auth_bp.route('/delete-account', methods=['POST'])
@login_required
def delete_account():
    """Permanently delete user account and all data."""
    user = current_user
    session.clear()
    logout_user()
    db.session.delete(user)
    db.session.commit()
    return redirect('/')
