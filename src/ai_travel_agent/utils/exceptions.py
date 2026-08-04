"""Custom exceptions for the travel agent tools."""


class TravelAgentError(Exception):
    """Base exception for all travel agent errors."""


class APITimeoutError(TravelAgentError):
    """API call took too long."""


class APIRateLimitError(TravelAgentError):
    """Hit API rate limit."""

    def __init__(self, retry_after: int = 60) -> None:
        self.retry_after = retry_after
        super().__init__(f"Rate limited. Retry after {retry_after}s")


class NoResultsError(TravelAgentError):
    """API returned successfully but found nothing."""

    def __init__(self, query: str) -> None:
        super().__init__(f"No results found for: {query}")


class APIAuthError(TravelAgentError):
    """Authentication failed — bad API key."""


class InvalidInputError(TravelAgentError):
    """Input validation failed before hitting API."""
