from typing import Any, Dict, TypeVar, Type
from pydantic import BaseModel, ValidationError, ConfigDict

T = TypeVar("T", bound="BaseConfigModel")


class BaseConfigModel(BaseModel):
    """
    Base class for all configuration schemas.
    Provides a best-effort loading mechanism.
    """
    model_config = ConfigDict(validate_assignment=True, extra="ignore")

    @classmethod
    def load_best_effort(cls: Type[T], data: Any) -> T:
        """
        Attempt to create an instance from data by validating each field individually.
        Invalid fields will be ignored, falling back to their default values.
        """
        if not isinstance(data, dict):
            # If not a dict, return defaults
            return cls.model_validate({})

        valid_data = {}
        # Iterate over all fields defined in the model
        for field_name, field_info in cls.model_fields.items():
            if field_name not in data:
                continue

            val = data[field_name]

            # Special case: Nested BaseConfigModel
            # annotation can be complex (Optional[...], etc), so we check if it's a subclass
            target_type = field_info.annotation

            # Simplistic check for nested models that also inherit from BaseConfigModel
            if hasattr(target_type, "load_best_effort"):
                # Recursive repair for nested models
                valid_data[field_name] = target_type.load_best_effort(val)
                continue

            # For simple fields, try to validate by making a temporary dict
            # and seeing if Pydantic accepts it in a minimal context.
            try:
                # We validate by putting it into a dict and using model_validate
                # but we need to ensure other non-optional fields aren't missing.
                # A safer way is to use model_validate with a dict containing only
                # the field we want to test, trusting defaults for the rest.
                cls.model_validate({field_name: val})
                valid_data[field_name] = val
            except ValidationError:
                # Value for this specific field is invalid
                print(
                    f"[Config] Field '{cls.__name__}.{field_name}' is invalid. Skipping."
                )
                pass
            except Exception:
                # Unforeseen error
                pass

        # Instantiate the final model.
        # Fields not in valid_data will automatically use their default values.
        return cls.model_validate(valid_data)
