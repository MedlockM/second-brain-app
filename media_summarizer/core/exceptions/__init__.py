"""
Custom exceptions for Media Summarizer.

This module defines custom exceptions used throughout the application.
"""

class MediaSummarizerError(Exception):
    """Base exception for all Media Summarizer errors."""
    
    def __init__(self, message: str = "An error occurred in Media Summarizer"):
        self.message = message
        super().__init__(self.message)


class ResourceNotFoundError(MediaSummarizerError):
    """Exception raised when a requested resource is not found."""
    
    def __init__(self, resource_type: str, resource_id: str):
        self.resource_type = resource_type
        self.resource_id = resource_id
        message = f"{resource_type} with ID '{resource_id}' not found"
        super().__init__(message)


class ValidationError(MediaSummarizerError):
    """Exception raised when validation fails."""
    
    def __init__(self, message: str = "Validation failed"):
        super().__init__(message)


class AuthenticationError(MediaSummarizerError):
    """Exception raised when authentication fails."""
    
    def __init__(self, message: str = "Authentication failed"):
        super().__init__(message)


class AuthorizationError(MediaSummarizerError):
    """Exception raised when authorization fails."""
    
    def __init__(self, message: str = "Not authorized to perform this action"):
        super().__init__(message)


class InsufficientCreditsError(MediaSummarizerError):
    """Exception raised when a user has insufficient credits."""
    
    def __init__(self, user_id: str, required: int, available: int):
        self.user_id = user_id
        self.required = required
        self.available = available
        message = f"User '{user_id}' has insufficient credits (required: {required}, available: {available})"
        super().__init__(message)


class ExternalServiceError(MediaSummarizerError):
    """Exception raised when an external service fails."""
    
    def __init__(self, service_name: str, message: str = "External service error"):
        self.service_name = service_name
        full_message = f"{service_name} error: {message}"
        super().__init__(full_message)


class ProcessingError(MediaSummarizerError):
    """Exception raised when processing fails."""
    
    def __init__(self, job_id: str, step: str, message: str = "Processing failed"):
        self.job_id = job_id
        self.step = step
        full_message = f"Processing failed for job '{job_id}' at step '{step}': {message}"
        super().__init__(full_message)