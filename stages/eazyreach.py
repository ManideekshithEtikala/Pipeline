import os
import re
import time
import requests
from dotenv import load_dotenv
from utils.helpers import get_logger, retry

load_dotenv()
log = get_logger()

# correct endpoints from docs.eazyreach.app
AUTH_URL = "https://api.superflow.run/b2b/createAuthToken/"
EAZYREACH_URL = "https://api.superflow.run/b2b/linkedin-emails"


def get_access_token():
    """
    exchanges clientId + clientSecret for an auth_token.
    response returns: { status, auth_token, id }
    note: params are camelCase - clientId not client_id
    """
    client_id = os.getenv("EAZYREACH_CLIENT_ID")
    client_secret = os.getenv("EAZYREACH_CLIENT_SECRET")

    if not client_id or not client_secret:
        log.error("EAZYREACH_CLIENT_ID or EAZYREACH_CLIENT_SECRET missing from .env")
        return None

    try:
        r = requests.post(
            AUTH_URL,
            json={
                "clientId": client_id,        # camelCase - important
                "clientSecret": client_secret, # camelCase - important
            },
            headers={"Content-Type": "application/json"},
            timeout=15,
        )
        r.raise_for_status()
        data = r.json()

        # response field is auth_token (snake_case)
        token = data.get("authToken")

        if not token:
            log.error(f"Auth succeeded but no auth_token in response: {data}")
            return None

        log.info("Eazyreach auth token obtained successfully")
        return token

    except requests.exceptions.HTTPError as e:
        log.error(f"Auth failed ({e.response.status_code}): {e.response.text}")
        return None
    except Exception as e:
        log.error(f"Auth request failed: {e}")
        return None


def is_valid_email(email):
    return bool(re.match(r"[^@]+@[^@]+\.[^@]+", email.strip()))


def pick_best_email(emails):
    """
    prefer 'verified' over 'probable'.
    response: emails: [{ email, verification, source }]
    """
    if not emails:
        return None

    for e in emails:
        if e.get("verification", "").lower() == "verified":
            return e.get("email", "").strip()

    for e in emails:
        if e.get("verification", "").lower() == "probable":
            return e.get("email", "").strip()

    return emails[0].get("email", "").strip()


def resolve_via_prospeo(linkedin_url):
    """
    fallback to find email via Prospeo's enrich-person endpoint
    using the linkedin URL of the person.
    """
    api_key = os.getenv("PROSPEO_API_KEY")
    if not api_key:
        return None

    headers = {
        "X-KEY": api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "data": {
            "linkedin_url": linkedin_url
        }
    }

    try:
        r = requests.post(
            "https://api.prospeo.io/enrich-person",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if r.status_code == 200:
            data = r.json()
            person = data.get("person", {})
            email_info = person.get("email", {})
            email = email_info.get("email")
            # we accept VERIFIED and RISKY email status
            if email and email_info.get("status") in ["VERIFIED", "RISKY"]:
                return email.strip().lower()
        elif r.status_code == 429:
            log.warning("Prospeo API rate limit reached, sleeping before retry...")
            time.sleep(2)
    except Exception as e:
        log.warning(f"Prospeo fallback failed for {linkedin_url}: {e}")

    return None


def resolve_emails(contacts):
    """
    resolves linkedin URLs to verified work emails using eazyreach.
    falls back to Prospeo's enrich-person API if eazyreach fails or has zero balance.
    """

    token = get_access_token()
    if not token:
        log.warning("Could not get Eazyreach auth token - will fall back directly to Prospeo")

    headers = {
        "Authorization": f"Bearer {token}" if token else "",
        "Content-Type": "application/json",
    }

    resolved = []
    skipped = 0

    for i, contact in enumerate(contacts, 1):
        linkedin_url = contact.get("linkedin", "").strip()

        if not linkedin_url:
            log.debug(f"  No linkedin URL for {contact.get('name', 'unknown')}, skipping")
            skipped += 1
            continue

        if "linkedin.com/in/" not in linkedin_url:
            log.debug(f"  Malformed linkedin URL, skipping: {linkedin_url}")
            skipped += 1
            continue

        log.info(f"  [{i}/{len(contacts)}] Resolving email for {contact.get('name', linkedin_url)}")
        email = None

        # Try Eazyreach first if we have a token
        if token:
            def make_request(url=linkedin_url):
                payload = {"linkedinUrl": url}  # camelCase
                r = requests.post(
                    EAZYREACH_URL,
                    json=payload,
                    headers=headers,
                    timeout=20,
                )
                r.raise_for_status()
                return r.json()

            data = retry(make_request)
            if data and data.get("status") == "success":
                emails_list = data.get("emails", [])
                email = pick_best_email(emails_list)

        # Fallback to Prospeo if Eazyreach resolution was unsuccessful
        if not email:
            log.info(f"  Eazyreach resolution failed or skipped. Trying Prospeo enrichment fallback...")
            email = resolve_via_prospeo(linkedin_url)

        if not email:
            log.debug(f"  No email found for {contact.get('name')}")
            skipped += 1
            time.sleep(0.5)
            continue

        if not is_valid_email(email):
            log.debug(f"  Invalid email format: {email}")
            skipped += 1
            continue

        resolved.append({**contact, "email": email.lower()})
        log.debug(f"  Resolved: {email}")
        # small pause so we dont hammer the apis
        time.sleep(0.8)

    log.info(f"Emails resolved: {len(resolved)} | Skipped: {skipped}")
    return resolved
