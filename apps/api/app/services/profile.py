from app.core.config import Settings
from app.schemas.lecture import ComplexityResult, PlaybackSegment


PLAYBACK_RATE_BY_COMPLEXITY = {1: 2.0, 2: 1.5, 3: 1.0, 4: 1.0, 5: 1.0}
LOW_CONFIDENCE_THRESHOLD = 0.65


class PlaybackProfileService:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    def generate(self, results: list[ComplexityResult]) -> list[PlaybackSegment]:
        profile: list[PlaybackSegment] = []
        for result in results:
            requested_rate = (
                1.0
                if result.confidence < LOW_CONFIDENCE_THRESHOLD
                else PLAYBACK_RATE_BY_COMPLEXITY[result.complexity_score]
            )
            rate = min(
                self.settings.max_playback_rate,
                max(self.settings.min_playback_rate, requested_rate),
            )
            segment = PlaybackSegment(
                start_seconds=result.start_seconds,
                end_seconds=result.end_seconds,
                playback_rate=rate,
                complexity_score=result.complexity_score,
                category=result.category,
                reason=result.reason,
            )
            if (
                profile
                and profile[-1].end_seconds == segment.start_seconds
                and profile[-1].playback_rate == segment.playback_rate
            ):
                profile[-1].end_seconds = segment.end_seconds
            else:
                profile.append(segment)
        return profile
