"""Phone number validator using phonenumbers library"""
from typing import List, Tuple
from .base import SensitiveDataValidator
import logging
import phonenumbers
from phonenumbers import PhoneNumberMatcher


class PhoneValidator(SensitiveDataValidator):
    """Validator for phone numbers using Google's libphonenumber"""
    
    def __init__(self):
        """Initialize phone validator"""
        super().__init__('phone')
    
    def find_matches(self, text: str) -> List[Tuple[str, int, int]]:
        """Find all phone numbers in the text"""
        matches = []
        seen_numbers = set()  # To avoid duplicates
        
        # Try to find phone numbers without specifying region (None)
        # This allows phonenumbers to detect numbers with country codes
        # and make best guesses for local numbers
        try:
            for match in PhoneNumberMatcher(text, None):
                # Check context to avoid false positives
                start_pos = match.start
                
                # Skip if this looks like it's part of an API key or similar
                context_start = max(0, start_pos - 20)
                context = text[context_start:start_pos].lower()
                if any(keyword in context for keyword in ['key', 'token', 'secret', 'id', 'hash']):
                    continue
                
                number = match.number
                
                # Simple check: is it valid or at least possible?
                is_valid = phonenumbers.is_valid_number(number)
                is_possible = phonenumbers.is_possible_number(number)
                
                # If it's either valid or possible, consider it a phone number
                if is_valid or is_possible:
                    # Create a normalized key to check for duplicates
                    try:
                        number_key = phonenumbers.format_number(number, phonenumbers.PhoneNumberFormat.E164)
                    except Exception:
                        # If we can't format to E164, use the raw string
                        number_key = match.raw_string
                    
                    if number_key not in seen_numbers:
                        seen_numbers.add(number_key)
                        matches.append((match.raw_string, match.start, match.end))
                        
        except Exception as e:
            logging.debug(f"Error processing phone numbers: {e}")
        
        return matches 