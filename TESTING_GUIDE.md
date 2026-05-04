# ResumeIQ — Complete Testing Guide

## Overview

This guide walks you through every step:
1. Push to GitHub
2. Set up Railway + PostgreSQL
3. Configure Google OAuth
4. Configure Anthropic API key
5. Test every feature end-to-end

---

## PART 1 — PUSH TO GITHUB

### Step 1.1 — Extract the zip
Unzip `resumeiq-v2-final.zip` to a folder called `resumeiq-v2`.

### Step 1.2 — Create GitHub repo
Go to github.com → New repository
- Name: `ResumeIQ`
- Private or Public (your choice)
- Do NOT add README or .gitignore (already included)

### Step 1.3 — Push code
Open terminal in the `resumeiq-v2` folder:

```bash
git init
git add .
git commit -m "ResumeIQ v2 — full build"
git branch -M main
git remote add origin https://github.com/YOUR_USERNAME/ResumeIQ.git
git push -u origin main
```

Verify on GitHub that you see all these files:
```
app.py
api.py
models.py
knowledge_graph.py
tracker.py
job_digest.py
interview_prep.py
linkedin_optimizer.py
pdf_generator.py
email_service.py
stripe_billing.py
auth.py
config.py
templates/ (14 HTML files)
requirements.txt
Procfile
railway.toml
```

---

## PART 2 — RAILWAY SETUP

### Step 2.1 — Create Railway project
1. Go to railway.app → Sign in
2. Click **New Project** → **Deploy from GitHub repo**
3. Select your `ResumeIQ` repo
4. Railway detects the Procfile automatically

### Step 2.2 — Add PostgreSQL database
1. In Railway dashboard → click **+ New** → **Database** → **Add PostgreSQL**
2. Wait ~30 seconds for it to provision
3. Click on the PostgreSQL service → **Variables** tab
4. Copy the `DATABASE_URL` value (starts with `postgresql://`)

### Step 2.3 — Add environment variables
In Railway → your **Flask service** → **Variables** tab, add these one by one:

```
SECRET_KEY          = (any random 32-char string, e.g. abc123xyz789abc123xyz789abc123xy)
FLASK_ENV           = production
DATABASE_URL        = (paste from PostgreSQL service above)
ANTHROPIC_API_KEY   = sk-ant-... (from console.anthropic.com)
APP_URL             = https://your-app.up.railway.app
```

Leave these blank for now (add later):
```
GOOGLE_CLIENT_ID    = (set up in Part 3)
GOOGLE_CLIENT_SECRET= (set up in Part 3)
RESEND_API_KEY      = (optional for emails)
STRIPE_SECRET_KEY   = (optional for payments)
```

### Step 2.4 — Deploy
Railway auto-deploys when you push to GitHub.
Watch the **Deployments** tab — should show green checkmark in ~2 minutes.

### Step 2.5 — Verify health check
Visit: `https://your-app.up.railway.app/health`

Expected response:
```json
{"status": "ok", "version": "2.0"}
```

If you see a 500 error, check **Deployments → View Logs** in Railway.

---

## PART 3 — GOOGLE OAUTH SETUP

### Step 3.1 — Create Google Cloud project
1. Go to console.cloud.google.com
2. Click **Select a project** → **New Project**
3. Name: `ResumeIQ` → Create

### Step 3.2 — Enable Google OAuth
1. Go to **APIs & Services** → **OAuth consent screen**
2. User Type: **External** → Create
3. Fill in:
   - App name: `ResumeIQ`
   - User support email: your email
   - Developer contact: your email
4. Click **Save and Continue** through all steps

### Step 3.3 — Create OAuth credentials
1. Go to **APIs & Services** → **Credentials**
2. Click **+ Create Credentials** → **OAuth client ID**
3. Application type: **Web application**
4. Name: `ResumeIQ`
5. Authorized redirect URIs — add:
   ```
   https://your-app.up.railway.app/auth/google/authorized
   ```
6. Click **Create**
7. Copy **Client ID** and **Client Secret**

### Step 3.4 — Add to Railway
In Railway → Variables:
```
GOOGLE_CLIENT_ID     = 123456789-abc.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET = GOCSPX-your-secret
```

Railway will redeploy automatically.

---

## PART 4 — FEATURE TESTING CHECKLIST

Work through this checklist top to bottom. Each test builds on the previous one.

---

### TEST 1 — Landing Page
**URL:** `https://your-app.up.railway.app/`

