# StudyFlow

Adaptive lecture player. Upload a video and it transcribes the audio, scores how conceptually
dense each section is, and builds a playback profile — fast through the parts you already know,
back to normal speed for anything dense. The reasoning behind each speed change is shown in the
player, not hidden.

## Running it

Requirements: Python 3.11+, Node 20+.

```bash
make setup
cd apps/api && ../../.venv/bin/uvicorn app.main:app --reload
```

In a second terminal:

```bash
cd apps/web && npm run dev
```

Open http://localhost:3000. Signing in takes you to the upload page. The header has a link to
your library, where a lecture can be deleted, retried if processing failed, or a new one added
via a small popup.

Mock mode (default) needs no API keys and runs the same code path as production, just with a
mock transcription/classification provider.

## Real providers

```dotenv
OPENAI_API_KEY=your-key
TRANSCRIPTION_PROVIDER=openai
CLASSIFICATION_PROVIDER=openai
```

For a real Celery worker instead of the in-process dev one, set `PROCESSING_MODE=celery`, start
Redis (`docker compose up -d redis`), and run:

```bash
cd apps/api && ../../.venv/bin/celery -A app.workers.celery_app:celery_app worker --loglevel=info
```

Full variable list is in `.env.example`.

## Notes on how it's built

- FastAPI routes are thin, delegate to services. SQLAlchemy + Alembic for persistence.
- Transcription, classification, and job dispatch are all behind small protocols, so mock and
  real (OpenAI / Celery) implementations swap in via config, not code changes.
- Long lectures get split into audio chunks for transcription and stitched back into one
  transcript, since transcription APIs cap request duration.
- Videos are served via short-lived signed URLs rather than a permanently open endpoint.
- The player applies the playback profile locally once it has one — no polling or requests while
  the video is actually playing.
- Player controls (play/pause, skip, captions, fullscreen) are custom-built rather than relying
  on the native `<video controls>` bar, since the browser's native controls can't be extended.

## Checks

```bash
make test
make lint
make typecheck
make build
cd apps/web && npx playwright install chromium && make test-e2e
```
