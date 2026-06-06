import sys
import time
from stages.ocean import find_lookalikes
from stages.prospeo import find_decision_makers
from stages.eazyreach import resolve_emails
from stages.brevo import send_emails
from utils.helpers import get_logger, deduplicate

log = get_logger()

BANNER = """
╔══════════════════════════════════════════════╗
║        Automated Cold Outreach Pipeline      ║
║  seed domain → lookalikes → contacts → send  ║
╚══════════════════════════════════════════════╝
"""


def show_preview(contacts, limit=3):
    print(f"\n  {'NAME':<25} {'TITLE':<30} {'EMAIL':<35} COMPANY")
    print("  " + "-" * 100)
    for c in contacts[:limit]:
        name = (c.get("name") or "Unknown")[:24]
        title = (c.get("title") or "Unknown")[:29]
        email = (c.get("email") or "")[:34]
        domain = c.get("domain", "")
        print(f"  {name:<25} {title:<30} {email:<35} {domain}")
    if len(contacts) > limit:
        print(f"\n  ... and {len(contacts) - limit} more contacts\n")


def run(seed_domain):
    print(BANNER)
    log.info(f"Starting pipeline for seed domain: {seed_domain}")
    start = time.time()

    # ── stage 1 ──────────────────────────────────────────────────────────
    print("\n[1/4] 🔍 Finding lookalike companies via Ocean.io...")
    domains = find_lookalikes(seed_domain, limit=3)

    if not domains:
        log.error("Stage 1 returned no domains. Check your Ocean.io API key and try again.")
        sys.exit(1)

    print(f"  ✦ Found {len(domains)} lookalike companies:")
    for idx, domain in enumerate(domains, 1):
        print(f"    {idx}. {domain}")
    print()

    # ── stage 2 ──────────────────────────────────────────────────────────
    print("[2/4] 👥 Finding decision makers via Prospeo...")
    contacts = find_decision_makers(domains)

    if not contacts:
        log.error("Stage 2 returned no contacts. Either all domains failed or API credits ran out.")
        sys.exit(1)

    print(f"  ✦ Found {len(contacts)} senior contacts:")
    for contact in contacts:
        print(f"    • {contact.get('name')} ({contact.get('title')}) @ {contact.get('domain')}")
    print()

    # ── stage 3 ──────────────────────────────────────────────────────────
    print("[3/4] ✉️ Resolving work emails via Eazyreach...")
    verified = resolve_emails(contacts)

    if not verified:
        log.error("Stage 3 could not resolve any emails. Check Eazyreach credits.")
        sys.exit(1)

    # deduplicate before sending - dont want to email the same person twice
    verified = deduplicate(verified)
    print(f"  ✦ Resolved {len(verified)} verified email addresses:")
    for contact in verified:
        print(f"    • {contact.get('name')} ➔ {contact.get('email')}")
    print()

    # ── safety checkpoint ─────────────────────────────────────────────────
    print("┌────────────────────────────────────────────────────────┐")
    print(f"│           READY TO SEND OUTREACH EMAILS ({len(verified):<3})            │")
    print("└────────────────────────────────────────────────────────┘")
    show_preview(verified, limit=3)

    try:
        confirm = input("  Confirm send? (y/n): ").strip().lower()
    except KeyboardInterrupt:
        print("\n  Cancelled.")
        sys.exit(0)

    if confirm != "y":
        print("  Aborted. No emails were sent.")
        sys.exit(0)

    # ── stage 4 ──────────────────────────────────────────────────────────
    print("\n[4/4] 🚀 Sending emails via Brevo...")
    sent = send_emails(verified)

    elapsed = round(time.time() - start, 1)
    print(f"\n✓ Done. {sent}/{len(verified)} emails sent in {elapsed}s")
    print("  Check logs/ folder for the full run log.\n")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("\nUsage:  python main.py company.com\n")
        print("Example: python main.py stripe.com\n")
        sys.exit(1)

    domain = sys.argv[1].strip().lower()

    # strip https/http if someone pastes a full URL by mistake
    domain = domain.replace("https://", "").replace("http://", "").rstrip("/")

    run(domain)
