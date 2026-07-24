"""
Miscellaneous helper functions that do not fit into other specific modules.
"""

import hashlib
from typing import Union

def generate_file_hash(content: Union[str, bytes]) -> str:
    """
    Generates a SHA-256 hash for the given content.
    
    This is useful for creating unique filenames for caching.

    Args:
        content: The content to hash, as a string or bytes.

    Returns:
        A hex digest of the hash.
    """
    if isinstance(content, str):
        content = content.encode('utf-8')
    return hashlib.sha256(content).hexdigest()
