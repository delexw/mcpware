"""
SQL injection detection security policy
Detects and blocks suspicious SQL patterns that might indicate data exfiltration
"""
import re
import logging
from typing import Pattern as RePattern, List
from .base import SecurityPolicy, PolicyResult, ValidationContext

logger = logging.getLogger(__name__)


class SQLInjectionPolicy(SecurityPolicy):
    """Detects and blocks SQL injection attempts"""
    
    # Pre-compiled SQL patterns for better performance
    SUSPICIOUS_SQL_PATTERNS: List[RePattern[str]] = [
        re.compile(r'SELECT\s+\*\s+FROM\s+(users|accounts|credentials|passwords|tokens|api_keys)', re.IGNORECASE),
        re.compile(r'(password|hash|salt|token|secret|key|ssn|credit_card)', re.IGNORECASE),
        re.compile(r'UNION\s+SELECT', re.IGNORECASE),
        re.compile(r'INTO\s+OUTFILE', re.IGNORECASE),
        re.compile(r'LOAD_FILE', re.IGNORECASE)
    ]
    
    def _is_enabled(self) -> bool:
        """Check if SQL injection protection is enabled"""
        return self.config.get("sql_injection_protection", True)
    
    def validate(self, context: ValidationContext) -> PolicyResult:
        """Check for SQL injection patterns with early returns"""
        # Early return if disabled
        if not self.enabled:
            return PolicyResult(allowed=True)
        
        # Early return if not SQL-related tool
        if context.tool_name not in ["run_query", "execute_sql"]:
            return PolicyResult(allowed=True)
        
        query = context.tool_arguments.get("query", "")
        
        # Use walrus operator for cleaner detection and logging
        if self._detect_suspicious_sql(query):
            logger.warning(f"Suspicious SQL detected in {context.backend_name}: {query[:100]}...")
            return PolicyResult(
                allowed=False,
                error_message="Query contains suspicious patterns and was blocked",
                should_taint_session=True,
                taint_reason=f"suspicious SQL in {context.backend_name}"
            )
        
        return PolicyResult(allowed=True)
    
    def _detect_suspicious_sql(self, query: str) -> bool:
        """Detect suspicious SQL patterns using pre-compiled regex"""
        # Use any() for early termination on first match
        return any(pattern.search(query) for pattern in self.SUSPICIOUS_SQL_PATTERNS)
    
    @property
    def name(self) -> str:
        return "SQLInjectionPolicy" 