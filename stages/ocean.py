import os
import time
import requests
from dotenv import load_dotenv
from utils.helpers import get_logger, retry

load_dotenv()
log = get_logger()


def find_lookalikes(seed_domain, limit=1):
    """
    takes a seed domain and returns a list of similar company domains.
    uses ocean.io v3 API to search for companies with tech/industry filters.

    v3 API uses X-Api-Token header (not Bearer) and companiesFilters for searches.
    """
    api_key = os.getenv("OCEAN_API_KEY")
    if not api_key:
        log.error("OCEAN_API_KEY not found in .env - did you fill it in?")
        return []

    headers = {
        "X-Api-Token": api_key,
        "Content-Type": "application/json",
    }

    # v3 API uses companiesFilters for advanced searching
    payload = {
        "companiesFilters": {
            "lookalikeDomains": [seed_domain],
            "companySizes": ["11-50", "51-200", "201-500"],  # mid-market focus
            "industries": {
                "industries": ["SaaS", "Financial Services", "Technology"]
            },
        },
        "size": limit,
    }

    log.info(f"Searching for companies similar to: {seed_domain}")

    def make_request():
        r = requests.post(
            "https://api.ocean.io/v3/search/companies",
            json=payload,
            headers=headers,
            timeout=15,
        )
        r.raise_for_status()
        return r.json()

    data = retry(make_request)

    if not data:
        log.warning("Ocean.io returned nothing - check your API key or the domain you entered")
        return []

    companies = data.get("companies", [])
    domains = []

    for company_wrapper in companies:
        # v3 API returns companies nested under 'company' key
        company = company_wrapper.get("company", {})
        d = company.get("domain", "").strip() or company_wrapper.get("domain", "").strip()
        
        # clean up domain - remove http/https prefixes and www
        if d:
            d = d.replace("https://", "").replace("http://", "").replace("www.", "").split("/")[0]
        
        # skip empties and the seed itself
        if d and d != seed_domain:
            domains.append(d)

    log.info(f"Found {len(domains)} lookalike companies")

    # small pause so we dont hammer the api
    time.sleep(1)
    return domains
