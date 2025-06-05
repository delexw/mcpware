"""Password exposure validator using zxcvbn and entropy analysis"""
from typing import List, Tuple
from .base import SensitiveDataValidator
import re
import math
import zxcvbn


class PasswordValidator(SensitiveDataValidator):
    """Validator for exposed passwords using strength and entropy analysis"""
    
    # Common password exposure patterns
    PASSWORD_PATTERNS = [
        # Key-value patterns with various separators
        re.compile(r'(?i)(?:password|passwd|pwd|pass|secret)\s*[:=]\s*[\'"]?([^\s\'"]+)[\'"]?'),
        
        # Environment variable format
        re.compile(r'(?i)(?:PASSWORD|PASSWD|PWD|PASS|SECRET)=([^\s\n]+)'),
        
        # JSON/YAML format
        re.compile(r'(?i)[\'"]?(?:password|passwd|pwd|pass|secret)[\'"]?\s*:\s*[\'"]([^\'"]+)[\'"]'),
        
        # Database connection strings - fixed to capture just password
        re.compile(r'(?i)(?:mysql|postgres|postgresql|mongodb|redis)://[^:]+:([^@]+)@'),
        
        # Basic auth in URLs - fixed to capture just password
        re.compile(r'(?i)https?://[^:]+:([^@]+)@'),
    ]
    
    # Common placeholder/test passwords to ignore
    PLACEHOLDER_PASSWORDS = {
        'xxx', '***', '...', 'null', 'none', 'undefined', 'empty',
        'test', 'demo', 'example', 'sample', 'placeholder',
        'changeme', 'password', 'pass', 'pwd', 'secret',
        '123', '1234', '12345', '123456', 'admin', 'root'
    }
    
    def __init__(self, min_password_length: int = 8, min_entropy: float = 40.0):
        """
        Initialize password validator.
        
        Args:
            min_password_length: Minimum length for a string to be considered a password
            min_entropy: Minimum entropy (bits) for a password to be considered suspicious
        """
        super().__init__('password')
        self.min_password_length = min_password_length
        self.min_entropy = min_entropy
    
    def _calculate_entropy(self, password: str) -> float:
        """Calculate entropy (bits per character) for a password"""
        charset = 0
        
        # Count character set size
        if any(c.islower() for c in password):
            charset += 26
        if any(c.isupper() for c in password):
            charset += 26
        if any(c.isdigit() for c in password):
            charset += 10
        if any(c in "!@#$%^&*()-=+[]{};;'\",.<>?/\\|" for c in password):
            charset += 32
            
        if charset == 0:
            return 0
            
        return len(password) * math.log2(charset)
    
    def _is_high_entropy(self, password: str, threshold: float = 40) -> bool:
        """Check if password has high entropy"""
        return self._calculate_entropy(password) >= threshold
    
    def _is_suspicious_password(self, password: str) -> bool:
        """
        Check if a password looks suspicious using multiple heuristics.
        Returns True if it's likely a real password that should be flagged.
        """
        # Too short or too long passwords are likely not real
        if len(password) < 8 or len(password) > 64:
            return False
            
        # Check if it's a common placeholder
        if password.lower() in self.PLACEHOLDER_PASSWORDS:
            return False
            
        # Check if it's just letters (too simple)
        if re.fullmatch(r'[a-zA-Z]+', password):
            return False
            
        # Use zxcvbn to check password strength
        result = zxcvbn.zxcvbn(password)
        
        # If zxcvbn gives it a score of 2 or higher, it's likely a real password
        # Score: 0 = very weak, 1 = weak, 2 = fair, 3 = good, 4 = very strong
        if result['score'] >= 2:
            return True
            
        # If it has high entropy, it's likely a real password
        if self._is_high_entropy(password, self.min_entropy):
            return True
            
        # If it looks like a real password pattern (mix of characters)
        has_lower = any(c.islower() for c in password)
        has_upper = any(c.isupper() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_special = any(c in "!@#$%^&*()-=+[]{};;'\",.<>?/\\|" for c in password)
        
        # Real passwords often have at least 2-3 of these character types
        char_types = sum([has_lower, has_upper, has_digit, has_special])
        if char_types >= 2 and len(password) >= self.min_password_length:
            return True
            
        return False
    
    def find_matches(self, text: str) -> List[Tuple[str, int, int]]:
        """Find all exposed passwords in the text"""
        matches = []
        seen_passwords = set()  # Avoid duplicates
        
        for pattern in self.PASSWORD_PATTERNS:
            for match in pattern.finditer(text):
                full_match = match.group(0)
                password = match.group(1) if match.lastindex else full_match
                
                # Skip if it looks like a variable reference
                if password.startswith('$') or password.startswith('%'):
                    continue
                
                # Check if this looks like a real password worth flagging
                if not self._is_suspicious_password(password):
                    continue
                
                # Add to matches if not seen before
                if password not in seen_passwords:
                    seen_passwords.add(password)
                    start = match.start()
                    end = match.end()
                    matches.append((full_match, start, end))
        
        return matches 