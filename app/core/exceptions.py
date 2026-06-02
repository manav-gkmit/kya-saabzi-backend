from __future__ import annotations

from uuid import UUID


class AppError(Exception):
    """Root exception. Catch this at the top level."""


class AuthError(AppError):
    """Authentication or authorization failure."""


class InvalidCredentialsError(AuthError):
    """Raised when email or password (or API key) is invalid."""

    def __init__(self) -> None:
        super().__init__("Invalid credentials")


class TokenExpiredError(AuthError):
    """Raised when an access or refresh token has expired."""

    def __init__(self) -> None:
        super().__init__("Token has expired")


class TokenInvalidError(AuthError):
    """Raised when a token is invalid, malformed, or missing."""

    def __init__(self, detail: str = "Invalid token") -> None:
        super().__init__(detail)


class TokenReuseError(AuthError):
    """Raised when a revoked refresh token is presented (possible theft)."""

    def __init__(self, user_id: UUID) -> None:
        self.user_id = user_id
        super().__init__("Token reuse detected. All sessions revoked.")


class ForbiddenError(AppError):
    """Access denied."""


class HouseholdAccessDeniedError(ForbiddenError):
    """Raised when a user attempts to access a household they do not belong to."""

    def __init__(self, detail: str = "Member not found in your household") -> None:
        super().__init__(detail)


class NotFoundError(AppError):
    """Resource not found."""


class DishNotFoundError(NotFoundError):
    """Raised when a dish cannot be found."""

    def __init__(self, detail: str = "Dish not found") -> None:
        super().__init__(detail)


class HouseholdNotFoundError(NotFoundError):
    """Raised when a household cannot be found."""

    def __init__(self, detail: str = "Household not found") -> None:
        super().__init__(detail)


class CookLogNotFoundError(NotFoundError):
    """Raised when a cook log cannot be found."""

    def __init__(self, detail: str = "Cook log not found") -> None:
        super().__init__(detail)


class UserNotFoundError(NotFoundError):
    """Raised when a user cannot be found."""

    def __init__(self, detail: str = "User not found") -> None:
        super().__init__(detail)


class ConflictError(AppError):
    """Conflict state, e.g., already exists."""


class DishAlreadyExistsError(ConflictError):
    """Raised when trying to create a dish that already exists."""

    def __init__(self, detail: str = "Dish already exists") -> None:
        super().__init__(detail)


class UserAlreadyExistsError(ConflictError):
    """Raised when trying to register a user that already exists."""

    def __init__(self, detail: str = "Username or email already registered") -> None:
        super().__init__(detail)


class ValidationError(AppError):
    """Business rule validation failed."""


class InvalidDishNameError(ValidationError):
    """Raised when a dish name fails validation after normalization."""

    def __init__(self, detail: str = "Dish name cannot be empty after normalization") -> None:
        super().__init__(detail)
