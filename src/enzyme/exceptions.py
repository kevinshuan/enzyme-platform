"""Enzyme feature-specific exceptions."""


class EnzymeValidationError(ValueError):
    """Raised for invalid enzyme sequences or configuration."""


class GeneratorError(RuntimeError):
    """Raised when the candidate generator fails to produce results."""
