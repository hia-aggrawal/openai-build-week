import pytest

from app.core.config import Settings
from app.schemas.lecture import ComplexityCategory, ComplexityResult
from app.services.profile import (
    LOW_CONFIDENCE_THRESHOLD,
    PLAYBACK_RATE_BY_COMPLEXITY,
    PlaybackProfileService,
)


def result(score: int, confidence: float, start: float = 0, end: float = 20) -> ComplexityResult:
    return ComplexityResult(
        start_seconds=start,
        end_seconds=end,
        complexity_score=score,
        category=ComplexityCategory.EXPLANATION,
        reason="Test reason",
        confidence=confidence,
    )


@pytest.mark.parametrize(
    "results",
    [
        [
            result(1, 0.9, 0, 30),
            result(5, 0.9, 30, 40),
            result(1, 0.9, 40, 70),
        ],
        [
            result(1, 0.9, 0, 20),
            result(2, 0.9, 20, 40),
            result(3, 0.9, 40, 60),
            result(4, 0.9, 60, 80),
        ],
        [
            result(1, 0.9, 0, 30),
            result(5, 0.9, 30, 50),
            result(1, 0.9, 50, 80),
        ],
    ],
    ids=["short-complex-segment", "gradual-ramp", "important-between-easy"],
)
def test_profile_never_exceeds_each_classifications_safe_rate(
    results: list[ComplexityResult],
) -> None:
    settings = Settings()
    profile = PlaybackProfileService(settings).generate(results)

    for classified in results:
        requested_rate = (
            1.0
            if classified.confidence < LOW_CONFIDENCE_THRESHOLD
            else PLAYBACK_RATE_BY_COMPLEXITY[classified.complexity_score]
        )
        safe_rate = min(
            settings.max_playback_rate,
            max(settings.min_playback_rate, requested_rate),
        )
        covering_segments = [
            segment
            for segment in profile
            if segment.start_seconds < classified.end_seconds
            and segment.end_seconds > classified.start_seconds
        ]
        assert covering_segments
        assert all(segment.playback_rate <= safe_rate for segment in covering_segments)


def test_mixed_complexity_produces_varied_playback_rates() -> None:
    profile = PlaybackProfileService(Settings()).generate(
        [
            result(1, 0.9, 0, 30),
            result(2, 0.9, 30, 60),
            result(4, 0.9, 60, 90),
            result(1, 0.9, 90, 120),
        ]
    )

    assert [segment.playback_rate for segment in profile] == [2.0, 1.5, 1.0, 2.0]
    assert len({segment.playback_rate for segment in profile}) > 1


def test_low_confidence_uses_normal_speed() -> None:
    profile = PlaybackProfileService(Settings()).generate([result(1, 0.4)])

    assert profile[0].playback_rate == 1.0


def test_rates_are_clamped_to_configured_bounds() -> None:
    settings = Settings(min_playback_rate=1.25, max_playback_rate=1.75)
    profile = PlaybackProfileService(settings).generate(
        [result(1, 0.9, 0, 20), result(5, 0.9, 20, 40)]
    )

    assert [segment.playback_rate for segment in profile] == [1.75, 1.25]


def test_immediately_adjacent_equal_rates_are_merged() -> None:
    profile = PlaybackProfileService(Settings()).generate(
        [result(3, 0.9, 0, 20), result(5, 0.9, 20, 40)]
    )

    assert len(profile) == 1
    assert profile[0].start_seconds == 0
    assert profile[0].end_seconds == 40
    assert profile[0].playback_rate == 1.0


def test_equal_rates_separated_by_a_gap_are_not_merged() -> None:
    profile = PlaybackProfileService(Settings()).generate(
        [result(2, 0.9, 0, 20), result(2, 0.9, 25, 45)]
    )

    assert len(profile) == 2


def test_important_segment_between_easy_segments_keeps_its_own_rate() -> None:
    profile = PlaybackProfileService(Settings()).generate(
        [
            result(1, 0.9, 0, 30),
            result(5, 0.9, 30, 40),
            result(1, 0.9, 40, 70),
        ]
    )

    assert [segment.playback_rate for segment in profile] == [2.0, 1.0, 2.0]
    assert profile[1].start_seconds == 30
    assert profile[1].end_seconds == 40
