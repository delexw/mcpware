"""
Base interface for security policies
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional
from .models import SessionContext


@dataclass
class PolicyResult:
    """Result of a security policy validation"""
    allowed: bool
    error_message: Optional[str] = None
    should_taint_session: bool = False
    taint_reason: Optional[str] = None


@dataclass
class ValidationContext:
    """Context for security validation"""
    session: SessionContext
    backend_name: str
    backend_security_level: str
    tool_name: str
    tool_arguments: Dict[str, Any]
    config: Dict[str, Any]


class SecurityPolicy(ABC):
    """Abstract base class for security policies"""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize with policy configuration"""
        self.config = config
        self.enabled = self._is_enabled()
    
    @abstractmethod
    def _is_enabled(self) -> bool:
        """Check if this policy is enabled in configuration"""
        pass
    
    @abstractmethod
    def validate(self, context: ValidationContext) -> PolicyResult:
        """
        Validate the request against this security policy
        
        Args:
            context: Validation context containing session, backend info, etc.
            
        Returns:
            PolicyResult indicating if the request is allowed
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the name of this policy"""
        pass 