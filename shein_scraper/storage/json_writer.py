"""
Handles writing data to a JSON file.
"""

import json
import logging
from pathlib import Path
from typing import List

from models.product import Product
from config.constants import OUTPUTS_DIR

class JsonWriter:
    """
    Writes product data to a JSON file.
    """
    def __init__(self, filename: str):
        """
        Initializes the JsonWriter.

        Args:
            filename: The name of the output file (without extension).
        """
        self.filepath = OUTPUTS_DIR / f"{filename}.json"
        self._data: List[dict] = []

    def write(self, product: Product):
        """
        Adds a product to the internal list to be written.

        Args:
            product: The Product object to write.
        """
        if product:
            self._data.append(product.model_dump())
            logging.debug(f"Added product {product.product_id} to JSON writer buffer.")

    def save(self):
        """
        Saves all buffered products to the JSON file.
        """
        try:
            with open(self.filepath, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=4, ensure_ascii=False)
            logging.info(f"Successfully saved {len(self._data)} products to {self.filepath}")
        except IOError as e:
            logging.error(f"Failed to write to JSON file {self.filepath}: {e}")
