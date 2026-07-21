# StudyFlow Development Guide

This guide documents how the StudyFlow codebase is structured and the key conventions to follow when contributing.

## Project Overview

StudyFlow is a lecture video player that automatically adjusts playback speed based on the complexity of the material being presented.

The core workflow is:

1. Upload a lecture video.
2. Extract and transcribe the audio.
3. Divide the transcript into timestamped sections.
4. Estimate the cognitive complexity of each section.
5. Generate an adaptive playback profile.
6. Adjust the video playback rate as the lecture plays.

The product should remain focused on adaptive lecture playback. Do not add unrelated education features such as quizzes, flashcards, summaries, tutoring, or lecture chat unless explicitly requested.

## Project Tech Stack

* **Frontend**: Next.js with React and TypeScript

  * Tailwind CSS
  * shadcn/ui where appropriate
  * TanStack Query for server state
  * Vitest and React Testing Library
  * Playwright for end-to-end tests
* **Backend**: FastAPI with Python

  * Pydantic for validation
  * SQLAlchemy for database access
  * Alembic for migrations
  * Pytest for testing
* **Database**: PostgreSQL
* **Background Jobs**: Redis with Celery
* **Media Processing**: FFmpeg and FFprobe
* **AI Providers**:

  * OpenAI-compatible transcription provider
  * OpenAI structured output for complexity classification
* **Storage**: Local filesystem during development

## Repository Structure

```text
studyflow/
├── apps/
│   ├── web/
│   │   ├── app/
│   │   ├── components/
│   │   ├── features/
│   │   ├── hooks/
│   │   ├── lib/
│   │   └── tests/
│   └── api/
│       ├── app/
│       │   ├── api/
│       │   ├── core/
│       │   ├── db/
│       │   ├── models/
│       │   ├── repositories/
│       │   ├── schemas/
│       │   ├── services/
│       │   ├── providers/
│       │   └── workers/
│       └── tests/
├── docker-compose.yml
├── Makefile
├── .env.example
└── AGENTS.md
```

## Commands

### Project

* Install dependencies: `make setup`
* Start the development environment: `make dev`
* Run all tests: `make test`
* Run linting: `make lint`
* Run type checks: `make typecheck`
* Build the project: `make build`

### Frontend

Run commands from `apps/web`.

* Start frontend: `npm run dev`
* Run tests: `npm test`
* Run a specific test: `npm test -- path/to/test`
* Run linting: `npm run lint`
* Run type checks: `npm run typecheck`
* Run Playwright tests: `npm run test:e2e`

### Backend

Run commands from `apps/api`.

* Start API: `uvicorn app.main:app --reload`
* Run tests: `pytest`
* Run a specific test: `pytest path/to/test.py::test_name`
* Run linting: `ruff check .`
* Run formatting: `ruff format .`
* Run type checks: `mypy app`
* Create a migration: `alembic revision --autogenerate -m "description"`
* Run migrations: `alembic upgrade head`

### Infrastructure

* Start PostgreSQL and Redis: `docker compose up -d`
* Stop infrastructure: `docker compose down`
* View service logs: `docker compose logs -f`

## 1. Keep the Product Focused

StudyFlow has one core responsibility:

> Generate and play an adaptive playback profile for a lecture video.

Do not add adjacent education features unless explicitly requested.

Avoid adding:

* lecture summaries
* flashcards
* quizzes
* note generation
* AI tutoring
* chat with the lecture
* user profiles
* social features
* subscriptions
* video export

A feature should directly improve uploading, processing, understanding, or playing a lecture.

## 2. Build Vertical Slices

Prefer implementing complete user workflows over isolated layers.

A good development slice is:

```text
upload video
→ create processing job
→ show progress
→ generate playback profile
→ display lecture player
```

Do not fully build every backend abstraction before the frontend can demonstrate the feature.

The first complete version should use mock transcription and classification providers. Replace them with real providers after the workflow works end to end.

## 3. Keep API Routes Thin

FastAPI route handlers should only:

* validate request data
* authorize access when applicable
* call an application service
* serialize the response

Do not place media processing, database orchestration, or model-provider logic directly inside route handlers.

```python
# Good
@router.post("/lectures")
async def create_lecture(
    upload: UploadFile,
    service: LectureService = Depends(get_lecture_service),
) -> LectureCreatedResponse:
    return await service.create(upload)


# Bad
@router.post("/lectures")
async def create_lecture(upload: UploadFile):
    file_path = save_file(upload)
    audio_path = run_ffmpeg(file_path)
    transcript = openai.audio.transcriptions.create(...)
    ...
```

