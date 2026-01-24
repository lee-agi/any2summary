"""Tests for _is_stream_transport_error detecting openai.APIConnectionError."""

import pytest
from unittest.mock import MagicMock


def test_is_stream_transport_error_detects_api_connection_error():
    """Verify _is_stream_transport_error returns True for openai.APIConnectionError."""
    from any2summary.cli import _is_stream_transport_error
    import openai

    # Create a real APIConnectionError
    mock_request = MagicMock()
    exc = openai.APIConnectionError(request=mock_request)

    assert _is_stream_transport_error(exc) is True


def test_is_stream_transport_error_detects_remote_protocol_error():
    """Verify _is_stream_transport_error returns True for httpx.RemoteProtocolError."""
    from any2summary.cli import _is_stream_transport_error
    import httpx

    exc = httpx.RemoteProtocolError("Server disconnected without sending a response.")

    assert _is_stream_transport_error(exc) is True


def test_is_stream_transport_error_detects_timeout_exception():
    """Verify _is_stream_transport_error returns True for httpx.TimeoutException."""
    from any2summary.cli import _is_stream_transport_error
    import httpx

    exc = httpx.TimeoutException("Connection timed out")

    assert _is_stream_transport_error(exc) is True


def test_is_stream_transport_error_returns_false_for_other_errors():
    """Verify _is_stream_transport_error returns False for unrelated errors."""
    from any2summary.cli import _is_stream_transport_error

    exc = ValueError("some other error")

    assert _is_stream_transport_error(exc) is False


def test_create_azure_http_client_returns_valid_client():
    """Verify _create_azure_http_client creates a valid httpx client."""
    from any2summary.cli import _create_azure_http_client
    import httpx

    client = _create_azure_http_client()

    assert client is not None
    assert isinstance(client, httpx.Client)


def test_create_azure_http_client_has_extended_timeout():
    """Verify _create_azure_http_client sets extended timeouts for large audio."""
    from any2summary.cli import _create_azure_http_client

    client = _create_azure_http_client()

    assert client is not None
    # Check timeout configuration: 600s total, 30s connect
    assert client.timeout.read == 600.0
    assert client.timeout.connect == 30.0
