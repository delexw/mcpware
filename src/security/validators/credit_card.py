"""Credit card number validator"""
from typing import List, Tuple
from .base import SensitiveDataValidator
import re
import logging
from luhnchecker.luhn import Luhn


class CreditCardValidator(SensitiveDataValidator):
    """Validator for credit card numbers using LuhnChecker"""
    
    # Credit card patterns - flexible to handle various formats
    CARD_PATTERNS = [
        re.compile(r'\b(?:\d{4}[\s\-]?){3}\d{4}\b'),  # 16 digits with optional separators
        re.compile(r'\b\d{15}\b'),  # Amex - 15 digits
        re.compile(r'\b\d{13,19}\b'),  # Generic range for other cards
    ]
    
    def __init__(self):
        """Initialize credit card validator"""
        super().__init__('credit_card')
        self.checker = Luhn()
    
    def find_matches(self, text: str) -> List[Tuple[str, int, int]]:
        """Find all credit card numbers in the text"""
        matches = []
        seen_cards = set()
        
        for pattern in self.CARD_PATTERNS:
            for match in pattern.finditer(text):
                card_match = match.group(0)
                
                # Extract just the digits
                digits = re.sub(r'[\s\-]', '', card_match)
                
                # Skip if not the right length
                if len(digits) < 13 or len(digits) > 19:
                    continue
                
                # Validate using LuhnChecker
                try:
                    # Check if Luhn checksum is valid
                    if not self.checker.check_luhn(digits):
                        continue
                    
                    # Get card issuer to ensure it's a recognized card type
                    issuer = self.checker.credit_card_issuer(digits)
                    
                    # Skip if it's not a recognized card type
                    if issuer == "invalid card number":
                        continue
                    
                    # Skip test card numbers
                    if self._is_test_card(digits):
                        continue
                except Exception:
                    continue
                
                # Normalize for deduplication
                if digits in seen_cards:
                    continue
                
                seen_cards.add(digits)
                matches.append((card_match, match.start(), match.end()))
        
        return matches
    
    def _is_test_card(self, digits: str) -> bool:
        """Check if this is a known test card number"""
        test_cards = {
            '4111111111111111',  # Visa test
            '5555555555554444',  # Mastercard test
            '5105105105105100',  # Mastercard test
            '378282246310005',   # Amex test
            '371449635398431',   # Amex test
            '6011111111111117',  # Discover test
            '6011000990139424',  # Discover test
            '3530111333300000',  # JCB test
            '3566002020360505',  # JCB test
            '4242424242424242',  # Stripe test
            '4000056655665556',  # Stripe test
        }
        
        return digits in test_cards 