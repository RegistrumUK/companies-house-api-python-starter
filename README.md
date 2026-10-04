# companies-house-api-python-starter

A Python starter kit for the [UK Companies House REST API](https://developer.company-information.service.gov.uk) -- the free, official register of every UK company. This repo covers the three things that trip almost everyone up on their first integration:

- **Auth** -- CH uses HTTP Basic Auth with your key as the username, not a bearer token or `X-API-Key` header
- **Rate limits** -- 600 requests per 5-minute rolling window, with a `429` + `Retry-After` you need to respect
- **iXBRL vs PDF** -- filed accounts are only sometimes structured data; a lot of the time they're a flat PDF with nothing to parse

One file, no framework, nothing to configure beyond an API key.

## Get an API key

Free, official, no credit card: [developer.company-information.service.gov.uk](https://developer.company-information.service.gov.uk). Register an application, generate a REST API key, and you're in -- usually approved within minutes.

## Quick start

```bash
pip install -r requirements.txt
export CH_API_KEY=your_key_here
python example.py
```

```python
import requests

# The auth gotcha: your API key is the HTTP Basic Auth *username*.
# The password is left empty. This is not a bearer token.
response = requests.get(
    "https://api.company-information.service.gov.uk/company/00445790",
    auth=(CH_API_KEY, ""),
)
print(response.json()["company_name"])  # TESCO PLC
```

## The gotchas, in detail

### 1. Auth is Basic Auth, not a header

Most REST APIs today use `Authorization: Bearer <token>` or a custom header. Companies House predates that convention -- your key goes in as the HTTP Basic Auth username with an empty password:

```python
requests.get(url, auth=(api_key, ""))
```

Sending it as `X-API-Key` or `Authorization: Bearer <key>` returns a `401` that doesn't tell you what you did wrong.

### 2. Rate limits: 600 req / 5 min, and you need to back off correctly

Each key is capped at 600 requests per rolling 5-minute window. Exceed it and you get a `429` with a `Retry-After` header telling you how many seconds to wait. `example.py`'s `request_with_backoff()` reads that header instead of guessing a fixed sleep time -- guessing wrong either wastes time or gets you rate-limited again immediately.

### 3. Pagination uses `start_index`, not a page number

Officer, PSC, and filing-history endpoints return `items`, `items_per_page`, `start_index`, and `total_results`. There's no `page=2` parameter -- you increment `start_index` by your page size and stop when it reaches `total_results`. Code that only reads the first page will silently drop officers on any company with a long appointment history.

### 4. Filed accounts are metadata first, document second -- and often a plain PDF

`filing-history` tells you a set of accounts was filed and links to a `document_metadata` URL. That metadata lists which content types are actually available for that filing, under `resources`. This is the step people skip -- and it matters, because a large share of UK companies (small companies and micro-entities in particular) file accounts as flat, sometimes scanned, PDFs with **no structured iXBRL data at all**. If you build a parser assuming iXBRL will always be there, it'll work in testing on large companies and then silently fail across most of your real dataset. Check `resources` first; don't find out from a parse failure three steps downstream.

`get_latest_accounts_status()` in `example.py` shows the full check.

## Example: who owns this company? (PSC)

[`psc_example.py`](psc_example.py) fetches a company's persons with significant control and walks corporate owners up to the people behind them, using the [Registrum API](https://registrum.co.uk) (a free `REGISTRUM_API_KEY`, sent as an `X-API-Key` header -- not your Companies House key):

```bash
export REGISTRUM_API_KEY=your_key_here
python psc_example.py [company_number]
```

```
Ownership chain for RAW PROPERTY MANAGEMENT LTD:
  Wheatley Group Ltd (corporate-entity) -- Owns 75-100% of shares, ... [Companies House 10981633]
    Mrs Abigail Wheatley (individual) -- Owns 25-50% of shares, ... [identity verification: pending]
      -> ultimate owner (a person)
```

Two things it handles that are easy to get wrong: a corporate owner's `company_number` is only set for a confirmed Companies House registration (otherwise it is null and `registry_name` / `registry_number` say where it is registered), and `verification_status` is not a boolean -- `pending` is a deadline not yet passed, `unknown` is no record, and only `overdue` is a missed deadline.

## Beyond the raw API

This repo is a thin, honest wrapper around the official CH API -- it doesn't hide any of the above, it just handles it correctly. If you'd rather not deal with iXBRL parsing, pagination loops, and your own caching layer at all, [Registrum](https://registrum.co.uk) sits on top of the same official data and returns:

- Structured financials already parsed out of iXBRL, with a per-response `data_quality` block -- `completeness`, `fields_extracted`, `missing_fields`, `taxonomy_version` -- so you can see exactly how much of a filing was recovered rather than trusting it blindly, and a clear `unavailable_reason` when accounts are PDF-only
- **ECCTA identity-verification status** per company, ahead of the 18 November 2026 deadline, with `pending` (deadline not yet passed) and `overdue` (deadline missed) as separate counters -- they are not the same thing, and treating verification as a boolean misreports most of the register during the transition
- Director networks traversed to 2 degrees in one call
- PSC / beneficial ownership decoded to plain English, including corporate chains walked up to the ultimate owners
- Built-in caching, so you rarely hit the 600 req/5min ceiling in the first place

Free tier, no credit card: [registrum.co.uk](https://registrum.co.uk) -- 50 calls/month, or browse without a key at all. Live limits and pricing are always at [`GET /v1/plans`](https://api.registrum.co.uk/v1/plans).

Wiring UK company data into an AI agent instead? See [registrum-mcp-examples](https://github.com/RegistrumUK/registrum-mcp-examples). Prefer Node? [companies-house-api-node-starter](https://github.com/RegistrumUK/companies-house-api-node-starter) is this same kit in JavaScript.

## License

Code in this repo is MIT licensed. Companies House data is published under the [Open Government Licence v3.0](https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/).
