"""Tests for error handling system."""

import pytest

from reflex.core.errors import (
    AgentError,
    ErrorCode,
    EventNotFoundError,
    LockError,
    PublicationError,
    RateLimitError,
    ReflexError,
    StoreError,
    ValidationError,
)


class TestErrorCode:
    """Tests for ErrorCode enum."""

    def test_all_codes_are_strings(self) -> None:
        """Test that all error codes are string enums."""
        for code in ErrorCode:
            assert isinstance(code.value, str)

    def test_code_values_match_names(self) -> None:
        """Test that code values match their names."""
        for code in ErrorCode:
            assert code.value == code.name


class TestReflexError:
    """Tests for ReflexError base class."""

    def test_creation_with_message(self) -> None:
        """Test creating error with just a message."""
        error = ReflexError("Something went wrong")
        assert error.message == "Something went wrong"
        assert str(error) == "Something went wrong"
        assert error.details == {}

    def test_creation_with_details(self) -> None:
        """Test creating error with message and details."""
        error = ReflexError("Failed", details={"field": "value", "code": 123})
        assert error.message == "Failed"
        assert error.details == {"field": "value", "code": 123}

    def test_default_code_and_status(self) -> None:
        """Test default error code and status code."""
        error = ReflexError("Error")
        assert error.code == ErrorCode.INTERNAL_ERROR
        assert error.status_code == 500

    def test_to_response(self) -> None:
        """Test converting error to response dict."""
        error = ReflexError("Something broke", details={"id": "123"})
        response = error.to_response()

        assert response == {
            "error": {
                "code": "INTERNAL_ERROR",
                "message": "Something broke",
                "details": {"id": "123"},
            }
        }

    def test_to_response_empty_details(self) -> None:
        """Test response with no details."""
        error = ReflexError("Error")
        response = error.to_response()

        assert response["error"]["details"] == {}


class TestValidationError:
    """Tests for ValidationError."""

    def test_code_and_status(self) -> None:
        """Test ValidationError code and status."""
        error = ValidationError("Invalid input")
        assert error.code == ErrorCode.VALIDATION_ERROR
        assert error.status_code == 422

    def test_inheritance(self) -> None:
        """Test that ValidationError inherits from ReflexError."""
        error = ValidationError("Invalid")
        assert isinstance(error, ReflexError)


class TestEventNotFoundError:
    """Tests for EventNotFoundError."""

    def test_code_and_status(self) -> None:
        """Test EventNotFoundError code and status."""
        error = EventNotFoundError("Event not found")
        assert error.code == ErrorCode.EVENT_NOT_FOUND
        assert error.status_code == 404

    def test_with_event_id(self) -> None:
        """Test EventNotFoundError with event ID in details."""
        error = EventNotFoundError(
            "Event abc123 not found",
            details={"event_id": "abc123"},
        )
        response = error.to_response()
        assert response["error"]["details"]["event_id"] == "abc123"


class TestPublicationError:
    """Tests for PublicationError."""

    def test_code_and_status(self) -> None:
        """Test PublicationError code and status."""
        error = PublicationError("Failed to publish")
        assert error.code == ErrorCode.PUBLICATION_FAILED
        assert error.status_code == 500


class TestRateLimitError:
    """Tests for RateLimitError."""

    def test_code_and_status(self) -> None:
        """Test RateLimitError code and status."""
        error = RateLimitError("Rate limit exceeded")
        assert error.code == ErrorCode.RATE_LIMITED
        assert error.status_code == 429


class TestStoreError:
    """Tests for StoreError."""

    def test_code_and_status(self) -> None:
        """Test StoreError code and status."""
        error = StoreError("Database error")
        assert error.code == ErrorCode.STORE_ERROR
        assert error.status_code == 500


class TestAgentError:
    """Tests for AgentError."""

    def test_code_and_status(self) -> None:
        """Test AgentError code and status."""
        error = AgentError("Agent failed")
        assert error.code == ErrorCode.AGENT_ERROR
        assert error.status_code == 500


class TestLockError:
    """Tests for LockError."""

    def test_code_and_status(self) -> None:
        """Test LockError code and status."""
        error = LockError("Could not acquire lock")
        assert error.code == ErrorCode.LOCK_ERROR
        assert error.status_code == 503


class TestErrorHandling:
    """Tests for error handling in practice."""

    def test_raise_and_catch_specific(self) -> None:
        """Test raising and catching specific error types."""
        with pytest.raises(EventNotFoundError) as exc_info:
            raise EventNotFoundError("Not found", details={"id": "123"})

        assert exc_info.value.code == ErrorCode.EVENT_NOT_FOUND
        assert exc_info.value.details["id"] == "123"

    def test_catch_base_class(self) -> None:
        """Test catching errors via base class."""
        errors = [
            ValidationError("Invalid"),
            EventNotFoundError("Not found"),
            PublicationError("Failed"),
            StoreError("DB error"),
        ]

        for error in errors:
            with pytest.raises(ReflexError):
                raise error

    def test_all_errors_have_unique_codes(self) -> None:
        """Test that different error types have different codes."""
        error_types = [
            ValidationError,
            EventNotFoundError,
            PublicationError,
            RateLimitError,
            StoreError,
            AgentError,
            LockError,
        ]

        codes = [cls("test").code for cls in error_types]
        # Check that codes are unique (except for errors that share a code)
        # ValidationError, PublicationError, StoreError, AgentError all use different codes
        assert len(set(codes)) == len(error_types)
