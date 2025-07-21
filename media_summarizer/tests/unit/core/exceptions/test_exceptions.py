"""
Unit tests for custom exceptions.
"""
import pytest

from media_summarizer.core.exceptions import (
    MediaSummarizerError,
    ResourceNotFoundError,
    ValidationError,
    AuthenticationError,
    AuthorizationError,
    InsufficientCreditsError,
    ExternalServiceError,
    ProcessingError
)


class TestMediaSummarizerError:
    """Test cases for the MediaSummarizerError class."""
    
    def test_default_message(self):
        """Test the default error message."""
        error = MediaSummarizerError()
        assert str(error) == "An error occurred in Media Summarizer"
        assert error.message == "An error occurred in Media Summarizer"
    
    def test_custom_message(self):
        """Test a custom error message."""
        error = MediaSummarizerError("Custom error message")
        assert str(error) == "Custom error message"
        assert error.message == "Custom error message"
    
    def test_inheritance(self):
        """Test that MediaSummarizerError inherits from Exception."""
        error = MediaSummarizerError()
        assert isinstance(error, Exception)


class TestResourceNotFoundError:
    """Test cases for the ResourceNotFoundError class."""
    
    def test_error_message(self):
        """Test the error message format."""
        error = ResourceNotFoundError("Podcast", "podcast-123")
        assert str(error) == "Podcast with ID 'podcast-123' not found"
        assert error.resource_type == "Podcast"
        assert error.resource_id == "podcast-123"
    
    def test_inheritance(self):
        """Test that ResourceNotFoundError inherits from MediaSummarizerError."""
        error = ResourceNotFoundError("Podcast", "podcast-123")
        assert isinstance(error, MediaSummarizerError)


class TestValidationError:
    """Test cases for the ValidationError class."""
    
    def test_default_message(self):
        """Test the default error message."""
        error = ValidationError()
        assert str(error) == "Validation failed"
    
    def test_custom_message(self):
        """Test a custom error message."""
        error = ValidationError("Invalid email format")
        assert str(error) == "Invalid email format"
    
    def test_inheritance(self):
        """Test that ValidationError inherits from MediaSummarizerError."""
        error = ValidationError()
        assert isinstance(error, MediaSummarizerError)


class TestAuthenticationError:
    """Test cases for the AuthenticationError class."""
    
    def test_default_message(self):
        """Test the default error message."""
        error = AuthenticationError()
        assert str(error) == "Authentication failed"
    
    def test_custom_message(self):
        """Test a custom error message."""
        error = AuthenticationError("Invalid credentials")
        assert str(error) == "Invalid credentials"
    
    def test_inheritance(self):
        """Test that AuthenticationError inherits from MediaSummarizerError."""
        error = AuthenticationError()
        assert isinstance(error, MediaSummarizerError)


class TestAuthorizationError:
    """Test cases for the AuthorizationError class."""
    
    def test_default_message(self):
        """Test the default error message."""
        error = AuthorizationError()
        assert str(error) == "Not authorized to perform this action"
    
    def test_custom_message(self):
        """Test a custom error message."""
        error = AuthorizationError("Admin access required")
        assert str(error) == "Admin access required"
    
    def test_inheritance(self):
        """Test that AuthorizationError inherits from MediaSummarizerError."""
        error = AuthorizationError()
        assert isinstance(error, MediaSummarizerError)


class TestInsufficientCreditsError:
    """Test cases for the InsufficientCreditsError class."""
    
    def test_error_message(self):
        """Test the error message format."""
        error = InsufficientCreditsError("user-123", 10, 5)
        assert str(error) == "User 'user-123' has insufficient credits (required: 10, available: 5)"
        assert error.user_id == "user-123"
        assert error.required == 10
        assert error.available == 5
    
    def test_inheritance(self):
        """Test that InsufficientCreditsError inherits from MediaSummarizerError."""
        error = InsufficientCreditsError("user-123", 10, 5)
        assert isinstance(error, MediaSummarizerError)


class TestExternalServiceError:
    """Test cases for the ExternalServiceError class."""
    
    def test_default_message(self):
        """Test the default error message."""
        error = ExternalServiceError("S3")
        assert str(error) == "S3 error: External service error"
        assert error.service_name == "S3"
    
    def test_custom_message(self):
        """Test a custom error message."""
        error = ExternalServiceError("SQS", "Queue does not exist")
        assert str(error) == "SQS error: Queue does not exist"
        assert error.service_name == "SQS"
    
    def test_inheritance(self):
        """Test that ExternalServiceError inherits from MediaSummarizerError."""
        error = ExternalServiceError("S3")
        assert isinstance(error, MediaSummarizerError)


