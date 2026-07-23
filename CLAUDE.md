# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Generates Instagram Story ads (1080x1920) for Hielito, an Argentine ice-delivery business in Zona Sur, Buenos Aires. Content is written in Spanish (Rioplatense). Two entry points:

- `hielito_story_generator_V2.py` — generates a single story. This is the active, maintained module; everything else imports from it.
- `hielito_campaign_generator.py` — generates 2-6 variant proposals from a single objective, plus a comparison sheet (`comparativa.jpg`).
- `hielito_daily_story.py` — generates the day's story (via `obtener_prompt_del_dia`, a weekday → objective/creative_concept map) and publishes it as an Instagram Story through Meta's Graph API. Publishing logic lives in `instagram_publisher.py`.

`hielito_story_generator.py` (no `_V2` suffix) is an earlier version kept in the repo but not imported by anything else — treat it as legacy, not a dependency to update alongside V2.

## Commands

```bash
# Install
python -m pip install -r requirements.txt

# Run all tests
python -m unittest -v

# Run a single test file / case
python -m unittest test_hielito_story_generator.py -v
python -m unittest test_hielito_story_generator.StoryContentValidationTests.test_rejects_free_delivery -v

# Local generation (no OpenAI, Pillow-rendered templates)
python hielito_story_generator_V2.py --weather hot --temp 32 --stock medium

# OpenAI-written copy with local fallback
python hielito_story_generator_V2.py --use-openai --weather hot --temp 32 --stock medium \
  --objective "Promocionar bolsas para eventos del fin de semana"

# Full OpenAI-generated story (image model draws everything, no Pillow overlay)
python hielito_story_generator_V2.py --require-openai --full-openai-story --auto-reference \
  --creative-concept producto --objective "Promocionar la bolsa de 15 kg a $6500"

# Multi-proposal campaign
python hielito_campaign_generator.py --objective "Promocionar la bolsa de 15 kg para eventos" \
  --variants 3 --cost-profile draft --concepts producto evento comercio

# Regenerate the local Pillow template pack (assets/templates/*.png)
python hielito_story_generator_V2.py --generate-templates

# Generate + publish the day's story as an Instagram Story (Graph API)
python hielito_daily_story.py --cost-profile balanced
python hielito_daily_story.py --dry-run   # generate only, skip publishing
```

`OPENAI_API_KEY` (and optionally `OPENAI_MODEL`, `OPENAI_IMAGE_MODEL`) is read from a local `.env` (see `.env.example`). Publishing to Instagram additionally needs `IG_ACCESS_TOKEN` and `IG_BUSINESS_ACCOUNT_ID`, and benefits from `NGROK_AUTHTOKEN` (see below).

## Architecture

### Data flow

1. **Context** (`build_context`): CLI args (`--weather`, `--temp`, `--stock`, `--hour`, `--day`, brand overrides) plus `assets/brand_config.json` are combined into a `StoryContext` (weekday/hour/weather/business). `--hour`/`--day` let you simulate any point in time deterministically.
2. **Content**: either
   - `build_story_content` — picks a strategy (`choose_strategy`: e.g. `friday_push`, `heat_push`, `limited_stock`) from weekday/hour-bucket/weather/stock, then a hardcoded Spanish copy variant for that strategy, or
   - `generate_story_content_with_openai` — calls the Responses API with `business_facts.json` as the only source of truth, parses into the `GeneratedStoryContent` Pydantic model, then runs `validate_story_content` before accepting it.
3. **Image**: one of three renderers, selected by CLI flags:
   - `render_story` — pure Pillow, draws text over a local template PNG (`assets/templates/`) or a generated gradient.
   - `render_story_on_ai_background` (`--use-openai-image`) — OpenAI generates a background photo only (no text/logo), Pillow overlays the copy/CTA/logo on top.
   - `generate_complete_openai_story` (`--full-openai-story`) — OpenAI's image model generates the *entire* finished ad (photography, layout, typography, logo, price) in one call, given an exact "visible copy" block it must render verbatim. No Pillow drawing involved. Output is flagged `requires_visual_review: true` in metadata because image models can still distort text/numbers.
