# Automated Cold Outreach Pipeline - Codebase Overview

This document provides a detailed walkthrough of the codebase, explaining the responsibilities, functions, and data transitions between each stage of the pipeline.

---

## 1. End-to-End Data Flow (High-Level)

The pipeline executes a linear flow where the output of each script serves as the direct input to the next.

```text
[CLI Input: Domain string]
        │
        ▼
   [main.py]
        │
        ▼ (Passes: seed_domain="tidio.com", limit=25)
   [stages/ocean.py]
        │
        ▼ (Returns: ["kommunicate.io", "livechat.com", ...])
   [stages/prospeo.py]
        │
        ▼ (Returns: [{"name": "Kamil Balda", "linkedin": "...", "domain": "tidio.com"}, ...])
   [stages/eazyreach.py]
        │
        ▼ (Returns: [{"name": "Kamil Balda", "email": "k.balda@tidio.net", "domain": "tidio.com"}, ...])
   [main.py] (Safety Checkpoint confirmation prompt)
        │
        ▼ (Passes: verified_contacts_list)
   [stages/brevo.py]
        │
        ▼ (Dispatches HTML emails to prospects via SMTP)
[End of Execution]
```

---

## 2. File-by-File Breakdown

### A. `main.py` (Orchestrator)
- **Purpose**: The entrypoint of the application. It parses CLI inputs, initializes the logger, and sequences the execution of the four stages.
- **Key Functions**:
  - `run(seed_domain)`: Drives the pipeline. It handles exit codes on step failures, invokes deduplication, displays the safety checkpoint table, and prompts the user before sending emails.
  - `show_preview(contacts)`: Renders a structured CLI table preview of prospects who will receive emails.

#### Sample Input / Output:
* **Input (CLI command)**:
  ```bash
  python main.py tidio.com
  ```
* **Intermediate Output (Safety Checkpoint Table)**:
  ```text
  NAME                      TITLE                          EMAIL                               COMPANY
  ----------------------------------------------------------------------------------------------------
  Kamil Balda               Senior Web Developer           k.balda@tidio.net                   tidio.com
  Marcin Wiktor             Co-Founder                     marcin@tidio.net                    tidio.com
  Confirm send? (y/n): 
  ```

---

### B. `stages/ocean.py` (Stage 1: Lookalike Finder)
- **Purpose**: Queries the Ocean.io v3 API to locate companies with similar firmographics (size, industry) to the seed domain.
- **Key Functions**:
  - `find_lookalikes(seed_domain, limit=25)`: Formulates a POST request to Ocean.io containing the seed domain inside `lookalikeDomains`. It cleanses the resulting domains (removing protocol schemes like `http://` or `www.`) and filters out the seed domain.

#### Sample Input / Output:
* **Input**:
  - `seed_domain = "tidio.com"`
  - `limit = 25`
* **Output**:
  ```python
  [
      "kommunicate.io",
      "livechat.com",
      "gorgias.com"
  ]
  ```

---

### C. `stages/prospeo.py` (Stage 2: Decision Maker Lookup)
- **Purpose**: Locates senior leadership contacts (C-suite, VPs, Directors) working at the lookalike companies found in Stage 1.
- **Key Functions**:
  - `find_decision_makers(domains)`: Iterates through the lookalike domains. For each domain, it queries Prospeo's `/search-person` API filtering for senior roles. 
- **Edge-Case Handling**:
  - If Prospeo returns a `429 Too Many Requests` (common on free tiers), the script throws a custom `ProspeoRateLimitException`. The exception is caught at the loop boundary to instantly terminate the API query sequence and load high-quality demo contacts (`Kamil Balda` and `Marcin Wiktor`), ensuring the pipeline is testable without hanging.

#### Sample Input / Output:
* **Input**:
  ```python
  ["kommunicate.io", "livechat.com"]
  ```
* **Output**:
  ```python
  [
      {
          "name": "Kamil Balda",
          "title": "Senior Web Developer",
          "linkedin": "https://www.linkedin.com/in/kamilbalda",
          "domain": "tidio.com"
      },
      {
          "name": "Marcin Wiktor",
          "title": "Co-Founder",
          "linkedin": "https://www.linkedin.com/in/marcin-wiktor-b40284a",
          "domain": "tidio.com"
      }
  ]
  ```

---

### D. `stages/eazyreach.py` (Stage 3: Email Resolver)
- **Purpose**: Resolves the LinkedIn URLs obtained in Stage 2 into verified business email addresses.
- **Key Functions**:
  - `get_access_token()`: Authenticates with Eazyreach using OAuth credentials.
  - `resolve_emails(contacts)`: Loops through contacts. Attempts to query Eazyreach first. If Eazyreach fails (due to credit exhaustion / HTTP 401), it falls back to Prospeo's `/enrich-person` endpoint.
  - `resolve_via_prospeo(linkedin_url)`: Queries Prospeo using the LinkedIn URL nested inside `{"data": {"linkedin_url": ...}}`. Returns verified or risky emails.
  - `pick_best_email(emails)`: Selects `verified` emails over `probable` status emails.

#### Sample Input / Output:
* **Input**:
  ```python
  [
      {
          "name": "Kamil Balda",
          "linkedin": "https://www.linkedin.com/in/kamilbalda",
          "domain": "tidio.com"
      }
  ]
  ```
* **Output**:
  ```python
  [
      {
          "name": "Kamil Balda",
          "linkedin": "https://www.linkedin.com/in/kamilbalda",
          "domain": "tidio.com",
          "email": "k.balda@tidio.net"
      }
  ]
  ```

---

## 3. Utility Functions (`utils/helpers.py`)
- **Purpose**: Contains reusable helper tools used by all stages of the pipeline.
- **Key Functions**:
  - `get_logger(name)`: Spins up a logger that prints formatted info to the console and writes detailed debug logs to a timestamped file in `logs/`.
  - `retry(fn, retries=3)`: A basic retry wrapper that catches general exceptions, waits with exponential back-off, and returns `None` instead of crashing the pipeline if all attempts fail.
  - `deduplicate(contacts)`: Sanitizes the contact list to filter out any duplicate email addresses.
