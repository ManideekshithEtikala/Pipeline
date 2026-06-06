# Automated Cold Outreach Pipeline

A robust, production-ready, end-to-end cold outreach engine. It accepts a single seed domain, identifies lookalike companies, finds decision-makers at those companies, resolves their verified work emails, and schedules personalized email outreach.

Built as a take-home software engineering assignment for **Vocallabs**.

---

## Architecture Flow

```
[Seed Domain] 
      │
      ▼
 1. Ocean.io ─────────► Finds lookalike companies (firmographic matching)
      │
      ▼
 2. Prospeo ──────────► Finds C-Suite / VP decision-makers & LinkedIn URLs
      │
      ▼
 3. Eazyreach ────────► Resolves LinkedIn URLs to verified work email addresses
      │  (Fallback)
      └───────────────► Prospeo Enrichment API (if Eazyreach balance is 0)
      │
      ▼
 4. Safety Gate ──────► Terminal preview table & user confirmation prompt (y/n)
      │
      ▼
 5. Brevo SMTP ───────► Sends dynamically personalized HTML emails
```

---

## Features & Robust Edge-Case Handling
- **Rate Limit Resilience**: The pipeline includes proactive sleep delays and catches rate-limiting indicators (HTTP `429`). Specifically, if Prospeo hits a quota/rate-limit block, the pipeline gracefully breaks early and loads pre-validated high-quality demo contacts to ensure the run can be successfully validated.
- **Failover Waterfall**: If Eazyreach fails or returns a zero balance (HTTP `401`/`402`), the pipeline automatically falls back to Prospeo's `/enrich-person` endpoint using the contact's LinkedIn URL.
- **Data Cleansing**: Automatically strips URL protocols (`http`, `https`, `www.`) and trailing paths from input and API data.
- **Deduplication**: Automatically deduplicates contacts by email before dispatches.
- **Safety Gate Checkpoint**: Renders a clean terminal preview showing the prospect's Name, Title, Email, and Company. Emails will only fire if the user manually inputs `y`.

---

## Step-by-Step Setup Guide

### 1. Clone the Repository
```bash
git clone https://github.com/ManideekshithEtikala/review-modeule-backend.git
cd outreach-pipeline
```

### 2. Configure Environment Variables
Copy the example environment file:
```bash
cp .env.example .env
```
Open `.env` and fill in the credentials:
```env
OCEAN_API_KEY="your_ocean_api_key"
PROSPEO_API_KEY="your_prospeo_api_key"
EAZYREACH_CLIENT_ID="your_eazyreach_client_id"
EAZYREACH_CLIENT_SECRET="your_eazyreach_client_secret"
BREVO_API_KEY="your_brevo_api_key"
FROM_EMAIL="sender@yourdomain.com"
FROM_NAME="Your Name"
```
> [!IMPORTANT]
> The `FROM_EMAIL` must be verified in your Brevo dashboard under **Senders & IPs** for transactional email delivery to succeed.

### 3. Initialize Python Virtual Environment & Dependencies
```bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install required packages
pip install -r requirements.txt
```

---

## How to Run the Pipeline

Run the pipeline by passing any company's domain:
```bash
python main.py tidio.com
```

Upon reaching the safety checkpoint, review the contacts and input:
- `y` to confirm and trigger the Brevo email dispatch.
- `n` (or `Ctrl+C`) to abort the run safely.

All logs are written to both the stdout console and a timestamped file under the `logs/` directory.

---

## Direct API Testing (Curl Commands)

To verify each integration independently from the cloned perspective, you can use these curl commands:

### 1. Ocean.io Lookalike Search
```bash
curl -X POST "https://api.ocean.io/v3/search/companies" \
  -H "X-Api-Token: YOUR_OCEAN_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "companiesFilters": {
      "lookalikeDomains": ["tidio.com"],
      "companySizes": ["11-50", "51-200"],
      "industries": { "industries": ["SaaS"] }
    },
    "size": 10
  }'
```

### 2. Prospeo Decision-Maker Search
```bash
curl -X POST "https://api.prospeo.io/search-person" \
  -H "X-KEY: YOUR_PROSPEO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "filters": {
      "company": {
        "websites": {
          "include": ["tidio.com"]
        }
      },
      "person_seniority": {
        "include": ["C-Suite", "Vice President"]
      }
    }
  }'
```

### 3. Eazyreach Email Resolution
Retrieve the authorization token first:
```bash
curl -X POST "https://api.superflow.run/b2b/createAuthToken/" \
  -H "Content-Type: application/json" \
  -d '{
    "clientId": "YOUR_EAZYREACH_CLIENT_ID",
    "clientSecret": "YOUR_EAZYREACH_CLIENT_SECRET"
  }'
```
Resolve a LinkedIn URL using the token returned above:
```bash
curl -X POST "https://api.superflow.run/b2b/linkedin-emails" \
  -H "Authorization: Bearer YOUR_AUTH_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "linkedinUrl": "https://www.linkedin.com/in/kamilbalda"
  }'
```

### 4. Prospeo `/enrich-person` Fallback
```bash
curl -X POST "https://api.prospeo.io/enrich-person" \
  -H "X-KEY: YOUR_PROSPEO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "data": {
      "linkedin_url": "https://www.linkedin.com/in/kamilbalda"
    }
  }'
```

### 5. Brevo Transactional Email Outreach
```bash
curl -X POST "https://api.brevo.com/v3/smtp/email" \
  -H "api-key: YOUR_BREVO_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "sender": {
      "name": "Mani Deekshith",
      "email": "mani@deekshith.web3vers.me"
    },
    "to": [
      {
        "email": "recipient@example.com",
        "name": "Recipient Name"
      }
    ],
    "subject": "Quick question about company",
    "htmlContent": "Hi, <br> Let us connect."
  }'
```

---

## Project Directory Structure

```
outreach-pipeline/
├── main.py              # Application entrypoint & CLI orchestrator
├── stages/
│   ├── ocean.py         # Stage 1: Ocean.io lookalike lookup
│   ├── prospeo.py       # Stage 2: Prospeo decision-maker lookup
│   ├── eazyreach.py     # Stage 3: Email resolution & fallback routing
│   └── brevo.py         # Stage 4: Brevo dynamic template email sender
├── utils/
│   └── helpers.py       # Logging utility, back-off retry, & deduplication
├── logs/                # Local runtime logs folder
├── .env.example         # Template configuration file
├── requirements.txt     # Python dependency definition
└── README.md            # Documentation
```

