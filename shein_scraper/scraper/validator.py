"""
Responsible for validating the extracted data.

This module uses the Pydantic model to validate the data and ensure it
conforms to the expected schema.
"""

import logging
from typing import Any, Dict, Optional

from pydantic import ValidationError

from models.product import Product

class Validator:
    """
    Validates extracted data against the Product model.
    """
    @staticmethod
    def validate(data: Dict[str, Any]) -> Optional[Product]:
        """
        Validates the extracted data and creates a Product object.

        Args:
            data: A dictionary of extracted data.

        Returns:
            A Product object if validation is successful, otherwise None.
        """
        if not data:
            logging.warning("Cannot validate empty data.")
            return None
            
        try:
            product = Product(**data)
            logging.info(f"Successfully validated data for product: {product.product_id}")
            return product
        except ValidationError as e:
            logging.error(f"Data validation failed: {e}")
            return None
