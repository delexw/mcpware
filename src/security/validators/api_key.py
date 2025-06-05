"""API key validator for various services"""
from typing import List, Tuple, Dict
from .base import SensitiveDataValidator
import re


class ApiKeyValidator(SensitiveDataValidator):
    """Validator for API keys from various services"""
    
    # API key patterns for different services
    API_KEY_PATTERNS: Dict[str, re.Pattern] = {
        # Generic API key patterns - reduced minimum length to catch more cases
        'generic': re.compile(r'(?i)(?:api[_-]?key|apikey|api[_-]?token|access[_-]?token)\s*[:=]\s*[\'"]?([a-zA-Z0-9_\-]{10,})[\'"]?'),
        
        # Service-specific patterns
        'aws_access_key': re.compile(r'(?i)(?:aws[_-]?access[_-]?key[_-]?id|AKIA)[^\s]*[:=]?\s*([A-Z0-9]{20})'),
        'aws_secret_key': re.compile(r'(?i)aws[_-]?secret[_-]?access[_-]?key\s*[:=]\s*[\'"]?([a-zA-Z0-9/+=]{40})[\'"]?'),
        
        # Generic sk_ pattern for various services
        'generic_sk': re.compile(r'\bsk[-_][a-zA-Z0-9_\-]{8,}\b'),
        
        # GitHub tokens
        'github_pat': re.compile(r'ghp_[a-zA-Z0-9]{36}'),
        'github_oauth': re.compile(r'gho_[a-zA-Z0-9]{36}'),
        'github_app': re.compile(r'github_pat_[a-zA-Z0-9]{22}_[a-zA-Z0-9]{59}'),
        
        # Slack tokens
        'slack_token': re.compile(r'xox[baprs]-[0-9]{10,13}-[0-9]{10,13}-[a-zA-Z0-9]{24,34}'),
        
        # Stripe
        'stripe_live': re.compile(r'sk_live_[a-zA-Z0-9]{24,}'),
        'stripe_test': re.compile(r'sk_test_[a-zA-Z0-9]{24,}'),
        
        # SendGrid
        'sendgrid': re.compile(r'SG\.[a-zA-Z0-9_\-]{22}\.[a-zA-Z0-9_\-]{43}'),
        
        # Twilio
        'twilio': re.compile(r'SK[a-f0-9]{32}'),
        
        # Google API key
        'google_api': re.compile(r'AIza[0-9A-Za-z_\-]{35}'),
        
        # Bearer tokens
        'bearer': re.compile(r'(?i)bearer\s+([a-zA-Z0-9_\-\.]{20,})'),
    }
    
    def __init__(self, service_patterns: Dict[str, re.Pattern] = None):
        """
        Initialize API key validator.
        
        Args:
            service_patterns: Optional custom patterns to use instead of defaults
        """
        super().__init__('api_key')
        self.patterns = service_patterns or self.API_KEY_PATTERNS
    
    def find_matches(self, text: str) -> List[Tuple[str, int, int]]:
        """Find all API keys in the text"""
        matches = []
        seen_keys = set()
        
        for service_name, pattern in self.patterns.items():
            for match in pattern.finditer(text):
                key = match.group(0)
                
                # Skip if already seen
                if key in seen_keys:
                    continue
                
                # Skip common false positives
                if self._is_false_positive(key, service_name):
                    continue
                
                seen_keys.add(key)
                matches.append((key, match.start(), match.end()))
        
        return matches
    
    def _is_false_positive(self, key: str, service_name: str) -> bool:
        """Check if a potential key is likely a false positive"""
        # Skip example/documentation keys
        if 'example' in key.lower() or 'sample' in key.lower():
            return True
        
        # Skip placeholder values
        if key in ['xxxxxxxxxxxxxxxxxxxx', 'your-api-key-here', 'YOUR_API_KEY']:
            return True
        
        # Skip if all same character
        if len(set(key.replace('-', '').replace('_', ''))) <= 2:
            return True
        
        return False 