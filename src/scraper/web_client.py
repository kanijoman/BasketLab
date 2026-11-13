"""Base HTTP client with retry logic."""

import requests
from typing import Optional, Dict, Callable
import re
from urllib.parse import parse_qs, urlsplit

from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from .constants import DEFAULT_TIMEOUT, DEFAULT_HEADERS

# FEB links its own pages as http:// and the server answers 301 to https:// (26 of the 87 requests of a collection were that hop, #924): for the hosts known to do it the request goes
# straight to https. Any other host (a local fake server, for one) is left as it is.
HTTPS_HOSTS = frozenset({"baloncestoenvivo.feb.es", "www.fbcyl.es"})


def _feb_canonical(url: str) -> Optional[str]:
    """The address FEB redirects calendario.aspx?g=G&t=T&nm=NM, resultados.aspx?... and Series.aspx?f=ID to (301 to http://, then another 301 to https://: three requests for one
    page); None for anything that is not exactly one of those."""
    parts = urlsplit(url)
    if (parts.hostname or "").lower() != "baloncestoenvivo.feb.es":
        return None
    page, query = parts.path.lstrip("/").lower(), parse_qs(parts.query, keep_blank_values=True)
    if page in ("calendario.aspx", "resultados.aspx") and set(query) == {"g", "t", "nm"} and all(len(v) == 1 for v in query.values()):
        group, season, name = query["g"][0], query["t"][0], query["nm"][0]
        if group.isdigit() and season.isdigit() and re.fullmatch(r"[A-Za-z0-9_-]+", name):
            return f"https://baloncestoenvivo.feb.es/{page[:-5]}/{name}/{group}/{season}"
    if page == "series.aspx" and set(query) == {"f"} and len(query["f"]) == 1 and query["f"][0].isdigit():
        return f"https://baloncestoenvivo.feb.es/series/{query['f'][0]}"
    return None


def secure_scheme(url: str) -> str:
    """url over https when its host is one of HTTPS_HOSTS and it says http (the only change a POST gets: it goes where its form posts)."""
    parts = urlsplit(url)
    if parts.scheme.lower() == "http" and (parts.hostname or "").lower() in HTTPS_HOSTS:
        return "https://" + url.split("://", 1)[1]
    return url


def secure_url(url: str) -> str:
    """The address to ask for url (GET): the canonical one FEB would redirect to, or https when the host is one of HTTPS_HOSTS and it says http; otherwise as it is."""
    return _feb_canonical(url) or secure_scheme(url)


# Retry decorator for transient network failures: 3 attempts with 1s/2s/4s back-off
_retry_on_connection_error = retry(
    retry=retry_if_exception_type((requests.ConnectionError, requests.Timeout)),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=4),
    reraise=False,
)


class WebClient:
    """Base HTTP client with error handling and retry logic."""

    def __init__(self, headers: Optional[Dict[str, str]] = None):
        """
        Initialize web client.

        Args:
            headers: Default headers for requests
        """
        self.headers = headers or DEFAULT_HEADERS.copy()
        self.session = requests.Session()

    def get(self, url: str, headers: Optional[Dict[str, str]] = None,
            timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
        """
        Perform GET request with error handling.

        Retries up to 3 times on ``ConnectionError`` / ``Timeout`` (1-4 s back-off).

        Args:
            url: URL to fetch
            headers: Optional headers to override defaults
            timeout: Request timeout in seconds

        Returns:
            Response object or None if failed
        """
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            return self._execute_get(url, request_headers, timeout)
        except requests.RequestException as e:
            print(f"[WebClient] GET request failed for {url}: {e}")
            return None

    def post(self, url: str, data: Dict, headers: Optional[Dict[str, str]] = None,
             timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
        """
        Perform POST request with error handling.

        Retries up to 3 times on ``ConnectionError`` / ``Timeout`` (1-4 s back-off).

        Args:
            url: URL to post to
            data: Form data
            headers: Optional headers to override defaults
            timeout: Request timeout in seconds

        Returns:
            Response object or None if failed
        """
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            return self._execute_post(url, data, request_headers, timeout)
        except requests.RequestException as e:
            print(f"[WebClient] POST request failed for {url}: {e}")
            return None

    @_retry_on_connection_error
    def _execute_get(self, url: str, headers: Dict, timeout: int) -> requests.Response:
        """Execute a GET request; retried on ConnectionError/Timeout."""
        response = self.session.get(secure_url(url), headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    @_retry_on_connection_error
    def _execute_post(self, url: str, data: Dict, headers: Dict, timeout: int) -> requests.Response:
        """Execute a POST request; retried on ConnectionError/Timeout."""
        response = self.session.post(secure_scheme(url), data=data, headers=headers, timeout=timeout)
        response.raise_for_status()
        return response

    def get_with_retry(self, url: str, headers: Optional[Dict[str, str]] = None,
                       on_401: Optional[Callable[[], Optional[str]]] = None,
                       timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
        """
        Perform GET request with retry on 401 unauthorized.

        Args:
            url: URL to fetch
            headers: Optional headers
            on_401: Callback to refresh token on 401 error
            timeout: Request timeout in seconds

        Returns:
            Response object or None if failed
        """
        request_headers = self.headers.copy()
        if headers:
            request_headers.update(headers)

        try:
            return self._execute_get(url, request_headers, timeout)
        except requests.HTTPError as e:
            if e.response.status_code == 401 and on_401:
                print(f"[WebClient] Unauthorized (401), attempting to refresh token")
                new_token = on_401()
                if new_token:
                    request_headers["Authorization"] = f"Bearer {new_token}"
                    try:
                        return self._execute_get(url, request_headers, timeout)
                    except requests.RequestException as retry_e:
                        print(f"[WebClient] Retry failed: {retry_e}")
                        return None
            print(f"[WebClient] HTTP error: {e}")
            return None
        except requests.RequestException as e:
            print(f"[WebClient] Request failed: {e}")
            return None

    def get_session(self) -> requests.Session:
        """Get the underlying session object."""
        return self.session
