"""
Sensitive data detection security policy
Scans responses for sensitive data patterns and blocks leaks from public backends
"""
import json
import logging
from typing import Any, List, Tuple, Dict
from .base import SecurityPolicy, PolicyResult, ValidationContext
from .validators import (
    PhoneValidator,
    EmailValidator, 
    PasswordValidator,
    ApiKeyValidator,
    CreditCardValidator
)

logger = logging.getLogger(__name__)


class SensitiveDataPolicy(SecurityPolicy):
    """Detects and prevents sensitive data leaks using specialized validators"""
    
    def __init__(self, config: dict):
        """Initialize policy with validators"""
        super().__init__(config)
        
        # Initialize all validators
        self.validators = [
            PhoneValidator(),
            EmailValidator(),
            PasswordValidator(),
            ApiKeyValidator(),
            CreditCardValidator()
        ]
        
        # Create a mapping for quick lookup
        self.validator_map = {v.name: v for v in self.validators}
    
    def _is_enabled(self) -> bool:
        """Check if sensitive data leak prevention is enabled"""
        return self.config.get("prevent_sensitive_data_leak", True)
    
    def validate(self, context: ValidationContext) -> PolicyResult:
        """This policy only validates responses, not requests"""
        # Request validation always passes - this policy is for responses
        return PolicyResult(allowed=True)
    
    def validate_response(self, backend_name: str, backend_security_level: str, 
                         response: Any) -> Tuple[bool, List[str]]:
        """
        Validate response content for sensitive data
        
        Returns:
            Tuple of (has_sensitive_data, detected_patterns)
        """
        if not self.enabled:
            return False, []
        
        # Convert response to string for pattern matching
        response_str = json.dumps(response) if isinstance(response, dict) else str(response)
        
        # Check each validator
        detected_patterns = []
        detected_details: Dict[str, List[str]] = {}
        
        for validator in self.validators:
            if validator.contains_sensitive_data(response_str):
                detected_patterns.append(validator.name)
                
                # Optionally collect matched values for logging (masked)
                matches = validator.find_matches(response_str)
                if matches:
                    # Store first few masked examples
                    examples = []
                    for match_text, _, _ in matches[:3]:  # Limit to first 3 examples
                        masked = validator.mask_sensitive_data(match_text)
                        examples.append(masked)
                    detected_details[validator.name] = examples
        
        if detected_patterns and backend_security_level == "public":
            # Log with masked examples for debugging
            log_msg = f"Blocked sensitive data leak from {backend_name}: {detected_patterns}"
            if logger.isEnabledFor(logging.DEBUG) and detected_details:
                log_msg += f" Examples (masked): {detected_details}"
            logger.warning(log_msg)
        
        return bool(detected_patterns), detected_patterns
    
    def add_custom_validator(self, validator) -> None:
        """Add a custom validator to the policy"""
        self.validators.append(validator)
        self.validator_map[validator.name] = validator
    
    def remove_validator(self, name: str) -> bool:
        """Remove a validator by name"""
        if name in self.validator_map:
            validator = self.validator_map[name]
            self.validators.remove(validator)
            del self.validator_map[name]
            return True
        return False
    
    @property
    def name(self) -> str:
        return "SensitiveDataPolicy" 