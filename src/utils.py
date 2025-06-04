"""
Utility functions for Gateway MCP Server
"""
import os
import re


def substitute_env_vars(value: str) -> str:
    """Substitute environment variables in a string
    
    Args:
        value: String that may contain ${VAR_NAME} placeholders
        
    Returns:
        String with environment variables substituted
        
    Example:
        >>> os.environ['TOKEN'] = 'secret123'
        >>> substitute_env_vars('Bearer ${TOKEN}')
        'Bearer secret123'
    """
    def replace_var(match):
        var_name = match.group(1)
        return os.environ.get(var_name, match.group(0))
    
    return re.sub(r'\$\{([^}]+)\}', replace_var, value) 