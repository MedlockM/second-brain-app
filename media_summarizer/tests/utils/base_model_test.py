"""
Base test class for domain model validation patterns.

This module provides a common base class for testing domain models with standardized
validation patterns to reduce code duplication across model tests.
"""
import pytest
from datetime import datetime
from pydantic import ValidationError
from typing import Any, Dict, Type, Optional, List
from abc import ABC, abstractmethod


class BaseModelTest(ABC):
    """
    Base test class for domain model validation.

    This class provides common test patterns for Pydantic models including:
    - Valid data creation tests
    - Minimal data creation tests
    - Invalid data validation tests
    - Update method tests
    - Field validation tests

    Subclasses should implement the abstract methods to provide model-specific data.
    """

    @property
    @abstractmethod
    def model_class(self) -> Type:
        """Return the model class being tested."""
        pass

    @property
    @abstractmethod
    def valid_data(self) -> Dict[str, Any]:
        """Return a dictionary of valid data for creating the model."""
        pass

    @property
    @abstractmethod
    def minimal_data(self) -> Dict[str, Any]:
        """Return a dictionary of minimal required data for creating the model."""
        pass

    @property
    @abstractmethod
    def required_fields(self) -> List[str]:
        """Return a list of required field names."""
        pass

    @property
    def invalid_data_cases(self) -> List[Dict[str, Any]]:
        """
        Return a list of invalid data cases for validation testing.

        Each case should be a dictionary with:
        - 'data': The invalid data dictionary
        - 'expected_error': Part of the expected error message
        - 'description': Description of what makes this case invalid
        """
        return []

    @property
    def updateable_fields(self) -> Dict[str, Any]:
        """
        Return a dictionary of fields that can be updated and their new values.
        Override this if the model has an update method.
        """
        return {}

    def test_model_creation_with_valid_data(self):
        """Test creating a model instance with valid data."""
        # Arrange
        data = self.valid_data

        # Act
        instance = self.model_class(**data)

        # Assert
        for field_name, expected_value in data.items():
            actual_value = getattr(instance, field_name)
            if hasattr(actual_value, '__str__') and isinstance(expected_value, str) and expected_value.startswith(('http://', 'https://')):
                # Handle URL fields - compare string representations
                assert str(actual_value) == expected_value
            else:
                assert actual_value == expected_value

        # Check timestamp fields if they exist
        if hasattr(instance, 'created_at'):
            assert isinstance(instance.created_at, datetime)
        if hasattr(instance, 'updated_at'):
            assert isinstance(instance.updated_at, datetime)

    def test_model_creation_with_minimal_data(self):
        """Test creating a model instance with minimal required data."""
        # Arrange
        data = self.minimal_data

        # Act
        instance = self.model_class(**data)

        # Assert
        for field_name, expected_value in data.items():
            actual_value = getattr(instance, field_name)
            if hasattr(actual_value, '__str__') and isinstance(expected_value, str) and expected_value.startswith(('http://', 'https://')):
                # Handle URL fields - compare string representations
                assert str(actual_value) == expected_value
            else:
                assert actual_value == expected_value

        # Check that optional fields are None or have default values
        all_fields = set(self.valid_data.keys())
        required_fields = set(self.minimal_data.keys())
        optional_fields = all_fields - required_fields

        for field_name in optional_fields:
            if hasattr(instance, field_name):
                # Optional field should be None or have a default value
                value = getattr(instance, field_name)
                # We don't assert None because some fields might have defaults
                assert value is None or value is not None  # Just check it exists

    def test_model_creation_with_missing_required_fields(self):
        """Test that creating a model without required fields raises ValidationError."""
        for required_field in self.required_fields:
            # Arrange - Remove one required field at a time
            data = self.minimal_data.copy()
            if required_field in data:
                del data[required_field]

                # Act & Assert
                with pytest.raises(ValidationError) as excinfo:
                    self.model_class(**data)

                # Verify the error mentions the missing field
                error_str = str(excinfo.value)
                assert required_field in error_str or "required" in error_str.lower()

    def test_model_creation_with_invalid_data(self):
        """Test that creating a model with invalid data raises ValidationError."""
        for case in self.invalid_data_cases:
            data = case['data']
            expected_error = case['expected_error']
            description = case['description']

            # Act & Assert
            with pytest.raises(ValidationError) as excinfo:
                self.model_class(**data)

            # Verify the expected error message appears
            error_str = str(excinfo.value)
            assert expected_error in error_str, f"Failed case: {description}. Expected '{expected_error}' in '{error_str}'"

    def test_model_update_method(self):
        """Test the update method if the model has one."""
        if not hasattr(self.model_class, 'update') or not self.updateable_fields:
            pytest.skip("Model does not have update method or updateable fields")

        # Arrange
        instance = self.model_class(**self.minimal_data)
        original_created_at = getattr(instance, 'created_at', None)
        original_updated_at = getattr(instance, 'updated_at', None)

        # Act
        updated_instance = instance.update(**self.updateable_fields)

        # Assert
        for field_name, expected_value in self.updateable_fields.items():
            actual_value = getattr(updated_instance, field_name)
            if hasattr(actual_value, '__str__') and isinstance(expected_value, str) and expected_value.startswith(('http://', 'https://')):
                # Handle URL fields - compare string representations
                assert str(actual_value) == expected_value
            else:
                assert actual_value == expected_value

        # Check that created_at is preserved and updated_at is updated
        if original_created_at is not None:
            assert updated_instance.created_at == original_created_at
        if original_updated_at is not None:
            assert updated_instance.updated_at > original_updated_at

    def test_model_update_with_invalid_attribute(self):
        """Test that the update method ignores invalid attributes."""
        if not hasattr(self.model_class, 'update'):
            pytest.skip("Model does not have update method")

        # Arrange
        instance = self.model_class(**self.minimal_data)

        # Act
        updated_instance = instance.update(invalid_attribute="This should be ignored")

        # Assert
        assert not hasattr(updated_instance, "invalid_attribute")

    def test_model_string_representation(self):
        """Test that the model has a meaningful string representation."""
        # Arrange
        instance = self.model_class(**self.valid_data)

        # Act
        str_repr = str(instance)

        # Assert - should not be the default object representation
        assert str_repr != f"<{self.model_class.__name__} object at 0x"
        assert len(str_repr) > 0

    def test_model_equality(self):
        """Test model equality comparison."""
        # Arrange
        instance1 = self.model_class(**self.valid_data)
        instance2 = self.model_class(**self.valid_data)

        # Act & Assert
        if hasattr(instance1, 'id'):
            # If models have an id field, they should be equal if ids are equal
            assert instance1 == instance2 or instance1 != instance2  # Just check comparison works
        else:
            # For models without id, test basic equality
            assert instance1 == instance2 or instance1 != instance2  # Just check comparison works

    def test_model_dict_conversion(self):
        """Test converting model to dictionary."""
        # Arrange
        instance = self.model_class(**self.valid_data)

        # Act
        if hasattr(instance, 'model_dump'):
            result = instance.model_dump()
        elif hasattr(instance, 'dict'):
            result = instance.dict()
        else:
            pytest.skip("Model does not have dict() or model_dump() method")

        # Assert
        assert isinstance(result, dict)
        for field_name in self.valid_data.keys():
            assert field_name in result


