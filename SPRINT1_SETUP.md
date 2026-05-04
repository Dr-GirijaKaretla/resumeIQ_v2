# ResumeIQ v2 — Sprint 1 Setup Guide

## Step 1 — Push to GitHub

```bash
cd resumeiq-v2
git init
git add .
git commit -m "Sprint 1: Auth + Knowledge Graph"
git branch -M main
git remote add origin https://github.com/Dr-GirijaKaretla/ResumeIQ-v2.git
git push -u origin main
```

## Step 2 — Create Railway Project

1. Go to railway.app → New Project → Deploy from GitHub
2. Select the `ResumeIQ-v2` repo
3. Railway will detect the `Procfile` automatically

## Step 3 — Add PostgreSQL Database

1. In Railway dashboard → click **+ New** → **Database** → **PostgreSQL**
2. Click on the PostgreSQL service
3. Go to **Variables** tab
4. Copy the `DATABASE_URL` value

## Step 4 — Add All Environment Variables

In Railway → your Flask service → **Variables** tab, add:

```
SECRET_KEY              = (generate a random 32-char string)
FLASK_ENV               = production
ANTHROPIC_API_KEY       = sk-ant-...
DATABASE_URL            = (paste from PostgreSQL service)
GOOGLE_CLIENT_ID        = (from Google Cloud Console)
GOOGLE_CLIENT_SECRET    = (from Google Cloud Console)
APP_URL                 = https://your-app.up.railway.app
```

## Step 5 — Set Up Google OAuth

1. Go to console.cloud.google.com
2. Create a new project: "ResumeIQ"
3. Go to APIs & Services → OAuth consent screen
   - User type: External
   - App name: ResumeIQ
   - Add scopes: email, profile, openid
4. Go to APIs & Services → Credentials
   - Create OAuth 2.0 Client ID
   - Application type: Web application
   - Authorized redirect URIs: 
     `https://your-app.up.railway.app/auth/google/authorized`
5. Copy Client ID and Client Secret to Railway variables

## Step 6 — Deploy

Railway auto-deploys after every push to main.
Watch the deployment logs for any errors.

## Step 7 — Test the Flow

1. Visit your Railway URL
2. Click "Sign in with Google"
3. After login → redirected to /setup
4. Upload a resume
5. Review extracted profile
6. Save → redirected to /app dashboard

## Verify These Work

- [ ] Google login works
- [ ] Resume uploads successfully
- [ ] Knowledge graph shows correct data
- [ ] Profile review screen shows extracted info
- [ ] Save profile works
- [ ] Dashboard loads after setup
- [ ] /health returns {"status": "ok"}

## Sprint 2 Preview

Once Sprint 1 is live and tested:
- Job URL fetching
- Quality gate (65% threshold)  
- Full analysis
- Resume rewrite
- STAR cover letter
- Recruiter email
- PDF download
