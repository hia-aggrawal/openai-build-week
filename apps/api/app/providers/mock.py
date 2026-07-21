from app.schemas.lecture import ComplexityCategory, ComplexityResult, TranscriptSegment
from app.schemas.media import AudioChunk


class MockTranscriptionProvider:
    provider_name = "mock"

    _text = (
        "Today we will build an intuition for how a system changes over time.",
        "Start with this concrete example and notice how each input affects the result.",
        "The central idea connects several variables, so follow each dependency carefully.",
        "With that model in place, we can apply the same reasoning to a new situation.",
    )

    def transcribe(self, audio_chunks: list[AudioChunk]) -> list[TranscriptSegment]:
        duration_seconds = max(
            chunk.start_offset_seconds + chunk.duration_seconds for chunk in audio_chunks
        )
        count = min(4, max(1, int(duration_seconds // 15)))
        width = duration_seconds / count
        return [
            TranscriptSegment(
                start_seconds=round(index * width, 3),
                end_seconds=round(
                    duration_seconds if index == count - 1 else (index + 1) * width, 3
                ),
                text=self._text[index],
            )
            for index in range(count)
        ]


class MockComplexityClassifier:
    provider_name = "mock"

    _scores = (1, 3, 5, 2)
    _categories = (
        ComplexityCategory.INTRODUCTION,
        ComplexityCategory.EXAMPLE,
        ComplexityCategory.DENSE_CONCEPT,
        ComplexityCategory.EXPLANATION,
    )

    def classify(self, segments: list[TranscriptSegment]) -> list[ComplexityResult]:
        return [
            ComplexityResult(
                start_seconds=segment.start_seconds,
                end_seconds=segment.end_seconds,
                complexity_score=self._scores[index],
                category=self._categories[index],
                reason=(
                    "Foundational material can be reviewed quickly."
                    if index == 0
                    else "The pace reflects the number of connected ideas in this section."
                ),
                confidence=0.92,
            )
            for index, segment in enumerate(segments)
        ]
