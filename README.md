# Daily Texts

Fetch [Moravian Daily Texts](https://www.moravian.org/the-daily-texts/), localize scripture to Traditional Chinese (RCUV), translate the daily prayer, and export to Markdown, HTML, and plain text.

## Architecture

Clean Architecture with ports and adapters:

- **Providers** — fetch raw English content (Phase 1: HTML sidebar scraper)
- **BibleService** — RCUV lookup via FHL API
- **Translators** — prayer translation (OpenAI)
- **Formatters** — Markdown / HTML / text output
- **Publishers** — interface only in Phase 1 (LINE, Email, Telegram, Website stubs)

## Setup

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
# Set OPENAI_API_KEY in .env (or set TRANSLATOR=noop for offline)
```

## Usage

```bash
# Fetch today's daily text
daily-texts fetch

# Fetch a specific date (validates against widget date)
daily-texts fetch --date 2026-07-31

# Force overwrite existing output
daily-texts fetch --force

# Offline / tests without OpenAI
TRANSLATOR=noop daily-texts fetch

# Run the daily scheduler (Asia/Taipei 00:00 by default; also retries at configured hours)
daily-texts run-scheduler
```

Output is written to `output/{YYYY-MM-DD}/daily-text.{md,html,txt}`.

## Configuration

See `.env.example` for all options.

Translation uses a **CompositeTranslator** chain by default:

```
TRANSLATOR=composite
TRANSLATORS=openai,anthropic,local,fallback
```

Order: OpenAI → Anthropic → Local (Ollama-compatible) → Fallback (keep English). Unavailable providers are skipped; the first successful translation wins.


## Tests

```bash
pytest
```

## License & Attribution (Milestone 2 — pending)

Phase 1 is for personal / development use. Before any production publish:

1. Confirm Moravian / IBOC content reuse terms (contact [moravianiboc@mcnp.org](mailto:moravianiboc@mcnp.org) as needed).
2. Review FHL / RCUV licensing: [信望愛版權說明](https://www.fhl.net/main/fhl/fhl8.html).
3. Add formal attribution, robots / rate-limit policy, and a `REQUIRE_LICENSE_ACK` gate for publishers.

Sources used by this project:

- Daily Texts widget: [moravian.org/the-daily-texts](https://www.moravian.org/the-daily-texts/)
- Scripture text: FHL Bible API (`version=rcuv`, Traditional Chinese)
