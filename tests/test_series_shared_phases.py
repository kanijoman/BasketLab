"""One ``Series.aspx`` page for several phases (Copa de España), issue #459.

``_build_series_cache`` linked each series link to the FIRST group whose label contains it, so with a single page ``Play-offs`` and one group
per round (``Play-offs 1/16 Final``, ``Play-offs 1/8 Final``) only the first round had series: the 1/8 would have had no matches. Linking all of
them would give every round the matches of all the others, so the codes are filtered by the phase the group label names (the same rule the
calendar uses, ``calendar_parser.phase_matches``).
"""
from unittest.mock import MagicMock

from src.scraper.calendar_parser import CalendarMatch, phase_matches
from src.scraper.feb_scraper import FEBWebScraper

CAL = "https://baloncestoenvivo.feb.es/calendario.aspx?g=73&t=2026&nm=copaespaa"
SERIES = "https://baloncestoenvivo.feb.es/Series.aspx?f=45116"
GROUPS = [("Play-offs 1/16 Final", "1"), ("Play-offs 1/8 Final", "2")]


def tie(phase, code, score="80 - 70"):
    return (f'<h1 class="titulo-modulo">{phase}. A - B</h1><table><tr><td><a href="x/Equipo.aspx?i=1">A</a> - <a href="x/Equipo.aspx?i=2">B</a></td>'
            f'<td><a href="x/Partido.aspx?p={code}">{score}</a></td><td>01/11/2026 20:00</td></tr></table>')


def scraper(series_html, link_label="Play-offs"):
    fases = f'<table id="x_fasesDataList"><tr><td><a href="{SERIES}">{link_label}</a></td></tr></table>'
    pages = {CAL: fases, SERIES: series_html}
    client = MagicMock()
    client.get.side_effect = lambda url, timeout=None: MagicMock(content=pages[url].encode()) if url in pages else None
    return FEBWebScraper(client)


def m(phase):
    return CalendarMatch("1", "scheduled", 1, "1", "A", "2", "B", phase=phase)


class TestPhaseMatches:
    def test_the_most_specific_phase_of_the_label_wins(self):
        assert [x.phase for x in phase_matches([m("Final"), m("1/16 Final")], "Play-offs 1/16 Final")] == ["1/16 Final"]

    def test_without_a_phase_in_the_label_everything_is_kept(self):
        assert len(phase_matches([m("1/4 Final"), m("1/2 Final")], "2ºA-1ºB")) == 2

    def test_matches_without_phase_are_not_filtered_out_when_nothing_matches(self):
        assert len(phase_matches([m(None)], "Play-offs 1/16 Final")) == 1


class TestSharedSeries:
    def test_every_group_the_link_names_gets_the_series_page(self):
        s = scraper(tie("1/16 Final", "10") + tie("1/8 Final", "20"))
        s._build_series_cache(GROUPS, CAL)
        assert s._series_url_by_group == {"1": [SERIES], "2": [SERIES]}

    def test_each_round_gets_only_its_own_matches(self):
        s = scraper(tie("1/16 Final", "10") + tie("1/16 Final", "11", "70 - 60") + tie("1/8 Final", "20"))
        s._build_series_cache(GROUPS, CAL)
        assert s._get_matches_via_series(CAL, "1", "2026") == ["10", "11"]
        assert s._get_matches_via_series(CAL, "2", "2026") == ["20"]

    def test_a_round_not_drawn_yet_has_no_matches_not_those_of_the_others_regression(self):
        s = scraper(tie("1/16 Final", "10"))
        s._build_series_cache(GROUPS, CAL)
        assert s._get_matches_via_series(CAL, "2", "2026") == []

    def test_an_exact_label_is_linked_alone_so_final_does_not_feed_the_semi_final(self):
        """LF2: the ``Final`` link must not also become a source of ``1/2 Final`` just because the text is contained."""
        s = scraper(tie("Final", "30"), link_label="Final")
        s._build_series_cache([("1/2 Final", "5"), ("Final", "6")], CAL)
        assert s._series_url_by_group == {"6": [SERIES]}

    def test_a_series_page_of_a_single_phase_is_not_filtered(self):
        """LF2 style page whose ties are titled with the phase of the link: all its matches belong to the group."""
        s = scraper(tie("1/2 Final", "40") + tie("1/2 Final", "41"), link_label="1/2 Final")
        s._build_series_cache([("1/2 Final", "7")], CAL)
        assert s._get_matches_via_series(CAL, "7", "2026") == ["40", "41"]

    def test_a_page_with_several_phases_and_a_group_named_after_the_series_keeps_everything(self):
        s = scraper(tie("1/4 Final", "50") + tie("1/2 Final", "51"), link_label="2ºA-1ºB")
        s._build_series_cache([("2ºA-1ºB Final", "8")], CAL)
        assert s._get_matches_via_series(CAL, "8", "2026") == ["50", "51"]

    def test_ties_not_played_yet_are_not_ingested(self):
        s = scraper(tie("1/16 Final", "10") + tie("1/16 Final", "11", "* - *") + tie("1/8 Final", "20"))
        s._build_series_cache(GROUPS, CAL)
        assert s._get_matches_via_series(CAL, "1", "2026") == ["10"]