## 4. Use Services for Workflows

Use service objects for multi-step application workflows.

Examples:

```text
LectureService
LectureProcessingService
TranscriptionService
PlaybackProfileService
MediaService
```

Services may coordinate repositories, providers, and domain functions.

Keep services focused. Do not create one global service that handles the entire application.

## 5. Keep Provider Code Behind Interfaces

External AI and infrastructure providers must be replaceable.

Use protocols or abstract base classes for:

* transcription
* complexity classification
* storage
* job dispatching
* OCR

```python
class TranscriptionProvider(Protocol):
    async def transcribe(self, audio_path: Path) -> TranscriptResult:
        ...
```

Provider implementations may include:

```text
MockTranscriptionProvider
OpenAITranscriptionProvider
LocalWhisperTranscriptionProvider
```

Business logic must not depend directly on an SDK response format.

Convert provider responses into internal Pydantic models at the provider boundary.

## 6. Treat AI Output as Untrusted Input

All AI responses must use structured output and be validated before use.

Validate:

* required fields
* timestamp ranges
* complexity score bounds
* playback-rate bounds
* missing or overlapping segments
* invalid category values

Do not parse free-form prose when a structured response can be requested.

Do not store raw AI responses as the authoritative domain result.

## 7. Separate Classification from Playback Rules

The model estimates complexity.

Application code determines playback behavior.

The model should return values such as:

```json
{
  "complexityScore": 4,
  "category": "DENSE_CONCEPT",
  "reason": "Introduces several related concepts using multi-step reasoning.",
  "confidence": 0.88
}
```

The backend should map that score to a playback rate.

```python
PLAYBACK_RATE_BY_COMPLEXITY = {
    1: 2.0,
    2: 1.5,
    3: 1.0,
    4: 0.85,
    5: 0.75,
}
```

Do not let the model select arbitrary playback rates.

## 8. Keep Playback Logic in the Frontend

The backend generates an ordered playback profile.

The frontend is responsible for:

* tracking the current video time
* finding the active playback segment
* changing `video.playbackRate`
* showing the active segment
* handling seeking
* allowing adaptive playback to be disabled

Do not make API requests while the lecture is playing merely to determine the current speed.

Do not repeatedly assign the same playback rate.

## 9. Avoid Jittery Playback

Playback changes should feel intentional.

Apply these rules when generating the final profile:

* Avoid segments shorter than 15 seconds.
* Merge adjacent segments with the same playback rate.
* Merge insignificant complexity changes.
* Avoid extreme jumps between adjacent rates.
* Use `1.0×` when classifier confidence is low.
* Keep playback rates within configured minimum and maximum values.

Prefer fewer meaningful speed changes over constant adjustments.

## 10. Background Processing

Lecture analysis must run outside the HTTP request lifecycle.

The API should:

1. Save the uploaded file.
2. Create a lecture record.
3. Create a processing job.
4. Enqueue the job.
5. Return immediately.

The worker should process stages independently:

```text
media inspection
→ audio extraction
→ transcription
→ segmentation
→ classification
→ smoothing
→ playback profile generation
```

Each stage should update job status and progress.

Do not hide a long-running task inside a FastAPI background task in production code.

## 11. Processing States

Use explicit workflow states.

```text
QUEUED
PROCESSING
COMPLETED
FAILED
```

Track the current processing stage separately.

```text
VALIDATING
INSPECTING_MEDIA
EXTRACTING_AUDIO
TRANSCRIBING
SEGMENTING
CLASSIFYING
GENERATING_PROFILE
```

State transitions should be handled through model or service methods rather than scattered field assignments.

```python
job.mark_processing(stage=ProcessingStage.TRANSCRIBING)
job.mark_completed()
job.mark_failed(code="TRANSCRIPTION_FAILED", message=message)
```

## 12. Database Practices

* Use SQLAlchemy models only for persistence.
* Use Pydantic schemas at API and provider boundaries.
* Keep complex workflow logic out of database models.
* Use database constraints for simple invariants.
* Use application code for cross-record and workflow validation.
* Add indexes for foreign keys and frequently queried status fields.
* Always generate Alembic migrations.
* Do not manually edit an existing applied migration.
* Do not place business logic inside database triggers or stored procedures.

Use database constraints for:

* non-null fields
* foreign keys
* unique identifiers
* positive file sizes
* valid timestamp ordering where practical

