"""
Transformer module - data transformation functions.
"""
import re
from typing import Any, Callable, Dict, Tuple, Optional


# Built-in transformations: (display_name, function)
TRANSFORMS: Dict[str, Tuple[str, Callable[[Any], Any]]] = {
    "none": ("Brak", lambda x: x),
    "trim": ("Usuń spacje", lambda x: str(x).strip() if x is not None else x),
    "upper": ("WIELKIE LITERY", lambda x: str(x).upper() if x is not None else x),
    "lower": ("małe litery", lambda x: str(x).lower() if x is not None else x),
    "title": ("Pierwsza Wielka", lambda x: str(x).title() if x is not None else x),
    "round_2": ("Zaokrąglij do 2 miejsc", lambda x: round(float(x), 2) if x is not None else x),
    "round_0": ("Liczba całkowita", lambda x: int(round(float(x))) if x is not None else x),
    "int": ("Konwertuj na int", lambda x: int(float(x)) if x is not None else x),
    "remove_html": ("Usuń tagi HTML", lambda x: re.sub(r'<[^<]+?>', '', str(x)) if x is not None else x),
    "first_100": ("Pierwsze 100 znaków", lambda x: str(x)[:100] if x is not None else x),
    "first_255": ("Pierwsze 255 znaków", lambda x: str(x)[:255] if x is not None else x),
    "first_500": ("Pierwsze 500 znaków", lambda x: str(x)[:500] if x is not None else x),
    "extract_numbers": ("Tylko cyfry", lambda x: re.sub(r'[^\d]', '', str(x)) if x is not None else x),
    "extract_decimal": ("Tylko liczba", lambda x: re.sub(r'[^\d.,]', '', str(x)).replace(',', '.') if x is not None else x),
    "remove_newlines": ("Usuń entery", lambda x: str(x).replace('\n', ' ').replace('\r', '') if x is not None else x),
    "normalize_spaces": ("Normalizuj spacje", lambda x: ' '.join(str(x).split()) if x is not None else x),
}


def apply_transform(value: Any, transform_id: Optional[str]) -> Any:
    """Apply a transformation to a value.
    
    Args:
        value: The value to transform
        transform_id: The ID of the transformation to apply
        
    Returns:
        The transformed value
    """
    if transform_id is None or transform_id == "none":
        return value
    
    if transform_id in TRANSFORMS:
        try:
            _, func = TRANSFORMS[transform_id]
            return func(value)
        except (ValueError, TypeError, AttributeError) as e:
            # Return original value if transformation fails
            return value
    
    return value


def get_transform_names() -> Dict[str, str]:
    """Get dictionary of transform IDs to display names."""
    return {k: v[0] for k, v in TRANSFORMS.items()}


def apply_regex_transform(value: Any, pattern: str, replacement: str) -> str:
    """Apply regex find/replace to a value.
    
    Args:
        value: The value to transform
        pattern: Regex pattern to find
        replacement: Replacement string
        
    Returns:
        The transformed string
    """
    if value is None:
        return ""
    
    try:
        return re.sub(pattern, replacement, str(value))
    except re.error:
        return str(value)


def apply_value_mapping(value: Any, mapping: Dict[str, str]) -> Any:
    """Apply a value mapping (dictionary replacement).
    
    Args:
        value: The value to transform
        mapping: Dictionary mapping old values to new values
        
    Returns:
        The mapped value or original if not in mapping
    """
    if value is None:
        return None
    
    str_value = str(value).strip()
    return mapping.get(str_value, value)


def apply_template(values: Dict[str, Any], template: str) -> str:
    """Apply a template with placeholders.
    
    Args:
        values: Dictionary of column names to values
        template: Template string like "{Imię} {Nazwisko}"
        
    Returns:
        The formatted string
    """
    result = template
    for key, val in values.items():
        placeholder = "{" + key + "}"
        result = result.replace(placeholder, str(val) if val is not None else "")
    return result


def validate_regex(pattern: str) -> Tuple[bool, str]:
    """Validate a regex pattern.
    
    Args:
        pattern: The regex pattern to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        re.compile(pattern)
        return True, ""
    except re.error as e:
        return False, str(e)
