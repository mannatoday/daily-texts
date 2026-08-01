# Daily Texts

Fetch [Moravian Daily Texts](https://www.moravian.org/the-daily-texts/), localize scripture to Traditional Chinese (RCUV), translate the daily prayer, and export to Markdown, HTML, plain text, and JSON.

## Architecture

Clean Architecture with ports and adapters:

- **Providers** — fetch raw English content (HTML sidebar scraper)
- **BibleService** — RCUV lookup via FHL API
- **Translators** — prayer translation (composite chain)
- **Formatters** — Markdown / HTML / text / JSON file outputs
- **Publishers** — `static_site` (GitHub Pages); stubs for LINE, Email, Telegram, Website (S3/CMS)

Conceptual publisher registry:

```text
PublisherRegistry
├── File outputs (formatters → output/{date}/)
│      ├── Markdown / HTML / Text / JSON
├── StaticSitePublisher   → site/{YYYY-MM-DD}.html + index.html
├── WebsitePublisher      (stub)
├── EmailPublisher        (stub)
└── LinePublisher         (stub)
```

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

# Write GitHub Pages files under ./site
PUBLISHERS=static_site daily-texts fetch --force

# Offline / tests without OpenAI
TRANSLATOR=noop daily-texts fetch

# Run the daily scheduler (Asia/Taipei 00:00 by default; also retries at configured hours)
daily-texts run-scheduler
```

File output: `output/{YYYY-MM-DD}/daily-text.{md,html,txt,json}`.

Static site: `site/{YYYY-MM-DD}.html` and `site/index.html` when `PUBLISHERS` includes `static_site`.

### GitHub Pages

1. Repo **Settings → Pages → Source: GitHub Actions**
2. Commit and push updates under `site/` (or run fetch with `static_site` then push)
3. Workflow [`.github/workflows/pages.yml`](.github/workflows/pages.yml) deploys `site/` on push to `master`

See [`site/README.md`](site/README.md).

## Configuration

See `.env.example` for all options.

| Variable | Notes |
|----------|--------|
| `FORMATS` | Default `markdown,html,text,json` |
| `PUBLISHERS` | `null`, `static_site`, or stubs (`website`, `line`, `email`, `telegram`) |
| `SITE_DIR` | Default `./site` |

Translation uses a **CompositeTranslator** chain by default:

```
TRANSLATOR=composite
TRANSLATORS=local,openai,anthropic,google,fallback
```

Order: Local Ollama (`qwen2.5:7b`) → OpenAI → Anthropic → Google → Fallback (keep English). Unavailable providers are skipped; the first successful translation wins.

```bash
ollama serve
ollama pull qwen2.5:7b
```

`.env` should include:

```
LOCAL_TRANSLATOR_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_TRANSLATOR_MODEL=qwen2.5:7b
```


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
