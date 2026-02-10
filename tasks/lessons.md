# WONTECH — Lessons Learned

> Updated after every correction or mistake. Rules for preventing repeat errors.

---

## OpenAI Realtime API

1. **System prompt size matters.** 47-table schema dump (~9.7K chars) caused the model to behave erratically — calling random tools and not generating audio responses. Whitelist only essential tables (~22) to keep the prompt under ~6K chars. The Realtime API is much more sensitive to prompt size than the Chat API.

2. **Function call output size matters.** Large arrays (1000+ rows) sent back via `conversation.item.create` can choke the WebRTC data channel. Always truncate arrays to ~20 items before sending back to the model. Render full data locally.

3. **VAD `speech_started` can be triggered by speaker echo.** The OpenAI Realtime API's server VAD can mistake audio from the speaker as new user speech. Don't clear data visualizations on `speech_started` — only clear text. Let `renderData()` manage the data lifecycle when new results arrive.

## Database Schema Gotchas

4. **Per-tenant DB tables are inconsistent about `organization_id`.** Some tables (attendance, payroll_history, employees) have `organization_id`. Others (sales_history, invoices, products, ingredients) don't — they're inherently scoped by the per-tenant DB. Always check with `PRAGMA table_info()` before writing queries.

5. **`sales_history` uses `sale_date`, not `date`.** Column naming is inconsistent across tables. Never assume column names — verify with PRAGMA.

## Python / Environment

6. **Use venv Python explicitly.** `python` may fail (permission denied on macOS). Always use `/Users/dell/WONTECH/venv/bin/python` for script execution.