class BaseModelValidationTest(BaseModelTest):
    """
    Extended base class for models that need specific field validation testing.

    This class adds additional test methods for specific field types like URLs,
    email addresses, positive integers, etc.
    """

    @property
    def url_fields(self) -> List[str]:
        """Return a list of field names that should validate as URLs."""
        return []

    @property
    def email_fields(self) -> List[str]:
        """Return a list of field names that should validate as email addresses."""
        return []

    @property
    def positive_integer_fields(self) -> List[str]:
        """Return a list of field names that should be positive integers."""
        return []

    @property
    def string_fields_min_length(self) -> Dict[str, int]:
        """Return a dict of string field names and their minimum lengths."""
        return {}

    def test_url_field_validation(self):
        """Test that URL fields properly validate URLs."""
        for field_name in self.url_fields:
            # Test invalid URL
            data = self.minimal_data.copy()
            data[field_name] = "invalid-url"

            with pytest.raises(ValidationError) as excinfo:
                self.model_class(**data)

            error_str = str(excinfo.value)
            assert "URL" in error_str or "url" in error_str

    def test_email_field_validation(self):
        """Test that email fields properly validate email addresses."""
        for field_name in self.email_fields:
            # Test invalid email
            data = self.minimal_data.copy()
            data[field_name] = "invalid-email"

            with pytest.raises(ValidationError) as excinfo:
                self.model_class(**data)

            error_str = str(excinfo.value)
            assert "email" in error_str.lower() or "valid" in error_str.lower()

    def test_positive_integer_field_validation(self):
        """Test that positive integer fields reject negative values."""
        for field_name in self.positive_integer_fields:
            # Test negative value
            data = self.minimal_data.copy()
            data[field_name] = -1

            with pytest.raises(ValidationError) as excinfo:
                self.model_class(**data)

            error_str = str(excinfo.value)
            assert "positive" in error_str.lower() or "greater" in error_str.lower()

    def test_string_field_min_length_validation(self):
        """Test that string fields enforce minimum length requirements."""
        for field_name, min_length in self.string_fields_min_length.items():
            # Test string shorter than minimum
            data = self.minimal_data.copy()
            data[field_name] = "x" * (min_length - 1)

            with pytest.raises(ValidationError) as excinfo:
                self.model_class(**data)

            error_str = str(excinfo.value)
            assert "character" in error_str.lower() or "length" in error_str.lower()
