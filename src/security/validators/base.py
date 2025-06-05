"""Base class for sensitive data validators"""
from abc import ABC, abstractmethod
from typing import List, Tuple, Optional
import re


class SensitiveDataValidator(ABC):
    """Abstract base class for sensitive data validators"""
    
    def __init__(self, name: str):
        """Initialize validator with a name"""
        self.name = name
    
    @abstractmethod
    def find_matches(self, text: str) -> List[Tuple[str, int, int]]:
        """
        Find all matches of sensitive data in the given text.
        
        Args:
            text: The text to search for sensitive data
            
        Returns:
            List of tuples containing (matched_text, start_position, end_position)
        """
        pass
    
    def contains_sensitive_data(self, text: str) -> bool:
        """
        Check if the text contains any sensitive data.
        
        Args:
            text: The text to check
            
        Returns:
            True if sensitive data is found, False otherwise
        """
        return len(self.find_matches(text)) > 0
    
    def mask_sensitive_data(self, text: str, mask_char: str = '*') -> str:
        """
        Mask sensitive data in the text.
        
        Args:
            text: The text containing sensitive data
            mask_char: Character to use for masking
            
        Returns:
            Text with sensitive data masked
        """
        matches = self.find_matches(text)
        if not matches:
            return text
        
        # Sort matches by start position in reverse order to avoid position shifts
        matches.sort(key=lambda x: x[1], reverse=True)
        
        result = text
        for matched_text, start, end in matches:
            # Keep first and last few characters visible
            if len(matched_text) > 4:
                masked = matched_text[:2] + mask_char * (len(matched_text) - 4) + matched_text[-2:]
            else:
                masked = mask_char * len(matched_text)
            result = result[:start] + masked + result[end:]
        
        return result
    
    def __str__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"
    
    def __repr__(self) -> str:
        return self.__str__() 