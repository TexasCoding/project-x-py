"""
Standardized deprecation utilities for ProjectX SDK.

Author: SDK v3.1.14
Date: 2025-01-17

This module provides consistent deprecation handling across the entire SDK,
ensuring proper warnings, documentation, and migration paths for users.
"""

import functools
import warnings
from collections.abc import Callable
from typing import Any, TypeVar, cast

from deprecated import deprecated as _deprecated_decorator

F = TypeVar("F", bound=Callable[..., Any])


def deprecated(
    reason: str,
    version: str | None = None,
    removal_version: str | None = None,
    replacement: str | None = None,
    category: type[Warning] = DeprecationWarning,
) -> Callable[[F], F]:
    """
    Mark a function, method, or class as deprecated with standardized messaging.

    This decorator provides consistent deprecation warnings across the SDK,
    including version information, migration paths, and proper warning categories.

    Args:
        reason: Brief description of why this is deprecated
        version: Version when this was deprecated (e.g., "3.1.14")
        removal_version: Version when this will be removed (e.g., "4.0.0")
        replacement: What to use instead (e.g., "TradingSuite.track_order()")
        category: Warning category (default: DeprecationWarning)

    Returns:
        Decorated function/class with deprecation warning

    Example:
        ```python
        @deprecated(
            reason="Use TradingSuite.track_order() for integrated tracking",
            version="3.1.14",
            removal_version="5.0.0",
            replacement="TradingSuite.track_order()",
        )
        def old_track_order(order_id: int):
            # Old implementation
            pass
        ```
    """
    # Build the deprecation message
    messages = [reason]

    if version:
        messages.append(f"Deprecated since v{version}.")

    if replacement:
        messages.append(f"Use {replacement} instead.")

    if removal_version:
        messages.append(f"Will be removed in v{removal_version}.")

    full_message = " ".join(messages)

    def decorator(func: F) -> F:
        # Use the deprecated package for IDE support
        if removal_version:
            func = _deprecated_decorator(
                reason=full_message,
                version=version or "",
                action="always",
                category=category,
            )(func)

        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            warnings.warn(full_message, category=category, stacklevel=2)
            return func(*args, **kwargs)

        # Add deprecation info to docstring
        if func.__doc__:
            func.__doc__ = f"**DEPRECATED**: {full_message}\n\n{func.__doc__}"
        else:
            func.__doc__ = f"**DEPRECATED**: {full_message}"

        # Store deprecation metadata
        # We use setattr here to add custom attributes to the function object
        # This avoids type checking issues while preserving the metadata
        setattr(wrapper, "__deprecated__", True)  # noqa: B010
        setattr(wrapper, "__deprecated_reason__", reason)  # noqa: B010
        setattr(wrapper, "__deprecated_version__", version)  # noqa: B010
        setattr(wrapper, "__deprecated_removal__", removal_version)  # noqa: B010
        setattr(wrapper, "__deprecated_replacement__", replacement)  # noqa: B010

        return cast(F, wrapper)

    return decorator


def deprecated_parameter(
    param_name: str,
    reason: str,
    version: str | None = None,
    removal_version: str | None = None,
    replacement: str | None = None,
) -> Callable[[F], F]:
    """
    Mark a specific parameter as deprecated.

    Args:
        param_name: Name of the deprecated parameter
        reason: Why this parameter is deprecated
        version: Version when deprecated
        removal_version: Version when it will be removed
        replacement: What to use instead

    Returns:
        Decorated function that warns when the parameter is used

    Example:
        ```python
        @deprecated_parameter(
            "old_param", reason="Parameter renamed for clarity", replacement="new_param"
        )
        def my_function(new_param: str, old_param: str | None = None):
            if old_param is not None:
                new_param = old_param
            # Rest of implementation
        ```
    """
    messages = [f"Parameter '{param_name}' is deprecated: {reason}"]

    if version:
        messages.append(f"Deprecated since v{version}.")

    if replacement:
        messages.append(f"Use '{replacement}' instead.")

    if removal_version:
        messages.append(f"Will be removed in v{removal_version}.")

    full_message = " ".join(messages)

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if the deprecated parameter was provided
            if param_name in kwargs and kwargs[param_name] is not None:
                warnings.warn(full_message, DeprecationWarning, stacklevel=2)
            return func(*args, **kwargs)

        return cast(F, wrapper)

    return decorator