✅ What to check:
- [ ] Page loads with dark theme
- [ ] "Sign in with Google" button visible
- [ ] Features section shows all 6 features
- [ ] Pricing link works
- [ ] Privacy link works
- [ ] No console errors (F12 → Console)

---

### TEST 2 — Google Sign-in (Onboarding)
**Click:** "Sign in with Google"

✅ What to check:
- [ ] Redirected to Google consent screen
- [ ] After approving → redirected to `/setup` page
- [ ] Your name and avatar appear in the nav
- [ ] "Free" tier badge shows in nav

---

### TEST 3 — Resume Upload (Knowledge Graph)
**Page:** `/setup`

**Use this sample resume text (copy-paste into the text area):**

```
Jane Smith
Sydney, Australia | jane.smith@email.com

EXPERIENCE
Senior Data Analyst — Acme Financial, Sydney (2022–2025)
• Built customer churn prediction model using Python and XGBoost achieving 91% AUC
• Reduced customer attrition by 18% saving $2.3M annually
• Led team of 4 analysts across 3 projects
• Developed real-time Tableau dashboard processing 2M daily transactions

Data Analyst — TechStart, Melbourne (2020–2022)
• Analysed user behaviour data using SQL and Python for 500K users
• Built A/B testing framework reducing experiment cycle time by 40%

EDUCATION
MS Data Science — University of Sydney, 2020

CERTIFICATIONS
AWS Solutions Architect Associate (2023)
Google Data Analytics Certificate (2024)

SKILLS
Python, SQL, Machine Learning, XGBoost, TensorFlow, Tableau, AWS, Pandas, Scikit-learn

PROJECTS
Customer Churn Model: Built XGBoost model predicting churn with 91% AUC deployed to production
Sales Analytics Dashboard: Real-time Tableau dashboard for 50-person sales team
```

✅ What to check:
- [ ] Upload button triggers loading animation
- [ ] After ~10 seconds → Review Profile screen appears
- [ ] Name extracted: "Jane Smith"
- [ ] Career level detected: "mid"
- [ ] Education shows: "MS Data Science"
- [ ] Skills section shows Python, SQL, etc.
- [ ] Projects section shows 2 projects
- [ ] Completeness bar shows 80%+
- [ ] Click "Save Profile & Start Applying" → redirected to `/app`

---

### TEST 4 — Dashboard and JD URL Fetch
**Page:** `/app`

**Use this Indeed job URL (or any real job URL):**
```
https://au.indeed.com/jobs?q=data+scientist&l=Sydney
```
Or paste directly into the "Job URL" field then click an actual job posting URL.

**Alternatively use the paste tab with this sample JD:**
```
Senior Data Scientist — DataCorp Sydney

We are looking for a Senior Data Scientist to join our growing team.

Requirements:
• 3+ years experience in data science or machine learning
• Strong Python skills including pandas, scikit-learn, TensorFlow
• Experience with SQL and data pipeline development
• AWS or cloud platform experience
• Experience deploying ML models to production
• Strong communication skills

Nice to have:
• Experience with Kubernetes or Docker
• MLOps experience
• Spark or distributed computing

Responsibilities:
• Build and deploy machine learning models
• Collaborate with engineering teams
• Present findings to stakeholders
• Mentor junior team members

Salary: $120,000 - $150,000 AUD
Location: Sydney CBD (hybrid)
```

✅ What to check:
- [ ] URL tab shows by default
- [ ] "Fetch" button calls `/api/fetch-jd`
- [ ] Status shows "✓ Fetched..."
- [ ] JD preview snippet appears
- [ ] Company/Role auto-filled from title
- [ ] OR: paste tab works with sample JD above
- [ ] Fill in: Company = "DataCorp", Role = "Senior Data Scientist"
- [ ] Click "✦ Analyze Match"
- [ ] Loading spinner with cycling messages appears
- [ ] Stage 1 → Stage 2 → Full analysis runs

---

### TEST 5 — Quality Gate (Below Threshold)
**Test the gate with a mismatched JD:**

Paste this JD (completely different field):
```
Senior Surgeon — City Hospital

Requirements:
• MBBS and surgical specialization
• 10+ years surgical experience
• Board certification in general surgery
• Hospital privileges
• Leadership experience in operating theatre
```

✅ What to check:
- [ ] Gate fires with "Match below threshold" message
- [ ] Score shown (should be very low, ~10-20%)
- [ ] "Critical gaps" listed
- [ ] "Try a different job" button works
- [ ] Full analysis NOT run (saves tokens)

---

### TEST 6 — Full Analysis Results
**Go back and run analysis with the Data Scientist JD from Test 4**

