"""Base HTTP client with retry logic."""

import requests
from typing import Optional, Dict, Callable
from .constants import DEFAULT_TIMEOUT, DEFAULT_HEADERS


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
            response = self.session.get(url, headers=request_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[WebClient] GET request failed for {url}: {e}")
            return None

    def post(self, url: str, data: Dict, headers: Optional[Dict[str, str]] = None,
             timeout: int = DEFAULT_TIMEOUT) -> Optional[requests.Response]:
        """
        Perform POST request with error handling.

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
            response = self.session.post(url, data=data, headers=request_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.RequestException as e:
            print(f"[WebClient] POST request failed for {url}: {e}")
            return None

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
            response = self.session.get(url, headers=request_headers, timeout=timeout)
            response.raise_for_status()
            return response
        except requests.HTTPError as e:
            if e.response.status_code == 401 and on_401:
                print(f"[WebClient] Unauthorized (401), attempting to refresh token")
                new_token = on_401()
                if new_token:
                    request_headers["Authorization"] = f"Bearer {new_token}"
                    try:
                        response = self.session.get(url, headers=request_headers, timeout=timeout)
                        response.raise_for_status()
                        return response
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