class TestProcessingError:
    """Test cases for the ProcessingError class."""
    
    def test_default_message(self):
        """Test the default error message."""
        error = ProcessingError("job-123", "transcription")
        assert str(error) == "Processing failed for job 'job-123' at step 'transcription': Processing failed"
        assert error.job_id == "job-123"
        assert error.step == "transcription"
    
    def test_custom_message(self):
        """Test a custom error message."""
        error = ProcessingError("job-123", "summarization", "LLM API error")
        assert str(error) == "Processing failed for job 'job-123' at step 'summarization': LLM API error"
        assert error.job_id == "job-123"
        assert error.step == "summarization"
    
    def test_inheritance(self):
        """Test that ProcessingError inherits from MediaSummarizerError."""
        error = ProcessingError("job-123", "transcription")
        assert isinstance(error, MediaSummarizerError)


class TestExceptionPropagation:
    """Test cases for exception propagation."""
    
    def test_catch_base_exception(self):
        """Test catching all custom exceptions with the base exception."""
        exceptions = [
            ResourceNotFoundError("Podcast", "podcast-123"),
            ValidationError("Invalid input"),
            AuthenticationError("Invalid token"),
            AuthorizationError("Insufficient permissions"),
            InsufficientCreditsError("user-123", 10, 5),
            ExternalServiceError("S3", "Access denied"),
            ProcessingError("job-123", "transcription", "Model error")
        ]
        
        for exception in exceptions:
            try:
                raise exception
            except MediaSummarizerError as e:
                # Should catch all custom exceptions
                assert isinstance(e, MediaSummarizerError)
    
    def test_exception_hierarchy(self):
        """Test the exception hierarchy."""
        # Create a function that raises different exceptions based on input
        def process_request(request_type):
            if request_type == "not_found":
                raise ResourceNotFoundError("Podcast", "podcast-123")
            elif request_type == "validation":
                raise ValidationError("Invalid input")
            elif request_type == "authentication":
                raise AuthenticationError("Invalid token")
            elif request_type == "authorization":
                raise AuthorizationError("Insufficient permissions")
            elif request_type == "credits":
                raise InsufficientCreditsError("user-123", 10, 5)
            elif request_type == "external":
                raise ExternalServiceError("S3", "Access denied")
            elif request_type == "processing":
                raise ProcessingError("job-123", "transcription", "Model error")
            else:
                raise MediaSummarizerError("Unknown error")
        
        # Test catching specific exceptions
        with pytest.raises(ResourceNotFoundError):
            process_request("not_found")
        
        with pytest.raises(ValidationError):
            process_request("validation")
        
        with pytest.raises(AuthenticationError):
            process_request("authentication")
        
        with pytest.raises(AuthorizationError):
            process_request("authorization")
        
        with pytest.raises(InsufficientCreditsError):
            process_request("credits")
        
        with pytest.raises(ExternalServiceError):
            process_request("external")
        
        with pytest.raises(ProcessingError):
            process_request("processing")
        
        with pytest.raises(MediaSummarizerError):
            process_request("unknown")
    
    def test_exception_attributes(self):
        """Test accessing exception attributes."""
        # ResourceNotFoundError
        try:
            raise ResourceNotFoundError("Podcast", "podcast-123")
        except ResourceNotFoundError as e:
            assert e.resource_type == "Podcast"
            assert e.resource_id == "podcast-123"
        
        # InsufficientCreditsError
        try:
            raise InsufficientCreditsError("user-123", 10, 5)
        except InsufficientCreditsError as e:
            assert e.user_id == "user-123"
            assert e.required == 10
            assert e.available == 5
        
        # ExternalServiceError
        try:
            raise ExternalServiceError("S3", "Access denied")
        except ExternalServiceError as e:
            assert e.service_name == "S3"
        
        # ProcessingError
        try:
            raise ProcessingError("job-123", "transcription", "Model error")
        except ProcessingError as e:
            assert e.job_id == "job-123"
            assert e.step == "transcription"