"""
Utility functions for mcpware
"""
import logging
import os
import re
from typing import Pattern

logger = logging.getLogger(__name__)

# Pre-compile regex pattern for better performance
ENV_VAR_PATTERN: Pattern[str] = re.compile(r'\$\{([^}]+)\}')


def substitute_env_vars(value: str, warn_missing: bool = True) -> str:
    """Substitute environment variables in a string.
    
    Args:
        value: String that may contain ${VAR_NAME} placeholders
        warn_missing: Whether to log warnings for missing variables
        
    Returns:
        String with environment variables substituted
        
    Example:
        >>> os.environ['TOKEN'] = 'secret123'
        >>> substitute_env_vars('Bearer ${TOKEN}')
        'Bearer secret123'
    """
    def replace_var(match: re.Match[str]) -> str:
        var_name = match.group(1)
        
        # Use walrus operator for cleaner code
        if (var_value := os.environ.get(var_name)) is not None:
            return var_value
        
        if warn_missing:
            logger.warning(f"Environment variable ${{{var_name}}} is not set")
        return match.group(0)  # Return the original ${VAR_NAME}
    
    return ENV_VAR_PATTERN.sub(replace_var, value) 