def deprecated_class(
    reason: str,
    version: str | None = None,
    removal_version: str | None = None,
    replacement: str | None = None,
) -> Callable[[type], type]:
    """
    Mark an entire class as deprecated.

    Args:
        reason: Why this class is deprecated
        version: Version when deprecated
        removal_version: Version when it will be removed
        replacement: What class to use instead

    Returns:
        Decorated class with deprecation warning on instantiation

    Example:
        ```python
        @deprecated_class(
            reason="Integrated into TradingSuite",
            version="3.1.14",
            removal_version="5.0.0",
            replacement="TradingSuite",
        )
        class OldManager:
            pass
        ```
    """
    messages = [reason]

    if version:
        messages.append(f"Deprecated since v{version}.")

    if replacement:
        messages.append(f"Use {replacement} instead.")

    if removal_version:
        messages.append(f"Will be removed in v{removal_version}.")

    full_message = " ".join(messages)

    def decorator(cls: type) -> type:
        # Store the original __init__ - using getattr to satisfy mypy type checking
        original_init = getattr(cls, "__init__")  # noqa: B009

        def new_init(self: Any, *args: Any, **kwargs: Any) -> None:
            warnings.warn(
                f"{cls.__name__} is deprecated: {full_message}",
                DeprecationWarning,
                stacklevel=2,
            )
            original_init(self, *args, **kwargs)

        cls.__init__ = new_init  # type: ignore

        # Update class docstring
        if cls.__doc__:
            cls.__doc__ = f"**DEPRECATED**: {full_message}\n\n{cls.__doc__}"
        else:
            cls.__doc__ = f"**DEPRECATED**: {full_message}"

        # Add deprecation metadata using setattr to avoid type issues
        setattr(cls, "__deprecated__", True)  # noqa: B010
        setattr(cls, "__deprecated_reason__", reason)  # noqa: B010
        setattr(cls, "__deprecated_version__", version)  # noqa: B010
        setattr(cls, "__deprecated_removal__", removal_version)  # noqa: B010
        setattr(cls, "__deprecated_replacement__", replacement)  # noqa: B010

        return cls

    return decorator


def check_deprecated_usage(obj: Any) -> dict[str, Any] | None:
    """
    Check if an object is deprecated and return deprecation information.

    Args:
        obj: Object to check (function, class, or instance)

    Returns:
        Dictionary with deprecation info if deprecated, None otherwise

    Example:
        ```python
        info = check_deprecated_usage(some_function)
        if info:
            print(f"This is deprecated: {info['reason']}")
        ```
    """
    # Check if object has deprecation metadata
    if hasattr(obj, "__deprecated__") and obj.__deprecated__:
        return {
            "deprecated": True,
            "reason": getattr(obj, "__deprecated_reason__", None),
            "version": getattr(obj, "__deprecated_version__", None),
            "removal_version": getattr(obj, "__deprecated_removal__", None),
            "replacement": getattr(obj, "__deprecated_replacement__", None),
        }

    # Check class of instance
    if hasattr(obj, "__class__"):
        return check_deprecated_usage(obj.__class__)

    return None


# Convenience function for warning about deprecated features
def warn_deprecated(
    message: str,
    category: type[Warning] = DeprecationWarning,
    stacklevel: int = 2,
) -> None:
    """
    Issue a standardized deprecation warning.

    Args:
        message: Warning message
        category: Warning category (default: DeprecationWarning)
        stacklevel: Stack level for warning (default: 2)
    """
    warnings.warn(message, category, stacklevel)
