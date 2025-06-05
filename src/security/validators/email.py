"""Email address validator"""
from typing import List, Tuple
from .base import SensitiveDataValidator
import re
import logging
from email_validator import validate_email, EmailNotValidError


class EmailValidator(SensitiveDataValidator):
    """Validator for email addresses"""
    
    # Basic email regex to find potential emails
    EMAIL_REGEX = re.compile(
        r'\b[A-Za-z0-9][A-Za-z0-9._%+-]*@[A-Za-z0-9][A-Za-z0-9.-]*\.[A-Z|a-z]{2,}\b',
        re.IGNORECASE
    )
    
    def __init__(self, check_deliverability: bool = False):
        """
        Initialize email validator.
        
        Args:
            check_deliverability: Whether to check if the domain has MX records
        """
        super().__init__('email')
        self.check_deliverability = check_deliverability
    
    def find_matches(self, text: str) -> List[Tuple[str, int, int]]:
        """Find all email addresses in the text"""
        matches = []
        
        # First, use regex to find potential emails
        for match in self.EMAIL_REGEX.finditer(text):
            email_str = match.group(0)
            start = match.start()
            end = match.end()
            
            try:
                # Validate the email using email-validator
                validate_email(
                    email_str, 
                    check_deliverability=self.check_deliverability
                )
                matches.append((email_str, start, end))
            except EmailNotValidError:
                # Skip invalid emails
                continue
        
        return matches 