✅ What to check:
- [ ] Score ring animates (should be 70-85% for Jane's profile)
- [ ] Letter grade shows (B+ or A-)
- [ ] Summary paragraph appears
- [ ] ATS Score, Interview Odds, Culture Fit stats show
- [ ] 4 section cards render (Skills, Experience, Education, Keywords)
- [ ] Progress bars animate
- [ ] Strengths (3 items) render
- [ ] Gaps (2 items) render
- [ ] Recommendations (3 items) render
- [ ] Salary intelligence card appears (~$120k-$150k AUD)
- [ ] Application Pack section shows with 4 tabs

---

### TEST 7 — Resume Rewrite
**Click: 📄 Resume tab in Application Pack**

✅ What to check:
- [ ] Loading spinner runs
- [ ] Rewritten resume text appears (Free tier shows upgrade message)
- [ ] If Job Hunter+ tier: text shows with proper sections
- [ ] "Copy Text" button works
- [ ] "⬇ Download PDF" triggers download (Job Hunter+)
- [ ] Downloaded PDF opens correctly in PDF viewer

---

### TEST 8 — STAR Cover Letter
**Click: ✍️ Cover Letter tab**

✅ What to check:
- [ ] Cover letter generates (Job Hunter+)
- [ ] Letter has 4-5 paragraphs
- [ ] References Jane's churn model project specifically (STAR technique)
- [ ] No forbidden phrases ("I am passionate about..." etc.)
- [ ] "Copy Text" button works
- [ ] "⬇ Download PDF" works

---

### TEST 9 — Recruiter Email
**Click: 📧 Email tab**

✅ What to check:
- [ ] Email generates (Job Hunter+)
- [ ] Under 8 sentences
- [ ] References a specific achievement with metric
- [ ] Has specific ask ("10 minutes" or "brief call")
- [ ] "Copy for LinkedIn / Email" button works

---

### TEST 10 — Keyword Intelligence
**Click: 🎯 Keywords tab**

✅ What to check:
- [ ] Keyword density score shows
- [ ] Quick Wins chips appear (Kubernetes, Docker, MLOps etc.)
- [ ] Click a Quick Win chip → copies to clipboard
- [ ] Missing keyword accordion items show
- [ ] Expand a keyword → shows JD context, placement strategy, example sentence
- [ ] "Copy" button on example sentence works

---

### TEST 11 — Red Flag Detection
**In URL tab, fetch this real JD (or paste a suspicious JD):**

Paste this to test red flags:
```
URGENT HIRE - Rock Star Developer needed IMMEDIATELY

We need a 10x engineer who can do EVERYTHING:
- Full-stack development
- DevOps and infrastructure
- Data science and ML
- Mobile development
- UX/UI design

Requirements:
- 15 years experience in technologies that are 5 years old
- Available to start TOMORROW
- Competitive salary (we can't tell you what it is)
- Must be passionate and love working long hours

We are a fast-moving startup with amazing culture.
Apply now before this opportunity disappears!
```

✅ What to check:
- [ ] Red flag panel appears above Analyze button
- [ ] "Warning" or "Red Flag" rating shows in red
- [ ] Multiple flags listed (unrealistic experience, vague salary, urgency)
- [ ] Each flag has advice
- [ ] Summary sentence shows

---

### TEST 12 — Sprint 5: Interview Prep
**Click: 🎤 Interview Prep card at bottom of results**
(Career Pro tier — or navigate to `/interview` directly)

✅ What to check:
- [ ] If Career Pro: form shows with JD and company pre-filled from URL params
- [ ] If Free/Job Hunter: upgrade prompt shows
- [ ] Generate → loading runs ~15-20 seconds
- [ ] "Tell Me About Yourself" script appears with Copy button
- [ ] Technical questions accordion — expand one
  - [ ] Model answer references Jane's real experience
  - [ ] Difficulty badge shows
  - [ ] Watch out warning shows
  - [ ] Copy button works
- [ ] Behavioural questions show STAR breakdown (S/T/A/R tabs)
- [ ] Questions to Ask section shows
- [ ] Salary negotiation opening line with Copy button
- [ ] Red flags to avoid list

---

### TEST 13 — Sprint 5: LinkedIn Optimizer
**Navigate to `/linkedin`**
(Career Pro tier)

✅ What to check:
- [ ] Target roles from profile display correctly
- [ ] Generate → loading ~15 seconds
- [ ] Profile strength score ring animates
- [ ] Quick Wins list (5 items)
- [ ] Optimized headline appears with Copy button
- [ ] 2 alternative headlines
- [ ] About summary (300 words) with Copy button
- [ ] Experience bullets for each role
- [ ] Skills to add with priority badges
- [ ] 3 skills to pin highlighted
- [ ] SEO keywords as tags
- [ ] Connection request template with Copy button

---

### TEST 14 — Sprint 6: Application Tracker
**Navigate to `/tracker`**

✅ What to check:
- [ ] Empty state shows with Add button
- [ ] Click "+ Add Application"
- [ ] Modal opens with all fields
- [ ] Fill in: Title = "Senior Data Scientist", Company = "DataCorp"
- [ ] Select status = "Applied"
- [ ] Add applied date = today
- [ ] Save → card appears in "Applied" column
- [ ] Stats strip updates (Total: 1, Active: 1)
- [ ] Click card → Edit modal opens
- [ ] Change status to "Interview" → Save
- [ ] Card moves to Interview column
- [ ] Stats: Interviews: 1
- [ ] Add a second application with status "Offer"
- [ ] Stats: Offers: 1
- [ ] Delete an application → confirm → removed

---

### TEST 15 — Sprint 6: Weekly Digest Preview
**Navigate to `/digest`**
(Career Pro tier)

✅ What to check:
- [ ] If Career Pro: generate button shows
- [ ] If not Career Pro: upgrade prompt shows
- [ ] Click "✦ Preview This Week's Digest"
- [ ] Loading ~15-20 seconds
- [ ] Greeting with name appears
- [ ] Motivation sentence personalised
- [ ] Weekly goal shown
- [ ] 5 job cards render with scores (65-95%)
- [ ] Each card: title, company, location, match score
- [ ] LinkedIn and Indeed search links work
- [ ] Skill spotlight shows
- [ ] "↩ Generate Another" resets

---

### TEST 16 — History Page
**Navigate to `/history`**

✅ What to check:
- [ ] Analysis from Test 6 shows
- [ ] Score bubble with correct color
- [ ] Grade displayed
- [ ] Resume/Cover/Email badges show
- [ ] Click the card → expands inline
- [ ] Summary text shows
- [ ] Strengths/Gaps in 2-column layout
- [ ] Output tabs (Resume, Cover, Email) switch correctly
- [ ] "📧 Email me this summary" sends email (if RESEND_API_KEY set)
- [ ] "⬇ PDF" download works

---

### TEST 17 — Profile Page
**Navigate to `/profile`**

✅ What to check:
- [ ] Profile completeness bar shows
- [ ] All fields pre-filled from knowledge graph
- [ ] Edit name/location → Save Changes
- [ ] Add a certification → Save → appears in profile
- [ ] Skills sections (Expert/Proficient/Familiar) editable
- [ ] Subscription section shows tier + manage link
- [ ] Privacy link in footer works

---

### TEST 18 — Pricing Page
**Navigate to `/pricing`**

✅ What to check:
- [ ] Three tiers display correctly
- [ ] Free / Job Hunter / Career Pro pricing
- [ ] Current plan button is disabled (if logged in)
- [ ] "Start Job Hunter" → triggers Stripe checkout (if STRIPE keys set)
- [ ] Without Stripe keys: shows error gracefully
- [ ] FAQ section renders
- [ ] Trust signals row shows

---

### TEST 19 — Mobile Responsiveness
**Open DevTools (F12) → Toggle Device Toolbar → iPhone 12**

✅ What to check on each page:
- [ ] `/` — Single column layout, text readable
- [ ] `/app` — Input and results stack vertically
- [ ] `/tracker` — Board columns stack to single column
- [ ] Nav links collapse on mobile
- [ ] Buttons are at least 44px tall
- [ ] No horizontal scrolling

---

### TEST 20 — Error Handling
**Test these edge cases:**

1. **Empty resume upload**
   - Go to `/setup`, click "Build My Profile" without text
   - Expected: "Please provide your resume" error shown

2. **Short JD**
   - Paste: "We need a developer" → Analyze
   - Expected: "Job description too short" error

3. **Invalid URL**
   - Type: `notaurl` in URL field → Fetch
   - Expected: "URL must start with https://" error

4. **LinkedIn URL (blocked)**
   - Type: `https://www.linkedin.com/jobs/view/12345`
   - Expected: "LinkedIn requires login" error with helpful message

5. **404 page**
   - Visit: `/this-page-does-not-exist`
   - Expected: Custom 404 page with "Go Home" button

---

## PART 5 — STRIPE SETUP (Optional for payment testing)

Only needed if you want to test the subscription flow.

### Step 5.1 — Create products
Stripe Dashboard → Products → Add Product:
- **Job Hunter**: $9/month recurring → copy Price ID
- **Career Pro**: $19/month recurring → copy Price ID

### Step 5.2 — Add webhook
Stripe → Developers → Webhooks → Add endpoint:
- URL: `https://your-app.up.railway.app/billing/webhook`
- Events: `checkout.session.completed`, `customer.subscription.updated`, `customer.subscription.deleted`, `invoice.payment_failed`
- Copy webhook signing secret

### Step 5.3 — Add to Railway
```
STRIPE_SECRET_KEY        = sk_test_...
STRIPE_PUBLISHABLE_KEY   = pk_test_...
STRIPE_WEBHOOK_SECRET    = whsec_...
STRIPE_JOB_HUNTER_PRICE  = price_...
STRIPE_CAREER_PRO_PRICE  = price_...
```

### Step 5.4 — Test payment
- Click "Start Job Hunter" on pricing page
- Use test card: `4242 4242 4242 4242` | Any future date | Any CVV
- After payment → `/billing/success` page
- Nav badge should change to "Job Hunter"
- All job hunter features unlocked

---

## PART 6 — EMAIL SETUP (Optional)

### Step 6.1 — Create Resend account
Go to resend.com → Sign up → Create API key

### Step 6.2 — Verify domain (optional)
For production: add your domain and verify DNS records.
For testing: use the resend.dev sandbox.

### Step 6.3 — Add to Railway
```
RESEND_API_KEY = re_...
FROM_EMAIL     = hello@yourdomain.com
```

### Step 6.4 — Test emails
- Sign up with a new Google account → should receive welcome email
- Run an analysis → check analysis summary email
- Upgrade subscription → check upgrade confirmation email

---

## TROUBLESHOOTING

### "Internal Server Error" on homepage
→ Check Railway logs for the specific error
→ Most likely: `DATABASE_URL` not set, or `GOOGLE_CLIENT_ID` missing

### "OAuth Error" on Google login
→ Check redirect URI exactly matches: `https://YOUR-APP.up.railway.app/auth/google/authorized`
→ No trailing slash

### "Could not parse JSON" on analysis
→ The AI response was truncated — retry
→ Check ANTHROPIC_API_KEY is valid

### "PDF generation failed"
→ WeasyPrint needs system fonts — add `nixpacks.toml`:
```toml
[phases.setup]
nixPkgs = ["weasyprint", "pango", "cairo", "gdk-pixbuf"]
```

### Database tables not created
→ The app auto-creates tables on startup via `db.create_all()`
→ Check `DATABASE_URL` is correct postgresql:// format

### Knowledge graph shows wrong data
→ Go to `/profile` and manually correct the extracted fields
→ Re-upload resume with more detailed text

---

## MINIMUM REQUIRED ENV VARS FOR BASIC TESTING

```
SECRET_KEY          = any-random-string-32chars
DATABASE_URL        = postgresql://... (from Railway PostgreSQL)
ANTHROPIC_API_KEY   = sk-ant-...
GOOGLE_CLIENT_ID    = ...apps.googleusercontent.com
GOOGLE_CLIENT_SECRET= ...
APP_URL             = https://your-app.up.railway.app
```

Everything else (Stripe, Resend) is optional for basic feature testing.

---

## WHAT EACH TIER CAN DO

| Feature | Free | Job Hunter | Career Pro |
|---------|------|-----------|-----------|
| Resume upload + profile | ✅ | ✅ | ✅ |
| Match score + grade | ✅ | ✅ | ✅ |
| Quality gate | ✅ | ✅ | ✅ |
| Keyword intelligence | ✅ (partial) | ✅ Full | ✅ Full |
| Red flag detection | ✅ | ✅ | ✅ |
| Salary intelligence | ✅ | ✅ | ✅ |
| Analyses per month | 3 | Unlimited | Unlimited |
| Resume rewrite + PDF | ❌ | ✅ | ✅ |
| STAR Cover letter + PDF | ❌ | ✅ | ✅ |
| Recruiter email | ❌ | ✅ | ✅ |
| Application history | ❌ | Last 10 | Unlimited |
| Application tracker | ✅ | ✅ | ✅ |
| Interview prep | ❌ | ❌ | ✅ |
| LinkedIn optimizer | ❌ | ❌ | ✅ |
| Weekly job digest | ❌ | ❌ | ✅ |
| Cover letter tones | ❌ | ❌ | ✅ |
