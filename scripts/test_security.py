#!/usr/bin/env python3
"""
Demonstration of security validation in mcpware
Shows how the system prevents cross-backend information leakage
"""
import json
import asyncio
from datetime import datetime

# Add parent directory to path
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.security import SecurityValidator


def print_header(title):
    """Print a formatted header"""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}\n")


def print_result(allowed, error=None):
    """Print the result of a validation"""
    if allowed:
        print("✅ ALLOWED")
    else:
        print(f"❌ BLOCKED: {error}")


async def main():
    """Run security validation demonstrations"""
    
    # Create test configuration with both public and sensitive backends
    backends = [
        {
            "name": "github",
            "command": "echo",
            "args": ["github-test-server"],
            "description": "GitHub MCP Server",
        },
        {
            "name": "database",
            "command": "echo",
            "args": ["database-test-server"],
            "description": "Database MCP Server",
        },
    ]
    
    config = {
        "backends": backends,
        "security_policy": {
            "backend_security_levels": {
                "github-test": "public",
                "database-test": "sensitive"
            },
            "prevent_sensitive_to_public": True,
            "prevent_sensitive_data_leak": True,
            "sql_injection_protection": True,
            "session_timeout_minutes": 30,
            "log_all_cross_backend_access": True,
            "block_after_suspicious_activity": True
        }
    }
    
    validator = SecurityValidator(config["security_policy"])
    
    print_header("Security Validation Demonstration")
    
    # Scenario 1: Normal flow - accessing backends separately
    print("Scenario 1: Normal Backend Access")
    print("-" * 40)
    
    session1 = "normal-session"
    
    print("1. Accessing GitHub backend...")
    allowed, error = validator.validate_backend_access(
        session1, "github-test", "list_issues", {}
    )
    print_result(allowed, error)
    
    print("\n2. Accessing MySQL backend (after waiting)...")
    # Simulate time passing
    session = validator.get_session(session1)
    session.accessed_backends[-1].timestamp = datetime.now().replace(second=0)
    
    allowed, error = validator.validate_backend_access(
        session1, "database-test", "run_query", 
        {"query": "SELECT name FROM products"}
    )
    print_result(allowed, error)
    
    # Scenario 2: Attack attempt - malicious SQL injection
    print_header("Scenario 2: SQL Injection Attack (Immediate)")
    
    session2 = "attack-sql-immediate"
    
    print("1. Attacker tries SQL injection directly...")
    allowed, error = validator.validate_backend_access(
        session2, "database-test", "run_query",
        {"query": "SELECT * FROM users UNION SELECT password FROM admin"}
    )
    print_result(allowed, error)
    
    print("\n2. Session is now tainted, trying to access public backend...")
    allowed, error = validator.validate_backend_access(
        session2, "github-test", "create_issue", 
        {"title": "Test", "body": "Some content"}
    )
    print_result(allowed, error)
    
    # Scenario 3: Data exfiltration attempt
    print_header("Scenario 3: Data Exfiltration Prevention")
    
    session3 = "exfiltration-attempt"
    
    print("1. Attempting to run malicious SQL query...")
    allowed, error = validator.validate_backend_access(
        session3, "database-test", "run_query",
        {"query": "SELECT * FROM passwords UNION SELECT api_key FROM tokens"}
    )
    print_result(allowed, error)
    
    print("\n2. Session is now tainted, trying to access any backend...")
    allowed, error = validator.validate_backend_access(
        session3, "github-test", "list_repos", {}
    )
    print_result(allowed, error)
    
    # Scenario 4: Data leak prevention
    print_header("Scenario 4: Sensitive Data Leak Prevention")
    
    session4 = "leak-prevention"
    
    print("1. Accessing MySQL and getting sensitive data...")
    # First access MySQL
    validator.validate_backend_access(
        session4, "database-test", "run_query",
        {"query": "SELECT email FROM users"}
    )
    
    # Mark as having sensitive data
    session = validator.get_session(session4)
    session.accessed_backends[-1].has_sensitive_data = True
    
    print("   (Response contained sensitive data)")
    
    print("\n2. Trying to access public GitHub after sensitive data...")
    allowed, error = validator.validate_backend_access(
        session4, "github-test", "create_issue",
        {"title": "Debug info", "body": "User data..."}
    )
    print_result(allowed, error)
    
    # Scenario 5: Response filtering
    print_header("Scenario 5: Response Content Filtering")
    
    session5 = "response-filter"
    
    print("1. GitHub response contains leaked API key...")
    response = {
        "issue": {
            "title": "Config issue",
            "body": "The API_KEY=sk-prod-12345 is exposed"
        }
    }
    
    allowed, error = validator.validate_response(
        session5, "github-test", response
    )
    print_result(allowed, error)
    
    # Show session summary
    print_header("Session Security Summary")
    
    for session_id in [session1, session2, session3, session4]:
        summary = validator.get_session_summary(session_id)
        print(f"\nSession: {session_id}")
        print(f"  Backends accessed: {', '.join(summary['accessed_backends'])}")
        print(f"  Total accesses: {summary['total_accesses']}")
        print(f"  Tainted: {'Yes' if summary['is_tainted'] else 'No'}")
        if summary['is_tainted']:
            print(f"  Taint source: {summary['taint_source']}")


if __name__ == "__main__":
    asyncio.run(main()) 