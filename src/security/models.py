"""
Data models for security validation
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class BackendAccess:
    """Record of a backend access"""
    backend_name: str
    timestamp: datetime
    tool_name: str
    data_security_level: str
    has_sensitive_data: bool = False


@dataclass
class SessionContext:
    """Context for a user session"""
    session_id: str
    started_at: datetime
    accessed_backends: List[BackendAccess] = field(default_factory=list)
    is_tainted: bool = False
    taint_source: Optional[str] = None 