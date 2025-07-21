#!/usr/bin/env python3
"""
Check settings and proxy configuration
"""
import sys
import os

sys.path.append("/mnt/g/programs/Page/Paper_Paser_1")

from literature_parser_backend.settings import Settings


def check_settings():
    """Check current settings configuration."""
    print("=" * 60)
    print("Checking current settings configuration")
    print("=" * 60)

    settings = Settings()

    print("Current settings:")
    print(f"  HTTP Proxy: {settings.http_proxy}")
    print(f"  HTTPS Proxy: {settings.https_proxy}")
    print(f"  External API timeout: {settings.external_api_timeout}")
    print(f"  External API max retries: {settings.external_api_max_retries}")

    print("\nProxy dictionary:")
    proxy_dict = settings.get_proxy_dict()
    print(f"  {proxy_dict}")

    print("\nEnvironment variables:")
    for key in [
        "LITERATURE_PARSER_BACKEND_HTTP_PROXY",
        "LITERATURE_PARSER_BACKEND_HTTPS_PROXY",
    ]:
        value = os.getenv(key)
        print(f"  {key}: {value}")


if __name__ == "__main__":
    check_settings()
