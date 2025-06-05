"""
Sensitive data detection security policy
Scans responses for sensitive data patterns and blocks leaks from public backends
"""
import re
import json
import logging
from typing import Any, List, Tuple, Pattern as RePattern, NamedTuple
from .base import SecurityPolicy, PolicyResult, ValidationContext

logger = logging.getLogger(__name__)


class SensitivePattern(NamedTuple):
    """Structured pattern definition for better clarity"""
    pattern: RePattern[str]
    name: str
    
    @classmethod
    def create(cls, pattern_str: str, name: str) -> 'SensitivePattern':
        """Factory method to create pattern with compiled regex"""
        return cls(re.compile(pattern_str, re.IGNORECASE), name)


class SensitiveDataPolicy(SecurityPolicy):
    """Detects and prevents sensitive data leaks"""
    
    # Pre-compiled patterns for better performance
    SENSITIVE_PATTERNS: List[SensitivePattern] = [
        SensitivePattern.create(r'(?i)(password|passwd|pwd)\s*[:=]\s*\S+', 'password'),
        SensitivePattern.create(r'(?i)(api[_-]?key|apikey)\s*[:=]\s*\S+', 'api_key'),
        SensitivePattern.create(r'(?i)(secret|token)\s*[:=]\s*\S+', 'secret'),
        SensitivePattern.create(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', 'email'),
        SensitivePattern.create(r'\b(?:\d{3}[-.]?)?\d{3}[-.]?\d{4}\b', 'phone'),
        SensitivePattern.create(r'\b\d{3}-\d{2}-\d{4}\b', 'ssn'),
        SensitivePattern.create(r'(?i)(credit[_-]?card|cc[_-]?number)\s*[:=]\s*\d+', 'credit_card'),
    ]
    
    def _is_enabled(self) -> bool:
        """Check if sensitive data leak prevention is enabled"""
        return self.config.get("prevent_sensitive_data_leak", True)
    
    def validate(self, context: ValidationContext) -> PolicyResult:
        """This policy only validates responses, not requests"""
        # Request validation always passes - this policy is for responses
        return PolicyResult(allowed=True)
    
    def validate_response(self, backend_name: str, backend_security_level: str, 
                         response: Any) -> Tuple[bool, List[str]]:
        """
        Validate response content for sensitive data
        
        Returns:
            Tuple of (has_sensitive_data, detected_patterns)
        """
        if not self.enabled:
            return False, []
        
        # Convert response to string for pattern matching
        response_str = json.dumps(response) if isinstance(response, dict) else str(response)
        
        # Check for sensitive patterns using list comprehension
        detected_patterns = [
            pattern.name 
            for pattern in self.SENSITIVE_PATTERNS 
            if pattern.pattern.search(response_str)
        ]
        
        if detected_patterns and backend_security_level == "public":
            logger.warning(f"Blocked sensitive data leak from {backend_name}: {detected_patterns}")
        
        return bool(detected_patterns), detected_patterns
    
    @property
    def name(self) -> str:
        return "SensitiveDataPolicy" 