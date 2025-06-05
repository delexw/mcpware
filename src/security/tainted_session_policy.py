"""
Tainted session security policy
Blocks all access after a session has been tainted by suspicious activity
"""
from .base import SecurityPolicy, PolicyResult, ValidationContext


class TaintedSessionPolicy(SecurityPolicy):
    """Blocks access from tainted sessions"""
    
    def _is_enabled(self) -> bool:
        """Check if blocking tainted sessions is enabled"""
        return self.config.get("block_after_suspicious_activity", True)
    
    def validate(self, context: ValidationContext) -> PolicyResult:
        """Check if session is tainted"""
        if not self.enabled:
            return PolicyResult(allowed=True)
        
        if context.session.is_tainted:
            return PolicyResult(
                allowed=False,
                error_message=f"Session is tainted from {context.session.taint_source}. Access denied for security."
            )
        
        return PolicyResult(allowed=True)
    
    @property
    def name(self) -> str:
        return "TaintedSessionPolicy" 