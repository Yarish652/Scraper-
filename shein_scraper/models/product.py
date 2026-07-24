"""
Pydantic model for a product.

This module defines the data structure and validation for a scraped product.
"""

from typing import List, Optional

from pydantic import BaseModel, Field


class Product(BaseModel):
    """
    Represents a single product scraped from SHEIN.
    """

    name: str = Field(..., description="The name of the product.")
    product_url: str = Field(..., description="The URL of the product page.")
    product_id: str = Field(..., description="The unique identifier for the product.")
    price: float = Field(..., description="The sale price of the product.", gt=0)
    currency: str = Field(..., description="The currency of the price (e.g., USD).")
    sku: str = Field(..., description="The stock keeping unit.")

    description: Optional[str] = Field(None, description="The product description.")
    images: List[str] = Field(default_factory=list, description="A list of product image URLs.")
    sizes: List[str] = Field(default_factory=list, description="Available sizes for the product.")
    color: Optional[str] = Field(None, description="The color of the product.")
    rating: Optional[float] = Field(None, description="The average product rating.", ge=0, le=5)
    review_count: Optional[int] = Field(None, description="The number of reviews.", ge=0)
    stock: Optional[int] = Field(None, description="Available stock count.", ge=0)
    discount: Optional[float] = Field(None, description="Discount percentage.", ge=0)
    retail_price: Optional[float] = Field(None, description="The retail price before discount.", ge=0)
    store_name: Optional[str] = Field(None, description="The store brand or seller name.")
    store_rating: Optional[float] = Field(None, description="The store rating.", ge=0, le=5)
    sales_count: Optional[int] = Field(None, description="The number of units sold.", ge=0)
    return_policy: Optional[str] = Field(None, description="The return policy text.")