4. **Output**: PNG + JSON metadata written to `output/` (campaigns go to `output/campaigns/<campaign_id>/`). Metadata records `content_source` (`openai`/`local`) and `image_source` (`pillow`/`openai`/`openai-full-story`) so generated pieces can be audited.

### Business-fact guardrails

`business_facts.json` is the single source of truth for prices, weights, delivery zones, WhatsApp number, and prohibited claims (no free/guaranteed-immediate delivery, no unverifiable certifications). Any OpenAI-generated copy is validated against it by `validate_story_content` before use — it checks for prohibited phrases, unauthorized prices/weights (cross-checked against `products`), and an incomplete/wrong WhatsApp number. If validation fails: `--use-openai` silently falls back to local copy; `--require-openai` raises and aborts.

`business.json` (no `_facts` suffix) is a separate file of **historical creative references only** — per `content_rules.historical_content_policy` in `business_facts.json`, its prices/promotions/promises must never be treated as current commercial data.

### Reference images and creative concepts

`CREATIVE_CONCEPTS` (`asado`, `evento`, `producto`, `comercio`) are canned English art-direction prompts fed to the image model. `referencias/reference_library.json` tags each image in `referencias/` with which concepts it suits; `--auto-reference` picks a random matching one, `--reference-image` sets one explicitly. Reference images only steer visual style — the prompt explicitly forbids copying their text/logos/claims (see `reference_library.json`'s own `notes` field).

### Cost control

Image generation is the expensive part. `IMAGE_QUALITY_PROFILES` maps `--cost-profile` (`draft`/`balanced`/`final`) to OpenAI image `quality` (`low`/`medium`/`high`). In the campaign generator, `--unique-copy` generates separate copy per variant (default: one shared copy across all variants), `--local-copy` skips the text API call entirely, and `final`-quality campaigns with more than 2 variants require `--allow-expensive` to proceed (see `calculate_call_plan` and the guard in `hielito_campaign_generator.main`).

### Prompt construction for full-story generation

`build_full_openai_story_prompt` assembles a large, structured prompt (canvas spec, safe areas, color palette, layout hierarchy, and a `VISIBLE COPY TO RENDER` block with exact strings). The image model is instructed to render only those exact strings and nothing else. When editing this prompt, keep the "internal layout labels vs. rendered text" distinction intact — tests assert specific substrings survive (see `test_full_story_prompt_has_exact_copy_and_safe_areas`).

### Daily Instagram publishing

`hielito_daily_story.py` wires a weekday to an objective/creative-concept pair (`ESTRATEGIA_POR_DIA` / `obtener_prompt_del_dia`), generates the full story image via `generate_complete_openai_story` (same OpenAI Images API path as `hielito_story_generator_V2.py` — no browser automation), then hands the saved PNG to `instagram_publisher.publicar_historia`.

Publishing uses Meta's Graph API Content Publishing endpoints (`{ig_user_id}/media` with `media_type=STORIES`, poll `status_code` until `FINISHED`, then `{ig_user_id}/media_publish`), which is the only supported way to post programmatically — it requires an Instagram professional account linked to a Facebook Page, a Meta for Developers app, and an access token with `instagram_content_publish`. Deliberately out of scope: scraping ChatGPT's web UI or automating the Instagram web/mobile UI with a persistent browser session — both violate the respective platforms' terms of service and risk account suspension; this repo already has direct OpenAI API access, so there is no reason to drive the ChatGPT web app instead.

Because the Graph API requires a public image URL rather than a file upload, `instagram_publisher.iniciar_hosting_temporal` briefly serves the single generated file from a local `ThreadingHTTPServer` under a random unguessable path, tunnels it with `pyngrok`, and tears the tunnel/server down (`detener_hosting_temporal`) as soon as Meta has fetched it — see the `finally` block in `publicar_historia`. Configure `NGROK_AUTHTOKEN` to avoid anonymous-tier ngrok rate limits.
