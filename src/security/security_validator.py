"""
Main security validator that orchestrates all security policies
"""
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from .base import SecurityPolicy, ValidationContext
from .models import SessionContext, BackendAccess
from .tainted_session_policy import TaintedSessionPolicy
from .sql_injection_policy import SQLInjectionPolicy
from .data_flow_policy import DataFlowPolicy
from .sensitive_data_policy import SensitiveDataPolicy

logger = logging.getLogger(__name__)


class SecurityValidator:
    """Orchestrates security policy validation"""
    
    def __init__(self, policy_config: Dict[str, Any]):
        """Initialize with security policy configuration"""
        self.sessions: Dict[str, SessionContext] = {}
        self.policy_config = self._validate_policy(policy_config)
        
        # Initialize all security policies
        self.policies: List[SecurityPolicy] = [
            TaintedSessionPolicy(self.policy_config),
            SQLInjectionPolicy(self.policy_config),
            DataFlowPolicy(self.policy_config)
        ]
        
        # Special handling for sensitive data policy (response validation)
        self.sensitive_data_policy = SensitiveDataPolicy(self.policy_config)
        
        logger.info(f"Initialized security validator with policies: "
                   f"{[p.name for p in self.policies if p.enabled]}")
    
    def _validate_policy(self, policy: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and set defaults for policy configuration"""
        # Required fields
        required_fields = ["backend_security_levels"]
        missing_fields = [field for field in required_fields if field not in policy]
        
        if missing_fields:
            raise ValueError(f"Missing required security policy fields: {', '.join(missing_fields)}")
            
        # Validate backend_security_levels
        if not isinstance(policy["backend_security_levels"], dict):
            raise ValueError("backend_security_levels must be a dictionary")
        
        # Set defaults for optional fields
        defaults = {
            "prevent_sensitive_to_public": True,
            "prevent_sensitive_data_leak": True,
            "sql_injection_protection": True,
            "session_timeout_minutes": 30,
            "log_all_cross_backend_access": True,
            "block_after_suspicious_activity": True
        }
        
        # Merge defaults with provided policy using dictionary unpacking
        # This creates a new dict without mutating the input
        # Defaults are applied first, then overridden by any values in policy
        merged_policy = {**defaults, **policy}
        
        return merged_policy
    
    def create_session(self, session_id: str) -> SessionContext:
        """Create a new session context"""
        session = SessionContext(
            session_id=session_id,
            started_at=datetime.now()
        )
        self.sessions[session_id] = session
        return session
    
    def get_session(self, session_id: str) -> SessionContext:
        """Get or create session context"""
        if session_id not in self.sessions:
            return self.create_session(session_id)
        
        session = self.sessions[session_id]
        
        # Check session timeout
        timeout = timedelta(minutes=self.policy_config["session_timeout_minutes"])
        if datetime.now() - session.started_at > timeout:
            logger.info(f"Session {session_id} timed out, creating new session")
            return self.create_session(session_id)
            
        return session
    
    def validate_backend_access(
        self, 
        session_id: str, 
        backend_name: str, 
        tool_name: str,
        tool_arguments: Dict[str, Any]
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if backend access is allowed
        Returns (is_allowed, error_message)
        """
        session = self.get_session(session_id)
        
        # Get backend security level
        try:
            backend_security_level = self._get_backend_security_level(backend_name)
        except ValueError as e:
            return False, str(e)
        
        # Create validation context
        context = ValidationContext(
            session=session,
            backend_name=backend_name,
            backend_security_level=backend_security_level,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            config=self.policy_config
        )
        
        # Run all policies using walrus operator for cleaner code
        for policy in self.policies:
            if policy.enabled and not (result := policy.validate(context)).allowed:
                # Handle session tainting even when access is denied
                if result.should_taint_session:
                    session.is_tainted = True
                    session.taint_source = result.taint_reason
                return False, result.error_message
        
        # All policies passed - log the access
        access = BackendAccess(
            backend_name=backend_name,
            timestamp=datetime.now(),
            tool_name=tool_name,
            data_security_level=backend_security_level
        )
        session.accessed_backends.append(access)
        
        # Log cross-backend access
        if self.policy_config["log_all_cross_backend_access"]:
            unique_backends = {a.backend_name for a in session.accessed_backends}
            if len(unique_backends) > 1:
                logger.info(f"Cross-backend access: {list(unique_backends)}")
        
        return True, None
    
    def validate_response(
        self,
        session_id: str,
        backend_name: str, 
        response: Any
    ) -> tuple[bool, Optional[str]]:
        """
        Validate response content for sensitive data
        Returns (is_allowed, error_message)
        """
        session = self.get_session(session_id)
        backend_security_level = self._get_backend_security_level(backend_name)
        
        # Check for sensitive data
        has_sensitive_data, detected_patterns = self.sensitive_data_policy.validate_response(
            backend_name, backend_security_level, response
        )
        
        if has_sensitive_data:
            # Use next() to find the last backend access more efficiently
            if access := next(
                (a for a in reversed(session.accessed_backends) if a.backend_name == backend_name),
                None
            ):
                access.has_sensitive_data = True
            
            # Block if this is a public backend
            if backend_security_level == "public":
                return False, f"Response contains sensitive data patterns: {', '.join(detected_patterns)}"
        
        return True, None
    
    def _get_backend_security_level(self, backend_name: str) -> str:
        """Get backend security level from configuration"""
        backend_security_levels = self.policy_config.get("backend_security_levels", {})
        
        if backend_name in backend_security_levels:
            return backend_security_levels[backend_name]
        else:
            raise ValueError(
                f"Backend '{backend_name}' is not classified in security policy. "
                f"Please add it to 'backend_security_levels' with value: public, internal, or sensitive"
            )
    
    def get_session_summary(self, session_id: str) -> Dict[str, Any]:
        """Get security summary for a session"""
        if not (session := self.sessions.get(session_id)):
            return {"error": "Session not found"}
        
        unique_backends = list({access.backend_name for access in session.accessed_backends})
        
        return {
            "session_id": session_id,
            "started_at": session.started_at.isoformat(),
            "duration_seconds": (datetime.now() - session.started_at).total_seconds(),
            "accessed_backends": unique_backends,
            "total_accesses": len(session.accessed_backends),
            "sensitive_data_accesses": sum(1 for a in session.accessed_backends if a.has_sensitive_data),
            "is_tainted": session.is_tainted,
            "taint_source": session.taint_source,
            "backend_sequence": [
                {
                    "backend": a.backend_name,
                    "tool": a.tool_name,
                    "security_level": a.data_security_level,
                    "has_sensitive_data": a.has_sensitive_data,
                    "timestamp": a.timestamp.isoformat()
                }
                for a in session.accessed_backends[-10:]  # Last 10 accesses
            ]
        } 