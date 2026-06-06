import os
import time
import requests
from dotenv import load_dotenv
from utils.helpers import get_logger

load_dotenv()
log = get_logger()


def build_subject(contact):
    company = contact.get("domain", "your company").replace(".com", "").replace(".io", "")
    # capitalise first letter so it looks less robotic
    company = company.capitalize()
    return f"Quick question about {company}"


def build_body(contact, from_name="Sender", from_email="sender@company.com"):
    """
    personalized enough to not look spammy but not so long
    that nobody reads it. the goal is to get a reply, not write an essay.
    """
    name = contact.get("name", "")
    first_name = name.split()[0] if name else "there"
    company = contact.get("domain", "your company").replace(".com", "").replace(".io", "").capitalize()
    title = contact.get("title", "")

    # tailor the opener slightly based on their seniority
    title_lower = (title or "").lower()
    if "cto" in title_lower or "technical" in title_lower or "engineering" in title_lower:
        angle = "building intelligent internal tools that save engineering teams hours every week"
    elif "ceo" in title_lower or "founder" in title_lower or "president" in title_lower:
        angle = "helping companies automate their most repetitive workflows using AI"
    elif "marketing" in title_lower or "growth" in title_lower:
        angle = "automating outreach and lead generation pipelines for growth teams"
    else:
        angle = "building AI-powered automation for teams like yours"

    body = f"""Hi {first_name},

I came across {company} while researching companies doing interesting things in your space and wanted to reach out.

I've been working on {angle}. Given what {company} does, I thought it might be relevant.

Would a 15-minute call this week make sense? Happy to keep it short and straight to the point.

Best,
{from_name}
{from_email}"""

    return body


def send_emails(contacts):
    """
    sends the final personalized outreach via brevo's transactional email API.
    brevo is free up to 300 emails/day which is more than enough here.

    important - make sure your FROM_EMAIL is verified in brevo's dashboard
    before running this or the sends will fail silently.
    """
    api_key = os.getenv("BREVO_API_KEY")
    from_email = os.getenv("FROM_EMAIL")
    from_name = os.getenv("FROM_NAME", "")

    if not api_key or not from_email:
        log.error("BREVO_API_KEY or FROM_EMAIL missing from .env")
        return 0

    headers = {
        "api-key": api_key,
        "Content-Type": "application/json",
    }

    sent = 0
    failed = 0

    for i, contact in enumerate(contacts, 1):
        email = contact.get("email", "").strip()
        name = contact.get("name", "")

        if not email:
            continue

        subject = build_subject(contact)
        body = build_body(contact, from_name=from_name, from_email=from_email)
        html_body = body.replace("\n", "<br>")

        payload = {
            "sender": {
                "email": from_email,
                "name": from_name,
            },
            "to": [{"email": email, "name": name}],
            "subject": subject,
            "htmlContent": html_body,
        }

        log.info(f"  [{i}/{len(contacts)}] Sending to {name} <{email}>")

        try:
            r = requests.post(
                "https://api.brevo.com/v3/smtp/email",
                json=payload,
                headers=headers,
                timeout=15,
            )
            r.raise_for_status()
            sent += 1
            log.debug(f"  Sent OK to {email}")
        except requests.exceptions.HTTPError as e:
            log.warning(f"  Failed to send to {email}: {e.response.status_code} - {e.response.text}")
            failed += 1
        except Exception as e:
            log.warning(f"  Unexpected error sending to {email}: {e}")
            failed += 1

        # small pause so brevo doesnt flag us as spammy
        time.sleep(0.5)

    log.info(f"Emails sent: {sent} | Failed: {failed}")
    print(f"\n  Emails sent: {sent} | Failed: {failed}\n")
    return sent
