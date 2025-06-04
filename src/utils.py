"""
Utility functions for Gateway MCP Server
"""
import os
import re
import logging

logger = logging.getLogger(__name__)


def substitute_env_vars(value: str, warn_missing: bool = True) -> str:
    """Substitute environment variables in a string
    
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
    def replace_var(match):
        var_name = match.group(1)
        var_value = os.environ.get(var_name)
        
        if var_value is None:
            if warn_missing:
                logger.warning(f"Environment variable ${{{var_name}}} is not set")
            return match.group(0)  # Return the original ${VAR_NAME}
        
        return var_value
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, value) 