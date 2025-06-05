"""
Data flow control security policy
Prevents sensitive data from leaking to public backends
"""
import logging
from .base import SecurityPolicy, PolicyResult, ValidationContext

logger = logging.getLogger(__name__)


class DataFlowPolicy(SecurityPolicy):
    """Controls data flow between different security levels"""
    
    def _is_enabled(self) -> bool:
        """Check if data flow prevention is enabled"""
        return self.config.get("prevent_sensitive_to_public", True)
    
    def validate(self, context: ValidationContext) -> PolicyResult:
        """Validate data flow rules"""
        if not self.enabled:
            return PolicyResult(allowed=True)
        
        # Check if session is tainted
        if context.session.is_tainted:
            if context.backend_security_level == "sensitive":
                return PolicyResult(
                    allowed=False,
                    error_message=f"Tainted session cannot access sensitive backend '{context.backend_name}'"
                )
        
        # If this is a public backend, check if sensitive data was accessed
        if context.backend_security_level == "public":
            # Use any() for early termination when finding sensitive data
            has_sensitive_data = any(
                access.data_security_level == "sensitive" and access.has_sensitive_data
                for access in context.session.accessed_backends
            )
            
            if has_sensitive_data:
                return PolicyResult(
                    allowed=False,
                    error_message="Cannot access public backend after accessing sensitive data"
                )
        
        return PolicyResult(allowed=True)
    
    @property
    def name(self) -> str:
        return "DataFlowPolicy" 