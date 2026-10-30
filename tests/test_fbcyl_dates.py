"""The day of a FBCYL game in Python (#681): ``stats.time`` is ``Oct 3, 2026, 6:30:00 PM`` today (a comma after the year and a narrow no-break space before ``PM``) and was
``Oct 4, 2025 7:00:00 PM``; ``stats.startDate`` is not in the documents."""
import pytest

from src.utils.time_utils import fbcyl_game_day

CURRENT = "Oct 3, 2026, 6:30:00\u202fPM"


@pytest.mark.parametrize("raw, day", [
    (CURRENT, "2026-10-03"),
    ("Oct 4, 2025 7:00:00 PM", "2025-10-04"),                  # the older writing
    ("Mar 1, 2026 1:00:00 PM", "2026-03-01"),
    ("Nov 11, 2026, 12:05:00\u202fAM", "2026-11-11"),
    ("  Oct 3, 2026, 6:30:00\u202fPM  ", "2026-10-03"),
])
def test_the_day_of_a_game_in_both_writings(raw, day):
    assert fbcyl_game_day(raw) == day


@pytest.mark.parametrize("raw", [None, "", "not a date", "Foo 3, 2026, 6:30:00\u202fPM", "Oct 32, 2026, 6:30:00\u202fPM"])
def test_what_is_not_a_date_has_no_day(raw):
    assert fbcyl_game_day(raw) == ""


def test_the_lineup_repository_reads_the_current_writing_regression():
    """Bug (#681): ``_parse_fbcyl_date`` only knew the older writing and answered the first 10 characters of the text (``Oct 3, 202``) for the current one."""
    from src.database.repository_lineup import LineupRepositoryMixin

    parse = LineupRepositoryMixin._parse_fbcyl_date
    assert parse(None, CURRENT) == "2026-10-03" and parse(None, "Mar 1, 2026 1:00:00 PM") == "2026-03-01"