## 13. Data Access

Use repositories for database access.

Examples:

```text
LectureRepository
ProcessingJobRepository
TranscriptRepository
PlaybackProfileRepository
```

Repositories should perform queries and persistence only.

Do not place AI calls, FFmpeg execution, or workflow orchestration inside repositories.

Collection endpoints must be paginated.

Avoid loading complete transcripts or playback profiles unless the endpoint requires them.

## 14. Media Handling

Treat uploaded media as untrusted.

Always:

* generate server-controlled filenames
* validate the file extension and MIME type
* inspect media with FFprobe
* enforce upload-size limits
* enforce video-duration limits
* keep uploads outside executable directories
* prevent directory traversal
* delete incomplete artifacts when appropriate

Never construct paths directly from user-provided filenames.

Use FFmpeg through a dedicated media service.

Do not spread subprocess calls throughout the codebase.

## 15. Frontend Organization

Organize frontend code by feature.

```text
features/
├── lecture-upload/
├── lecture-processing/
├── lecture-player/
├── playback-timeline/
└── transcript/
```

Each feature may contain:

```text
components/
hooks/
api/
schemas/
utils/
```

Use shared components only when they are genuinely reused.

Do not move a component into a global shared directory solely because it might be reused later.

## 16. Server State and Local State

Use TanStack Query for:

* lecture data
* processing status
* transcripts
* playback profiles
* retries

Use React state or refs for:

* current playback time
* current adaptive segment
* player controls
* temporary UI state

Do not mirror server state into local React state without a specific reason.

## 17. Semantic, Native HTML

Prefer semantic HTML and browser-native functionality.

Examples:

* Use `<video>` for video playback.
* Use `<button>` for actions.
* Use `<progress>` for processing progress where appropriate.
* Use `<dialog>` for modal dialogs.
* Use accessible form labels.
* Use native file inputs for uploads.

Do not build custom JavaScript replacements for reliable native browser features without a clear need.

## 18. Validation Approach

Validate only at system boundaries and where domain invariants require it.

System boundaries include:

* user uploads
* API request data
* environment variables
* external provider responses
* FFmpeg and FFprobe output

Do not add defensive validation for impossible internal states guaranteed by types or framework behavior.

Frontend validation improves user experience but does not replace backend validation.

## 19. Error Handling

Use typed application exceptions and stable error codes.

Examples:

```text
UNSUPPORTED_MEDIA_TYPE
UPLOAD_TOO_LARGE
VIDEO_TOO_LONG
MEDIA_INSPECTION_FAILED
AUDIO_EXTRACTION_FAILED
TRANSCRIPTION_FAILED
CLASSIFICATION_FAILED
INVALID_PROVIDER_RESPONSE
LECTURE_NOT_FOUND
PROCESSING_FAILED
```

Catch errors at the appropriate boundary.

Do not wrap every function in `try/except`.

Do not use broad `except Exception` blocks unless:

* logging unexpected failures at a worker boundary
* converting the failure into a stable job state
* re-raising or preserving the original exception context

Do not expose stack traces, local paths, provider responses, or secrets to the frontend.

## 20. Testing

### Backend

Use Pytest.

Test:

* API routes
* service workflows
* repository queries
* transcript segmentation
* complexity-to-speed mapping
* smoothing and merging
* processing state transitions
* provider-response validation
* video range requests

Use fixtures sparingly.

Keep base factories minimal and create edge cases directly inside tests.

Mock external providers through their interfaces.

Do not make real paid API calls in tests.

### Frontend

Use Vitest and React Testing Library.

Test:

* upload validation
* processing progress
* failed processing states
* timeline rendering
* click-to-seek behavior
* adaptive playback toggling
* playback-rate changes at segment boundaries

Use Playwright for the core end-to-end flow.

```text
upload lecture
→ processing completes
→ player loads
→ timeline appears
→ playback speed changes
```

Avoid testing implementation details.

Test observable behavior.

## 21. Mock Mode

The complete application must work without API credentials.

Use:

```text
PROCESSING_MODE=mock
```

Mock mode should:

* accept a real uploaded video
* simulate processing progress
* return a realistic transcript
* return multiple playback segments
* demonstrate automatic speed changes

Do not create a separate fake UI for demo mode.

Mock mode should use the same application workflow and interfaces as real processing.

## 22. Minimize Dependencies

