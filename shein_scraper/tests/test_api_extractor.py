from scraper.extractor import ApiProductExtractor


SAMPLE_API_RESPONSE = {
    "product_id": 123456,
    "goods_id": 123456,
    "goods_sn": "ABC123",
    "name": "Classic Oversized Hoodie",
    "sale_price": {"amount": 19.99, "currency": "USD"},
    "retail_price": {"amount": 39.99, "currency": "USD"},
    "discount": 50,
    "stock": 12,
    "goods_detail": {
        "goods_name": "Classic Oversized Hoodie",
        "goods_desc": "Comfortable everyday hoodie.",
        "images": [
            {"image_url": "https://img.shein.com/test1.jpg"},
            {"image_url": "https://img.shein.com/test2.jpg"},
        ],
        "sizes": ["S", "M", "L"],
        "colors": [
            {"name": "Black"},
            {"name": "White"},
        ],
        "rating": 4.6,
        "review_count": 120,
        "store": {
            "name": "SHEIN",
            "rating": 4.5,
            "sales_count": 950,
        },
        "return_policy": "30-day return policy",
    },
}


def test_api_product_extractor_returns_valid_product() -> None:
    product = ApiProductExtractor.extract(SAMPLE_API_RESPONSE)

    assert product is not None
    assert product.product_id == "123456"
    assert product.sku == "ABC123"
    assert product.name == "Classic Oversized Hoodie"
    assert product.price == 19.99
    assert product.currency == "USD"
    assert product.stock == 12
    assert product.description == "Comfortable everyday hoodie."
    assert len(product.images) == 2
    assert product.sizes == ["S", "M", "L"]
    assert product.color == "Black"
    assert product.rating == 4.6
    assert product.review_count == 120
    assert product.store_name == "SHEIN"
    assert product.store_rating == 4.5
    assert product.sales_count == 950
    assert product.return_policy == "30-day return policy"
