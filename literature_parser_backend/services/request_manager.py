"""
External Request Manager for unified HTTP request handling.

This module provides a centralized manager for handling all external HTTP requests
with proper proxy configuration, retry logic, and distinction between internal
and external communications.
"""

import logging
import time
from enum import Enum
from typing import Any, Optional

import requests
from requests.adapters import HTTPAdapter
from requests.exceptions import RequestException, Timeout
from urllib3.util.retry import Retry

from ..settings import Settings

logger = logging.getLogger(__name__)


class RequestType(str, Enum):
    """Request type enumeration to distinguish internal vs external requests."""

    INTERNAL = "internal"  # Container internal communication (GROBID, Redis, MongoDB)
    EXTERNAL = "external"  # External network requests (CrossRef, Semantic Scholar, PDF downloads)


class ExternalRequestManager:
    """
    Unified manager for all HTTP requests with proper proxy configuration.

    Features:
    - Separate sessions for internal and external requests
    - Automatic proxy configuration for external requests
    - Unified retry, timeout, and error handling
    - Request monitoring and logging
    """

    def __init__(self, settings: Optional[Settings] = None):
        """
        Initialize the request manager.

        Args:
            settings: Application settings (optional, will create default if not provided)
        """
        self.settings = settings or Settings()
        self.internal_session = requests.Session()
        self.external_session = requests.Session()
        self._configure_sessions()

        logger.info("ExternalRequestManager initialized")

    def _configure_sessions(self):
        """Configure internal and external sessions with appropriate settings."""
        # Configure retry strategy
        retry_strategy = Retry(
            total=self.settings.external_api_max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["HEAD", "GET", "OPTIONS", "POST"],
        )

        # Create HTTP adapter with retry strategy
        adapter = HTTPAdapter(max_retries=retry_strategy)

        # Configure internal session (no proxy)
        self.internal_session.proxies = {"http": "", "https": ""}
        self.internal_session.mount("http://", adapter)
        self.internal_session.mount("https://", adapter)

        # Configure external session (with proxy if configured)
        # TEMPORARY: Disable proxy for debugging since direct connection works
        proxy_disabled = True  # Set to False to re-enable proxy

        if not proxy_disabled and (
            self.settings.http_proxy or self.settings.https_proxy
        ):
            proxy_dict = {
                "http": self.settings.http_proxy,
                "https": self.settings.https_proxy,
            }
            self.external_session.proxies = proxy_dict
            logger.info(f"External session configured with proxy: {proxy_dict}")
        else:
            self.external_session.proxies = {"http": "", "https": ""}
            if proxy_disabled:
                logger.info(
                    "External session configured without proxy (proxy temporarily disabled)",
                )
            else:
                logger.info("External session configured without proxy")

        self.external_session.mount("http://", adapter)
        self.external_session.mount("https://", adapter)

        # Set common headers
        common_headers = {
            "User-Agent": "Literature Parser Backend/1.0",
            "Accept": "application/json",
        }
        self.internal_session.headers.update(common_headers)
        self.external_session.headers.update(common_headers)

    def get_session(self, request_type: RequestType) -> requests.Session:
        """
        Get the appropriate session for the request type.

        Args:
            request_type: Type of request (internal or external)

        Returns:
            Configured requests session
        """
        return (
            self.external_session
            if request_type == RequestType.EXTERNAL
            else self.internal_session
        )

    def request(
        self,
        method: str,
        url: str,
        request_type: RequestType,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """
        Make an HTTP request with proper session and error handling.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            request_type: Type of request (internal or external)
            timeout: Request timeout in seconds
            **kwargs: Additional arguments passed to requests

        Returns:
            Response object

        Raises:
            RequestException: If request fails after retries
        """
        session = self.get_session(request_type)
        request_timeout = timeout or self.settings.external_api_timeout

        start_time = time.time()

        try:
            logger.debug(f"Making {request_type.value} {method} request to {url}")
            response = session.request(
                method=method,
                url=url,
                timeout=request_timeout,
                **kwargs,
            )

            elapsed_time = time.time() - start_time
            logger.debug(
                f"{request_type.value} {method} {url} -> "
                f"{response.status_code} ({elapsed_time:.2f}s)",
            )

            response.raise_for_status()
            return response

        except Timeout as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"{request_type.value} {method} {url} -> "
                f"TIMEOUT after {elapsed_time:.2f}s",
            )
            raise RequestException(f"Request timeout after {elapsed_time:.2f}s") from e

        except RequestException as e:
            elapsed_time = time.time() - start_time
            logger.error(
                f"{request_type.value} {method} {url} -> "
                f"ERROR after {elapsed_time:.2f}s: {e}",
            )
            raise

    def get(
        self,
        url: str,
        request_type: RequestType,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Convenience method for GET requests."""
        return self.request("GET", url, request_type, timeout, **kwargs)

    def post(
        self,
        url: str,
        request_type: RequestType,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Convenience method for POST requests."""
        return self.request("POST", url, request_type, timeout, **kwargs)

    def put(
        self,
        url: str,
        request_type: RequestType,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Convenience method for PUT requests."""
        return self.request("PUT", url, request_type, timeout, **kwargs)

    def delete(
        self,
        url: str,
        request_type: RequestType,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> requests.Response:
        """Convenience method for DELETE requests."""
        return self.request("DELETE", url, request_type, timeout, **kwargs)

    def download_file(
        self,
        url: str,
        request_type: RequestType = RequestType.EXTERNAL,
        timeout: Optional[int] = None,
        **kwargs: Any,
    ) -> bytes:
        """
        Download a file and return its content as bytes.

        Args:
            url: URL to download
            request_type: Type of request (usually external for file downloads)
            timeout: Request timeout in seconds
            **kwargs: Additional arguments passed to requests

        Returns:
            File content as bytes

        Raises:
            RequestException: If download fails
        """
        response = self.get(url, request_type, timeout, **kwargs)

        # Check if response contains binary content
        content_type = response.headers.get("content-type", "").lower()
        if (
            "application/pdf" in content_type
            or "application/octet-stream" in content_type
        ):
            logger.info(f"Downloaded {len(response.content)} bytes from {url}")
            return response.content
        else:
            logger.warning(f"Unexpected content type '{content_type}' for URL: {url}")
            return response.content

    def close(self):
        """Close all sessions to free resources."""
        self.internal_session.close()
        self.external_session.close()
        logger.info("ExternalRequestManager sessions closed")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()


# Global instance for convenience
_request_manager: Optional[ExternalRequestManager] = None


def get_request_manager(settings: Optional[Settings] = None) -> ExternalRequestManager:
    """
    Get the global request manager instance.

    Args:
        settings: Application settings (optional)

    Returns:
        Global ExternalRequestManager instance
    """
    global _request_manager
    if _request_manager is None:
        _request_manager = ExternalRequestManager(settings)
    return _request_manager


def cleanup_request_manager():
    """Clean up the global request manager instance."""
    global _request_manager
    if _request_manager is not None:
        _request_manager.close()
        _request_manager = None