* Prefer platform and framework features before adding dependencies.
* Only add dependencies with a clear technical need.
* Prefer stable and well-maintained packages.
* Avoid dependencies for trivial utility functions.
* Do not introduce multiple libraries that solve the same problem.
* Keep frontend bundles and backend environments reasonably small.

Before adding a dependency, verify that the existing stack cannot solve the problem cleanly.

## 23. Optimize for Clarity

Prefer readable code over clever code.

* Use descriptive names.
* Keep functions focused.
* Make state transitions explicit.
* Avoid deeply nested conditionals.
* Avoid premature optimization.
* Document why a non-obvious decision exists.
* Do not comment code that is already self-explanatory.

Performance work should focus on meaningful bottlenecks such as:

* uploading large videos
* FFmpeg processing
* transcription duration
* repeated provider calls
* loading long transcripts

Do not optimize trivial operations.

## 24. Keep It Simple

Avoid over-engineering.

Only implement what is directly requested or clearly required for the core workflow.

* Do not add abstractions for one-time operations.
* Do not build for hypothetical multi-cloud support.
* Do not add user accounts before they are needed.
* Do not add permanent object storage during the initial MVP.
* Do not add OCR before transcript-based classification works.
* Do not refactor unrelated code while implementing a feature.
* Do not add configurable behavior without a current use case.
* Do not add fallbacks for scenarios that cannot reasonably occur.
* Prefer changing internal code over introducing compatibility shims.

The right level of complexity is the minimum required to keep the current code clear, testable, and functional.

## 25. Logging

Use structured logging.

Include identifiers where available:

```text
request_id
lecture_id
job_id
processing_stage
provider
duration_ms
error_code
```

Do not log:

* API keys
* full transcript contents
* uploaded video data
* authorization headers
* raw provider responses containing lecture content

Log processing stage duration so slow steps can be identified.

## 26. Environment Configuration

All environment-specific values must come from environment variables.

Keep `.env.example` current.

Expected variables include:

```text
APP_ENV
DATABASE_URL
REDIS_URL
MEDIA_STORAGE_PATH
PROCESSING_MODE
OPENAI_API_KEY
TRANSCRIPTION_MODEL
CLASSIFICATION_MODEL
MAX_UPLOAD_SIZE_MB
MAX_VIDEO_DURATION_MINUTES
MIN_PLAYBACK_RATE
MAX_PLAYBACK_RATE
```

Validate configuration when the application starts.

Do not commit secrets or machine-specific paths.

## Common Patterns

### Provider Pattern

Use providers for external services.

```python
class ComplexityClassifier(Protocol):
    async def classify(
        self,
        segments: list[TranscriptSegment],
    ) -> list[ComplexityResult]:
        ...
```

Implementations:

```text
MockComplexityClassifier
OpenAIComplexityClassifier
```

### Service Pattern

Use services to orchestrate workflows.

```python
class LectureProcessingService:
    def __init__(
        self,
        lectures: LectureRepository,
        jobs: ProcessingJobRepository,
        media: MediaService,
        transcription: TranscriptionProvider,
        classifier: ComplexityClassifier,
    ) -> None:
        ...
```

### Repository Pattern

Use repositories for persistence.

```python
class LectureRepository:
    async def get(self, lecture_id: UUID) -> Lecture | None:
        ...

    async def create(self, lecture: Lecture) -> Lecture:
        ...
```

### Structured Provider Results

Convert external responses immediately.

```python
class ComplexityResult(BaseModel):
    start_seconds: float
    end_seconds: float
    complexity_score: int = Field(ge=1, le=5)
    category: ComplexityCategory
    reason: str
    confidence: float = Field(ge=0, le=1)
```

### Processing Failure Handling

Worker-level failures should preserve completed artifacts and mark the job as failed.

```python
try:
    await processing_service.process(job_id)
except ProcessingError as error:
    await jobs.mark_failed(
        job_id,
        code=error.code,
        message=error.user_message,
    )
    raise
```

## Coding Agent Expectations

When working in this repository:

1. Read the relevant existing code before making changes.
2. Follow established patterns before introducing new ones.
3. Implement only the requested behavior.
4. Keep route handlers and UI components focused.
5. Keep external providers behind interfaces.
6. Preserve mock mode.
7. Add or update tests for behavioral changes.
8. Run formatting, linting, type checks, and relevant tests.
9. Update documentation when commands or architecture change.
10. Do not refactor unrelated code.

When requirements are ambiguous, choose the simplest implementation that supports the current user workflow.
