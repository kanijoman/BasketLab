"""FEB website scraper for seasons, groups, and matches."""

import re
import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Tuple, Optional

from utils import normalize_year, get_form_field_name, get_event_target
from .constants import (
    BASE_URL, SEASON_DROPDOWN_ID, GROUP_DROPDOWN_ID,
    HIDDEN_FIELDS, EXTENDED_TIMEOUT
)
from .web_client import WebClient


class FEBWebScraper:
    """Scrapes FEB website for calendar and match information."""

    def __init__(self, web_client: WebClient):
        """
        Initialize FEB web scraper.

        Args:
            web_client: WebClient instance
        """
        self.web_client = web_client
        # Maps group_id → list of Series.aspx URLs, populated by _get_fases_groups.
        # A playoff phase (e.g. "1/2 FINAL") can have multiple brackets, each
        # represented by a separate Series.aspx?f=XXXXX page.  All matching URLs
        # are stored so _get_matches_via_series can visit every bracket.
        self._series_url_by_group: Dict[str, List[str]] = {}

    def get_page_content(self, year: str) -> Tuple[BeautifulSoup, requests.Session]:
        """
        Fetch and parse webpage content for the given year.

        Args:
            year: Season year

        Returns:
            Tuple of (BeautifulSoup object, requests.Session)

        Raises:
            Exception if page fetch fails
        """
        norm_year = normalize_year(year)
        url = BASE_URL.format(year=norm_year)

        response = self.web_client.get(url, timeout=EXTENDED_TIMEOUT)
        if not response:
            raise Exception(f"Failed to fetch page for year {year}")

        soup = BeautifulSoup(response.content, "html.parser")
        return soup, self.web_client.get_session()

    def get_seasons(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract season options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (season_text, season_value) tuples
        """
        season_dropdown = soup.find("select", {"id": SEASON_DROPDOWN_ID})
        if not season_dropdown:
            return []

        seasons = []
        for option in season_dropdown.find_all("option"):
            text = option.text.strip()
            if text:
                value = option.get("value", text)
                seasons.append((text, value))

        return seasons

    def get_groups(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """
        Extract group options from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            List of (group_text, group_value) tuples
        """
        group_dropdown = soup.find("select", {"id": GROUP_DROPDOWN_ID})
        if not group_dropdown:
            return []

        groups = []
        for option in group_dropdown.find_all("option"):
            text = option.text.strip()
            if text:
                value = option.get("value", "")
                groups.append((text, value))

        return groups

    def get_groups_for_season(
        self, competition_url: str, season_value: str
    ) -> List[Tuple[str, str]]:
        """Return group options for a given season on a competition page.

        Tries the *resultados* equivalent of the URL first (which shows all
        groups including playoff phases without requiring an ASP.NET postback),
        then falls back to the classic GET + season-selection postback on the
        *calendario* page.

        The FEB website has two page families:
        - ``/calendario/`` – calendar/schedule view, sometimes only shows
          active regular-season groups in the dropdown.
        - ``/resultados/`` – results view, always lists all groups for the
          season (regular + playoff), making it the authoritative source.

        Args:
            competition_url: Full URL of the competition calendar page.
            season_value:    Season dropdown value to select before reading
                             groups (e.g. ``"2025"`` for the 2025/26 season).

        Returns:
            List of (group_label, group_value) tuples, empty on failure.
        """
        try:
            # Attempt 1: derive and fetch the resultados URL for the requested
            # season — this gives ALL groups (including playoffs) in one GET.
            results_url = self._calendar_to_results_url(competition_url, season_value)
            if results_url != competition_url:
                resp = self.web_client.get(results_url, timeout=EXTENDED_TIMEOUT)
                if resp:
                    groups = self.get_groups(BeautifulSoup(resp.content, "html.parser"))
                    if groups:
                        # Build the series URL cache so _get_matches_via_series
                        # can later reach playoff matches that are only on
                        # Series.aspx pages.  Series.aspx has no group dropdown,
                        # so we correlate by label substring matching.
                        self._build_series_cache(groups, competition_url)
                        return groups

            # Attempt 2 (fallback): GET the calendar page, POST to select the
            # season, then supplement with fasesDataList navigation links.
            # The fasesDataList on the calendar page lists playoff phases as
            # <a href="Series.aspx?f=XXXXX"> links that are outside the standard
            # group dropdown.  We GET each Series page and read the selected
            # option in the group dropdown to recover the proper group ID.
            response = self.web_client.get(competition_url, timeout=EXTENDED_TIMEOUT)
            if not response:
                return []
            calendar_soup = BeautifulSoup(response.content, "html.parser")
            hidden_fields = self.get_hidden_fields(calendar_soup)
            session = self.web_client.get_session()
            updated_soup, _ = self.select_season(
                session, competition_url, season_value, hidden_fields
            )
            groups = self.get_groups(updated_soup)
            existing_ids = {v for _, v in groups}
            extra = self._get_fases_groups(calendar_soup, existing_ids)
            # Also build series URL cache for any groups we know about
            if groups or extra:
                self._build_series_cache(groups + extra, competition_url)
            return groups + extra
        except Exception:
            return []

    def _build_series_cache(
        self, groups: List[Tuple[str, str]], calendar_url: str
    ) -> None:
        """Populate ``_series_url_by_group`` using label-substring matching.

        Series.aspx pages do not expose the group dropdown, so the group_id →
        Series URL mapping cannot be obtained by parsing those pages.  Instead,
        we match the short label of each fasesDataList link (e.g. ``"2ºA-1ºB"``)
        against the known group labels from the dropdown
        (e.g. ``"2ºA-1ºB Final"``) using case-insensitive substring containment.

        Args:
            groups:       List of ``(label, group_id)`` tuples already discovered.
            calendar_url: Competition calendar URL used to find fasesDataList.
        """
        try:
            cal_resp = self.web_client.get(calendar_url, timeout=EXTENDED_TIMEOUT)
            if not cal_resp:
                return
            soup = BeautifulSoup(cal_resp.content, "html.parser")
            for fases_label, fases_href in self._find_fases_links(soup):
                norm_fases = fases_label.upper().strip()
                if not norm_fases:
                    continue
                for g_label, g_id in groups:
                    norm_group = g_label.upper().strip()
                    if norm_fases in norm_group or norm_group in norm_fases:
                        urls = self._series_url_by_group.setdefault(g_id, [])
                        if fases_href not in urls:
                            urls.append(fases_href)
                        break
        except Exception:
            pass

    def _find_fases_links(self, soup: BeautifulSoup) -> List[Tuple[str, str]]:
        """Return ``(label, href)`` pairs for every Series.aspx link in fasesDataList.

        The FEB ASP.NET site renders the fasesDataList block differently depending
        on which URL format is requested:

        * **Pretty URL** (``/calendario/lf2/9/2025``): an outer ``<table>`` or
          ``<div>`` element carries an ID that ends with ``fasesDataList``.  The
          ``<a>`` links are children of that container.

        * **ASPX URL** (``calendario.aspx?g=9&t=2025&nm=lf2``): no outer
          container element; the ``<a>`` elements themselves carry IDs of the
          form ``..._fasesDataList__ctl0_seriesHyperLink`` (no parent wrapper
          with a matching ID).

        This method handles both layouts so callers don't need to care which URL
        was requested.
        """
        results: List[Tuple[str, str]] = []
        seen: set = set()

        # Layout 1: outer container whose ID ends with "fasesDataList"
        container = soup.find(id=re.compile(r"fasesDataList$"))
        if container:
            for a in container.find_all("a", href=re.compile(r"Series\.aspx", re.I)):
                href = a.get("href", "").split("#")[0]
                label = a.get_text(strip=True)
                if href and href not in seen:
                    results.append((label or href, href))
                    seen.add(href)
            return results

        # Layout 2: direct <a> elements whose ID contains "fasesDataList"
        for a in soup.find_all("a", href=re.compile(r"Series\.aspx", re.I)):
            if "fasesDataList" not in a.get("id", ""):
                continue
            href = a.get("href", "").split("#")[0]
            label = a.get_text(strip=True)
            if href and href not in seen:
                results.append((label or href, href))
                seen.add(href)
        return results

    def _get_fases_groups(
        self, soup: BeautifulSoup, existing_ids: set
    ) -> List[Tuple[str, str]]:
        """Resolve playoff groups from ``fasesDataList`` navigation links.

        The FEB calendar page shows playoff phases as ``<a>`` links inside the
        ``fasesDataList`` element when those phases are not yet included in the
        standard group dropdown (e.g. when the postback only returns regular-
        season groups).  Each link points to ``Series.aspx?f=XXXXX``.

        We GET each Series page and read the currently selected ``<option>``
        in the group dropdown to recover the proper group ID that can be used
        in form postbacks.  Only returns entries whose IDs are not already in
        ``existing_ids``.

        Args:
            soup:         Parsed HTML of the calendar page.
            existing_ids: Set of group IDs already discovered; updated in-place
                          to avoid duplicates across calls.

        Returns:
            List of (label, group_id) tuples for phases not in existing_ids.
        """
        extra: List[Tuple[str, str]] = []
        for label, href in self._find_fases_links(soup):
            resp = self.web_client.get(href, timeout=EXTENDED_TIMEOUT)
            if not resp:
                continue
            page = BeautifulSoup(resp.content, "html.parser")
            grp_sel = page.find("select", {"id": GROUP_DROPDOWN_ID})
            if not grp_sel:
                continue
            selected_opt = grp_sel.find("option", selected=True)
            if not selected_opt:
                continue
            gid = selected_opt.get("value", "")
            if gid:
                # Always cache the series URL — even when the group already
                # appears in the standard dropdown (found via /resultados/).  The
                # cache is the only reliable way to reach Series.aspx pages after
                # a group-select POST taints the ASP.NET session state.
                urls = self._series_url_by_group.setdefault(gid, [])
                if href not in urls:
                    urls.append(href)
                if gid not in existing_ids:
                    extra.append((label, gid))
                    existing_ids.add(gid)
        return extra

    @staticmethod
    def _calendar_to_results_url(calendar_url: str, season: str) -> str:
        """Derive the FEB results page URL from a calendar URL for a given season.

        FEB exposes two URL formats:
        - Pretty:  ``https://baloncestoenvivo.feb.es/calendario/lf2/9/2025``
        - Aspx:    ``https://baloncestoenvivo.feb.es/calendario.aspx?g=9&t=2025&nm=lf2``

        The corresponding results pages (which list *all* groups including
        playoff phases) follow the same pattern with ``resultados`` in place
        of ``calendario``, and the season year embedded in the URL:
        - Pretty:  ``https://baloncestoenvivo.feb.es/resultados/lf2/9/{season}``
        - Aspx:    ``https://baloncestoenvivo.feb.es/resultados.aspx?g=9&t={season}&nm=lf2``

        Returns the original URL unchanged if no substitution could be made.
        """
        if "/calendario/" in calendar_url:
            base = re.sub(r"/\d{4}$", f"/{season}", calendar_url)
            return base.replace("/calendario/", "/resultados/")
        if "calendario.aspx" in calendar_url:
            url = calendar_url.replace("calendario.aspx", "resultados.aspx")
            url = re.sub(r"([\?&]t=)\d+", rf"\g<1>{season}", url)
            return url
        return calendar_url

    def _get_matches_via_series(
        self, calendar_url: str, group_value: str, season_value: str = ""
    ) -> List[str]:
        """Fetch match codes from a Series.aspx page for a playoff group.

        Some playoff phases (e.g. "2ºA-1ºB Final") render their matches
        exclusively on a ``Series.aspx?f=XXXXX`` page.  The ``/resultados/``
        page for those groups shows the group selected in the dropdown but
        contains no match rows in the jornadaDataGrid.

        Note: Series.aspx pages have no group dropdown.  The group_id → URL
        mapping is built by label matching in ``_build_series_cache`` and
        stored in ``_series_url_by_group`` during ``get_groups_for_season``.

        Strategy:
        1. **Cache hit** — if ``_build_series_cache`` already resolved this
           group's Series URL, GET it directly (fast, no re-fetch).
        2. **Cache miss** — rebuild the cache by re-fetching groups from
           ``/resultados/`` then calling ``_build_series_cache``, and retry.

        Args:
            calendar_url:  Original competition calendar URL.
            group_value:   Group dropdown value to find matches for.
            season_value:  Season value used to derive the /resultados/ URL
                           when rebuilding the cache on a cache miss.

        Returns:
            List of match code strings, or empty list if not found.
        """
        # --- Fast path: cached Series URLs from get_groups_for_season ----------
        series_hrefs = self._series_url_by_group.get(group_value, [])
        if series_hrefs:
            return self._fetch_codes_from_series_urls(series_hrefs)

        # --- Slow path: rebuild cache from /resultados/ + label matching ------
        # Used when _get_matches_via_series is called without a prior
        # get_groups_for_season call (e.g. direct API usage in tests).
        if season_value:
            try:
                results_url = self._calendar_to_results_url(calendar_url, season_value)
                if results_url != calendar_url:
                    res_resp = self.web_client.get(results_url, timeout=EXTENDED_TIMEOUT)
                    if res_resp:
                        groups = self.get_groups(
                            BeautifulSoup(res_resp.content, "html.parser")
                        )
                        if groups:
                            self._build_series_cache(groups, calendar_url)
                            series_hrefs = self._series_url_by_group.get(group_value, [])
                            if series_hrefs:
                                return self._fetch_codes_from_series_urls(series_hrefs)
            except Exception:
                pass
        return []

    def _fetch_codes_from_series_urls(self, series_hrefs: List[str]) -> List[str]:
        """Fetch and merge match codes from multiple Series.aspx URLs.

        Visits every URL in *series_hrefs*, extracts match codes from each page,
        and returns a deduplicated list preserving encounter order.

        Args:
            series_hrefs: One or more Series.aspx URLs for a playoff phase group.

        Returns:
            Deduplicated list of match code strings.
        """
        codes: List[str] = []
        seen: set = set()
        for href in series_hrefs:
            resp = self.web_client.get(href, timeout=EXTENDED_TIMEOUT)
            if not resp:
                continue
            for code in self._extract_match_codes(BeautifulSoup(resp.content, "html.parser")):
                if code not in seen:
                    codes.append(code)
                    seen.add(code)
        return codes

    def _merge_with_series_codes(
        self, codes: List[str], group_value: str, calendar_url: str, soup: BeautifulSoup
    ) -> List[str]:
        """Supplement *codes* with all codes from cached Series.aspx pages for this group.

        For playoff phases /resultados/ only shows the current jornada; the full
        series history lives on Series.aspx.  This helper populates the series URL
        cache from *soup* if it is not yet present for *group_value*, then merges
        any additional codes found on those pages (deduplicated, order preserved).

        Returns *codes* unchanged when no Series.aspx URL is available.
        """
        if not self._series_url_by_group.get(group_value):
            # Cache not yet populated for this group — try to build it from soup.
            visible_groups = self.get_groups(soup)
            if visible_groups:
                self._build_series_cache(visible_groups, calendar_url)
        series_hrefs = self._series_url_by_group.get(group_value, [])
        if not series_hrefs:
            return codes
        series_codes = self._fetch_codes_from_series_urls(series_hrefs)
        seen = set(codes)
        for c in series_codes:
            if c not in seen:
                codes.append(c)
                seen.add(c)
        return codes

    @staticmethod
    def _aspx_to_pretty_calendar_url(aspx_url: str) -> str:
        """Convert ``calendario.aspx?g=G&t=T&nm=NM`` to ``/calendario/NM/G/T``.

        The FEB website exposes two URL formats for the same page.  The
        pretty-URL format (``/calendario/lf2/9/2025``) renders the
        ``fasesDataList`` playoff navigation block while the ASPX query-string
        format (``calendario.aspx?g=9&t=2025&nm=lf2``) does not.

        Returns the original URL unchanged if it is not in ASPX format or if
        the required query parameters are missing.
        """
        if "calendario.aspx" not in aspx_url:
            return aspx_url
        from urllib.parse import urlparse, parse_qs
        parsed = urlparse(aspx_url)
        qs = parse_qs(parsed.query)
        g = qs.get("g", [""])[0]
        t = qs.get("t", [""])[0]
        nm = qs.get("nm", [""])[0]
        if g and t and nm:
            base = f"{parsed.scheme}://{parsed.netloc}"
            return f"{base}/calendario/{nm}/{g}/{t}"
        return aspx_url

    def select_season(self, session: requests.Session, url: str, season_value: str,
                     hidden_fields: Dict[str, str]) -> Tuple[BeautifulSoup, Dict[str, str]]:
        """
        Perform a POST to select the season.

        Args:
            session: Requests session
            url: Target URL
            season_value: Season value to select
            hidden_fields: ASP.NET hidden form fields

        Returns:
            Tuple of (BeautifulSoup object, updated hidden_fields)

        Raises:
            Exception if POST fails
        """
        form_data = self._build_form_data(
            event_target=get_event_target(SEASON_DROPDOWN_ID),
            hidden_fields=hidden_fields,
            additional_fields={get_form_field_name(SEASON_DROPDOWN_ID): season_value}
        )

        response = self.web_client.post(url, data=form_data, timeout=EXTENDED_TIMEOUT)
        if not response:
            raise Exception("Failed to select season")

        soup = BeautifulSoup(response.content, "html.parser")
        updated_hidden_fields = self.get_hidden_fields(soup)

        return soup, updated_hidden_fields

    def select_group(self, session: requests.Session, url: str, season_value: str,
                    group_value: str, hidden_fields: Dict[str, str]) -> BeautifulSoup:
        """
        Perform a POST to select the group.

        Args:
            session: Requests session
            url: Target URL
            season_value: Season value
            group_value: Group value to select
            hidden_fields: ASP.NET hidden form fields

        Returns:
            BeautifulSoup object of the response

        Raises:
            Exception if POST fails
        """
        form_data = self._build_form_data(
            event_target=get_event_target(GROUP_DROPDOWN_ID),
            hidden_fields=hidden_fields,
            additional_fields={
                get_form_field_name(SEASON_DROPDOWN_ID): season_value,
                get_form_field_name(GROUP_DROPDOWN_ID): group_value
            }
        )

        response = self.web_client.post(url, data=form_data, timeout=EXTENDED_TIMEOUT)
        if not response:
            raise Exception("Failed to select group")

        return BeautifulSoup(response.content, "html.parser")

    def get_hidden_fields(self, soup: BeautifulSoup) -> Dict[str, str]:
        """
        Extract ASP.NET hidden fields from the page.

        Args:
            soup: BeautifulSoup object of the page

        Returns:
            Dictionary of hidden field names and values
        """
        fields = {}
        for field_name in HIDDEN_FIELDS:
            tag = soup.find("input", {"id": field_name})
            if tag and tag.has_attr("value"):
                fields[field_name] = tag["value"]
        return fields

    def get_matches(self, season_value: str, group_value: str, year: str,
                   session: requests.Session, url: Optional[str] = None) -> List[str]:
        """
        Fetch match codes for the given season and group.

        Args:
            season_value: Season value
            group_value: Group value
            year: Season year
            session: Requests session
            url: Optional URL for the competition (if not provided, uses BASE_URL)

        Returns:
            List of match codes
        """
        # Use provided URL or fall back to hardcoded BASE_URL
        if url is None:
            norm_year = normalize_year(year)
            url = BASE_URL.format(year=norm_year)

        # Remember original calendar URL for fasesDataList fallback
        original_calendar_url = url

        # Get initial page
        response = self.web_client.get(url, timeout=EXTENDED_TIMEOUT)
        if not response:
            return []

        soup = BeautifulSoup(response.content, "html.parser")

        # Check if the initial page already has the correct season and group selected
        season_dropdown = soup.find("select", {"id": SEASON_DROPDOWN_ID})
        group_dropdown = soup.find("select", {"id": GROUP_DROPDOWN_ID})

        current_season = None
        current_group = None

        if season_dropdown:
            selected_option = season_dropdown.find("option", selected=True)
            if selected_option:
                current_season = selected_option.get("value")

        if group_dropdown:
            selected_option = group_dropdown.find("option", selected=True)
            if selected_option:
                current_group = selected_option.get("value")

        # If the page already has the correct selection, use it directly
        if current_season == season_value and current_group == group_value:
            matches = self._extract_match_codes(soup)
            if matches:  # If we found matches, we're done
                return matches

        # Otherwise, need to select season and group via POST
        hidden_fields = self.get_hidden_fields(soup)

        # Select season (only if different from current)
        if current_season != season_value:
            # Before falling back to ASP.NET POST, try navigating directly to
            # the year-substituted URL.  get_feb_competitions() returns URLs with
            # the CURRENT season year embedded (e.g. /lfchallenge/67/2026 for
            # the 2026/27 page).  The completed past season lives at /2025.
            # A direct GET is simpler and avoids ASP.NET postback failures.
            seasonal_url = self._derive_seasonal_url(url, season_value)
            if seasonal_url != url:
                resp = self.web_client.get(seasonal_url, timeout=EXTENDED_TIMEOUT)
                if resp:
                    soup = BeautifulSoup(resp.content, "html.parser")
                    url = seasonal_url
                    original_calendar_url = seasonal_url  # keep Series.aspx cache on correct year
                    hidden_fields = self.get_hidden_fields(soup)
                    s_dd = soup.find("select", {"id": SEASON_DROPDOWN_ID})
                    s_sel = s_dd and s_dd.find("option", selected=True)
                    current_season = s_sel.get("value") if s_sel else season_value
                    g_dd = soup.find("select", {"id": GROUP_DROPDOWN_ID})
                    g_sel = g_dd and g_dd.find("option", selected=True)
                    current_group = g_sel.get("value") if g_sel else current_group
                    # Early exit only when BOTH season and group already match —
                    # otherwise the page shows the default group (usually A).
                    if current_season == season_value and current_group == group_value:
                        early_matches = self._extract_match_codes(soup)
                        if early_matches:
                            return early_matches
            if current_season != season_value:
                soup, hidden_fields = self.select_season(session, url, season_value, hidden_fields)

        # Select group (only if different from current)
        if current_group != group_value:
            # Verify the group exists in the current page's dropdown.
            # Playoff groups (discovered via /resultados/) are absent from the
            # /calendario/ dropdown — POSTing an unknown group value causes the
            # server to return a non-200 response → raise_for_status() → None →
            # Exception("Failed to select group").
            grp_dd = soup.find("select", {"id": GROUP_DROPDOWN_ID})
            in_dropdown = grp_dd and grp_dd.find("option", {"value": group_value})
            if not in_dropdown:
                # Switch to the /resultados/ equivalent URL which lists all groups
                results_url = self._calendar_to_results_url(url, season_value)
                if results_url != url:
                    resp = self.web_client.get(results_url, timeout=EXTENDED_TIMEOUT)
                    if resp:
                        soup = BeautifulSoup(resp.content, "html.parser")
                        hidden_fields = self.get_hidden_fields(soup)
                        # Re-select season on the new page if needed
                        s_dd = soup.find("select", {"id": SEASON_DROPDOWN_ID})
                        s_sel = s_dd and s_dd.find("option", selected=True)
                        if s_sel and s_sel.get("value") != season_value:
                            soup, hidden_fields = self.select_season(
                                session, results_url, season_value, hidden_fields
                            )
                        url = results_url
            soup = self.select_group(session, url, season_value, group_value, hidden_fields)

        # Extract match codes from the POST result page.
        # Note: for playoff phases /resultados/ shows only the current jornada;
        # Series.aspx carries the full series history.  Always merge both sources.
        codes = self._extract_match_codes(soup)
        merged = self._merge_with_series_codes(
            codes, group_value, original_calendar_url, soup
        )
        if merged:
            return merged

        # Final fallback: slow-path cache rebuild for groups where Series.aspx
        # is the only source (e.g. a phase with no match rows on /resultados/).
        return self._get_matches_via_series(original_calendar_url, group_value, season_value)

    @staticmethod
    def _derive_seasonal_url(url: str, season_value: str) -> str:
        """Return a URL with the year component replaced by *season_value*.

        Handles both pretty-URL format (/calendario/slug/group/YEAR) and ASPX
        query-string format (?…&t=YEAR&…).  Returns *url* unchanged when neither
        pattern is found or when the year is already correct.
        """
        if "/calendario/" in url:
            return re.sub(r"/(\d{4})$", f"/{season_value}", url)
        if "calendario.aspx" in url:
            return re.sub(r"([?&]t=)\d+", rf"\g<1>{season_value}", url)
        return url

    def _build_form_data(self, event_target: str, hidden_fields: Dict[str, str],
                        additional_fields: Dict[str, str]) -> Dict[str, str]:
        """Build ASP.NET form data for POST request."""
        form_data = {
            "__EVENTTARGET": event_target,
            "__EVENTARGUMENT": "",
            "__LASTFOCUS": ""
        }
        form_data.update(hidden_fields)
        form_data.update(additional_fields)
        return form_data

    def _extract_match_codes(self, soup: BeautifulSoup) -> List[str]:
        """
        Extract match codes from the calendar or results page.

        Supports two page structures:
        - ``/calendario/`` — match links inside ``div.tableLayout de dos columnas``
          tables, score cell has class ``resultado``.
        - ``/resultados/`` — match links inside ``table#jornadaDataGrid`` (or
          similar), no special container class; scores appear as ``"72-65"``
          directly in the ``<a>`` text.

        Only links whose text matches a completed-score pattern
        (``digits - digits``) are returned; future matches (``*-*``) are skipped.

        Args:
            soup: BeautifulSoup object of the calendar or results page

        Returns:
            List of match code strings (the ``p=`` URL parameter value)
        """
        matches: List[str] = []
        seen: set = set()

        # --- Primary: /calendario/ structure ---
        for container in soup.find_all("div", class_="tableLayout de dos columnas"):
            for table in container.find_all("table"):
                for row in table.find_all("tr")[1:]:
                    code = self._extract_match_code_from_row(row)
                    if code and code not in seen:
                        matches.append(code)
                        seen.add(code)
        if matches:
            return matches

        # --- Fallback: /resultados/ structure ---
        # Links are present anywhere on the page; filter by completed-score text.
        for link in soup.find_all("a", href=re.compile(r"[Pp]=\d+")):
            text = link.get_text(strip=True)
            if re.match(r"^\d+\s*-\s*\d+$", text):
                m = re.search(r"[Pp]=(\d+)", link["href"])
                if m and m.group(1) not in seen:
                    matches.append(m.group(1))
                    seen.add(m.group(1))
        return matches

    def _extract_match_code_from_row(self, row) -> Optional[str]:
        """
        Extract match code from a table row.

        Args:
            row: BeautifulSoup table row element

        Returns:
            Match code or None if not found
        """
        # Find result cell
        res_cell = row.find("td", class_="resultado")
        if not res_cell:
            return None

        # Find link with match parameter
        link = res_cell.find("a", href=re.compile(r"p=\d+"))
        if not link:
            return None

        # Verify it's a valid score format (e.g., "75 - 68")
        link_text = link.get_text(strip=True)
        if not re.match(r"^\d+\s*-\s*\d+$", link_text):
            return None

        # Extract match code from URL parameter
        match = re.search(r"p=(\d+)", link["href"])
        if match:
            return match.group(1)

        return None

    def get_feb_competitions(self) -> List[Dict[str, str]]:
        """
        Scrape FEB competitions page to get available competitions.

        Returns:
            List of dicts with 'name' and 'calendar_url' keys
        """
        url = "https://competiciones.feb.es/estadisticas/"
        response = self.web_client.get(url, timeout=EXTENDED_TIMEOUT)
        if not response:
            return []

        soup = BeautifulSoup(response.content, "html.parser")
        competitions = []
        seen_names = set()  # To avoid duplicates

        # Find all menu-item divs
        for menu_item in soup.find_all("div", class_="menu-item"):
            # Get competition name from menu-item-liga span
            name_span = menu_item.find("span", class_="menu-item-liga")
            if not name_span:
                continue

            comp_name = name_span.get_text(strip=True)
            if not comp_name or comp_name in seen_names:
                continue

            # Find the "Calendario" link in menu-item-links
            links_div = menu_item.find("div", class_="menu-item-links")
            if links_div:
                calendar_link = links_div.find("a", string="Calendario")
                if calendar_link and calendar_link.get("href"):
                    competitions.append({
                        "name": comp_name,
                        "results_url": calendar_link["href"]  # Keep same key name for backwards compatibility
                    })
                    seen_names.add(comp_name)

        return competitions
