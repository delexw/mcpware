"""Tests for the SecurityValidator module"""
import pytest
from datetime import datetime, timedelta
from src.security import SecurityValidator, SessionContext, BackendAccess


class TestSecurityValidator:
    """Test cases for SecurityValidator"""
    
    @pytest.fixture
    def validator(self):
        """Create a security validator with default config"""
        policy = {
            "backend_security_levels": {
                "github": "public",
                "gitlab": "public",
                "web-scraper": "public",
                "local-mysql": "sensitive",
                "local-postgres": "sensitive",
                "local-redis": "internal",
                "production-db": "sensitive",
                "api-keys-store": "sensitive"
            }
        }
        return SecurityValidator(policy)
    
    @pytest.fixture
    def custom_validator(self):
        """Create a validator with custom policy"""
        policy = {
            "backend_security_levels": {
                "github": "public",
                "web-scraper": "public",
                "local-mysql": "sensitive"
            },
            "prevent_sensitive_to_public": True,
            "prevent_sensitive_data_leak": True,
            "sql_injection_protection": True,
            "session_timeout_minutes": 5,
            "log_all_cross_backend_access": True,
            "block_after_suspicious_activity": True
        }
        return SecurityValidator(policy)
    
    def test_session_creation(self, validator):
        """Test session creation and retrieval"""
        session_id = "test-session-123"
        session = validator.create_session(session_id)
        
        assert session.session_id == session_id
        assert isinstance(session.started_at, datetime)
        assert len(session.accessed_backends) == 0
        assert not session.is_tainted
        
        # Test retrieval
        retrieved = validator.get_session(session_id)
        assert retrieved.session_id == session_id
    
    def test_session_timeout(self, custom_validator):
        """Test session timeout handling"""
        session_id = "timeout-test"
        session1 = custom_validator.create_session(session_id)
        
        # Manually set old timestamp
        old_time = datetime.now() - timedelta(minutes=10)
        session1.started_at = old_time
        
        # Should create new session due to timeout
        session2 = custom_validator.get_session(session_id)
        assert session2.started_at > old_time
    
    def test_backend_classification(self, validator):
        """Test backend classification logic"""
        # Test that valid backends can be accessed
        allowed, error = validator.validate_backend_access(
            "test-session", "github", "list_repos", {}
        )
        assert allowed is True
        
        allowed, error = validator.validate_backend_access(
            "test-session", "local-mysql", "run_query", {"query": "SELECT 1"}
        )
        assert allowed is True
        
        # Unclassified backends should raise an error
        allowed, error = validator.validate_backend_access(
            "test-session", "unclassified-backend", "some_tool", {}
        )
        assert allowed is False
        assert "not classified in security policy" in error
    
    def test_sql_injection_detection(self, validator):
        """Test SQL injection pattern detection"""
        session_id = "sql-test"
        
        malicious_queries = [
            "SELECT * FROM users WHERE 1=1 UNION SELECT password FROM admin",
            "SELECT password, salt FROM credentials",
            "SELECT * INTO OUTFILE '/tmp/data.txt' FROM users",
            "SELECT LOAD_FILE('/etc/passwd')",
            "select * from api_keys"
        ]
        
        for i, query in enumerate(malicious_queries):
            # Use different session for each query to avoid blocking due to tainting
            allowed, error = validator.validate_backend_access(
                f"{session_id}-{i}", "local-mysql", "run_query", {"query": query}
            )
            assert allowed is False
            assert "suspicious patterns" in error
        
        # Safe queries
        safe_queries = [
            "SELECT name, email FROM users WHERE id = 123",
            "SELECT COUNT(*) FROM products",
            "SELECT * FROM products WHERE category = 'electronics'"
        ]
        
        for query in safe_queries:
            # Create new session for each safe query
            allowed, error = validator.validate_backend_access(
                f"safe-sql-{query[:10]}", "local-mysql", "run_query", {"query": query}
            )
            assert allowed is True
    
    def test_public_to_sensitive_prevention(self, validator):
        """Test prevention of sensitive data leaking to public backends"""
        session_id = "test-flow"
        
        # Access public backend first
        allowed, error = validator.validate_backend_access(
            session_id, "github", "list_issues", {}
        )
        assert allowed is True
        
        # Access sensitive backend - should be allowed
        allowed, error = validator.validate_backend_access(
            session_id, "local-mysql", "run_query", 
            {"query": "SELECT * FROM products"}
        )
        assert allowed is True
        
        # Mark the sensitive access as having sensitive data
        session = validator.get_session(session_id)
        session.accessed_backends[-1].has_sensitive_data = True
        
        # Try to access public backend again - should be blocked
        allowed, error = validator.validate_backend_access(
            session_id, "github", "create_issue", 
            {"title": "Test", "body": "Some content"}
        )
        assert allowed is False
        assert "Cannot access public backend after accessing sensitive data" in error
    
    def test_tainted_session_blocking(self, validator):
        """Test that tainted sessions are blocked"""
        session_id = "taint-test"
        
        # Perform suspicious SQL query
        allowed, error = validator.validate_backend_access(
            session_id, "local-mysql", "run_query",
            {"query": "SELECT * FROM passwords WHERE 1=1"}
        )
        assert allowed is False
        assert "suspicious patterns" in error
        
        # Session should be tainted
        session = validator.get_session(session_id)
        assert session.is_tainted is True
        
        # Any further access should be blocked
        allowed, error = validator.validate_backend_access(
            session_id, "github", "list_repos", {}
        )
        assert allowed is False
        assert "tainted" in error.lower()
    
    def test_sensitive_data_detection(self, validator):
        """Test detection of sensitive data in responses"""
        session_id = "sensitive-test"
        
        # Responses with sensitive data
        sensitive_responses = [
            {"result": "password: secret123"},
            {"data": {"api_key": "sk-1234567890"}},
            {"users": [{"email": "user@example.com", "ssn": "123-45-6789"}]},
            {"config": "API_KEY=abcdef123 SECRET=xyz789"}
        ]
        
        for response in sensitive_responses:
            allowed, error = validator.validate_response(
                session_id, "github", response
            )
            assert allowed is False
            assert "sensitive data patterns" in error
    
    def test_public_to_sensitive_allowed(self, validator):
        """Test that public to sensitive transitions are allowed (no rate limiting)"""
        session_id = "transition-test"
        
        # Access public backend
        allowed, error = validator.validate_backend_access(
            session_id, "github", "list_repos", {}
        )
        assert allowed is True
        
        # Immediate access to sensitive backend - should be allowed
        allowed, error = validator.validate_backend_access(
            session_id, "local-mysql", "run_query", 
            {"query": "SELECT COUNT(*) FROM products WHERE category = 'electronics'"}
        )
        assert allowed is True  # No more rate limiting
        assert error is None
    
    def test_session_summary(self, validator):
        """Test session summary generation"""
        session_id = "summary-test"
        
        # Perform some accesses
        validator.validate_backend_access(
            session_id, "github", "list_repos", {}
        )
        
        validator.validate_backend_access(
            session_id, "local-mysql", "run_query",
            {"query": "SELECT name FROM products"}
        )
        
        summary = validator.get_session_summary(session_id)
        
        assert summary["session_id"] == session_id
        assert len(summary["accessed_backends"]) == 2
        assert summary["total_accesses"] == 2
        assert not summary["is_tainted"]
        assert "github" in summary["accessed_backends"]
        assert "local-mysql" in summary["accessed_backends"]
    
    def test_data_flow_with_clean_session(self, validator):
        """Test that data flow is allowed with clean sessions"""
        session_id = "clean-flow"
        
        # Access sensitive backend
        allowed, _ = validator.validate_backend_access(
            session_id, "local-mysql", "run_query",
            {"query": "SELECT COUNT(*) FROM users"}
        )
        assert allowed is True
        
        # Access public backend without sensitive data - should be allowed
        allowed, _ = validator.validate_backend_access(
            session_id, "github", "list_repos", {}
        )
        assert allowed is True
    
    def test_init_with_valid_policy(self):
        """Test initialization with valid security policy"""
        policy = {
            "backend_security_levels": {
                "github": "public",
                "database": "sensitive"
            }
        }
        validator = SecurityValidator(policy)
        
        # Check that the original values are preserved
        assert validator.policy_config["backend_security_levels"] == policy["backend_security_levels"]
        
        # Check that defaults were added
        assert validator.policy_config["prevent_sensitive_to_public"] is True
        assert validator.policy_config["prevent_sensitive_data_leak"] is True
        assert validator.policy_config["sql_injection_protection"] is True
        assert validator.policy_config["session_timeout_minutes"] == 30
        assert validator.policy_config["log_all_cross_backend_access"] is True
        assert validator.policy_config["block_after_suspicious_activity"] is True
        
        # Ensure the original policy object wasn't mutated
        assert len(policy) == 1  # Still only has backend_security_levels
    
    def test_init_with_invalid_policy(self):
        """Test initialization with invalid security policy"""
        # Missing required field
        policy = {}
        with pytest.raises(ValueError, match="Missing required security policy"):
            SecurityValidator(policy)
            
        # Invalid type
        policy = {
            "backend_security_levels": "not_a_dict"
        }
        with pytest.raises(ValueError, match="backend_security_levels must be a dictionary"):
            SecurityValidator(policy) 