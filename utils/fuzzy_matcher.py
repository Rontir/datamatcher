"""
Fuzzy matching module - provides approximate string matching for keys.
This enables DataMatcher to find matches even with typos or formatting differences.
"""
from typing import Dict, Any, Optional, List, Tuple


def levenshtein_distance(s1: str, s2: str) -> int:
    """
    Calculate the Levenshtein distance between two strings.
    This is the minimum number of single-character edits needed to transform s1 into s2.
    """
    if len(s1) < len(s2):
        return levenshtein_distance(s2, s1)
    
    if len(s2) == 0:
        return len(s1)
    
    previous_row = range(len(s2) + 1)
    
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            # Cost is 0 if characters match, 1 otherwise
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row
    
    return previous_row[-1]


def similarity_ratio(s1: str, s2: str) -> float:
    """
    Calculate similarity ratio between two strings (0.0 to 1.0).
    1.0 means identical strings.
    """
    if not s1 and not s2:
        return 1.0
    if not s1 or not s2:
        return 0.0
    
    max_len = max(len(s1), len(s2))
    distance = levenshtein_distance(s1, s2)
    
    return 1.0 - (distance / max_len)


def find_best_fuzzy_match(
    target_key: str,
    key_lookup: Dict[str, Dict[str, Any]],
    threshold: float = 0.8,
    max_candidates: int = 100
) -> Tuple[Optional[str], float, Optional[Dict[str, Any]]]:
    """
    Find the best fuzzy match for a target key in the lookup dictionary.
    
    Args:
        target_key: The key to find a match for
        key_lookup: Dictionary of {normalized_key: row_data}
        threshold: Minimum similarity ratio to consider a match (0.0-1.0)
        max_candidates: Maximum number of candidates to check (for performance)
    
    Returns:
        Tuple of (matched_key, similarity_score, row_data) or (None, 0.0, None)
    """
    if not target_key or not key_lookup:
        return None, 0.0, None
    
    target_lower = target_key.lower()
    best_match = None
    best_score = 0.0
    best_data = None
    
    # Optimization: first try prefix matching for large lookups
    candidates = list(key_lookup.keys())
    
    # If too many candidates, filter by first character or length similarity
    if len(candidates) > max_candidates:
        # Filter by first char match or similar length
        target_len = len(target_key)
        candidates = [
            k for k in candidates
            if (k and k[0].lower() == target_lower[0] if target_lower else True)
            or abs(len(k) - target_len) <= 2
        ][:max_candidates]
    
    for key in candidates:
        if key is None:
            continue
        
        score = similarity_ratio(target_lower, key.lower())
        
        if score > best_score and score >= threshold:
            best_score = score
            best_match = key
            best_data = key_lookup.get(key)
    
    return best_match, best_score, best_data


def find_partial_matches(
    target_key: str,
    key_lookup: Dict[str, Dict[str, Any]],
    match_type: str = "contains"
) -> List[Tuple[str, Dict[str, Any]]]:
    """
    Find keys that partially match the target.
    
    Args:
        target_key: The key to find matches for
        key_lookup: Dictionary of {normalized_key: row_data}
        match_type: "contains", "startswith", or "endswith"
    
    Returns:
        List of (matched_key, row_data) tuples
    """
    if not target_key or not key_lookup:
        return []
    
    target_lower = target_key.lower()
    matches = []
    
    for key, data in key_lookup.items():
        if key is None or data is None:
            continue
        
        key_lower = key.lower()
        
        if match_type == "contains":
            if target_lower in key_lower or key_lower in target_lower:
                matches.append((key, data))
        elif match_type == "startswith":
            if key_lower.startswith(target_lower) or target_lower.startswith(key_lower):
                matches.append((key, data))
        elif match_type == "endswith":
            if key_lower.endswith(target_lower) or target_lower.endswith(key_lower):
                matches.append((key, data))
    
    return matches


def normalize_for_fuzzy(value: str) -> str:
    """
    Normalize a string for fuzzy matching by removing common variations.
    """
    if not value:
        return ""
    
    result = value.lower().strip()
    
    # Remove common punctuation that might differ
    for char in ['-', '_', '.', ',', '/', '\\', '(', ')', '[', ']', '"', "'"]:
        result = result.replace(char, ' ')
    
    # Collapse multiple spaces
    while '  ' in result:
        result = result.replace('  ', ' ')
    
    return result.strip()
