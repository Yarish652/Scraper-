"""
Responsible for extracting structured product data from the SHEIN JSON API payload.

This module intentionally avoids HTML selectors and instead maps the browser-captured
JSON response into the application's `Product` model.
"""

import logging
import re
from typing import Any

from models.product import Product
from scraper.validator import Validator

logger = logging.getLogger(__name__)


class ApiProductExtractor:
    """
    Extracts a validated `Product` object from the SHEIN product detail JSON payload.
    """

    @staticmethod
    def _safe_get(mapping: dict[str, Any] | None, key: str, default: Any = None) -> Any:
        if not isinstance(mapping, dict):
            return default
        return mapping.get(key, default)

    @staticmethod
    def _safe_nested_get(mapping: dict[str, Any] | None, *keys: str) -> Any:
        current: Any = mapping
        for key in keys:
            if not isinstance(current, dict):
                return None
            current = current.get(key)
        return current

    @staticmethod
    def _extract_first_image(images: Any) -> list[str]:
        if isinstance(images, list):
            results: list[str] = []
            for item in images:
                if isinstance(item, dict):
                    image_url = ApiProductExtractor._safe_get(item, "image_url") or ApiProductExtractor._safe_get(item, "url")
                    if image_url:
                        results.append(str(image_url))
                elif isinstance(item, str):
                    results.append(item)
            return results
        return []

    @staticmethod
    def _extract_colors(colors: Any) -> list[str]:
        if isinstance(colors, list):
            extracted: list[str] = []
            for item in colors:
                if isinstance(item, dict):
                    name = ApiProductExtractor._safe_get(item, "name") or ApiProductExtractor._safe_get(item, "color_name")
                    if name:
                        extracted.append(str(name))
                elif isinstance(item, str):
                    extracted.append(item)
            return extracted
        return []

    @staticmethod
    def _coerce_float(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return float(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return None
            try:
                return float(cleaned)
            except ValueError:
                match = re.search(r"-?\d+(?:\.\d+)?", cleaned)
                if match:
                    return float(match.group(0))
        return None

    @staticmethod
    def _coerce_int(value: Any) -> int | None:
        if value is None or isinstance(value, bool):
            return None
        if isinstance(value, (int, float)):
            return int(value)
        if isinstance(value, str):
            cleaned = value.strip().replace(",", "")
            if not cleaned:
                return None
            match = re.search(r"-?\d+", cleaned)
            if match:
                return int(match.group(0))
        return None

    @staticmethod
    def _extract_title(api_payload: dict[str, Any]) -> str | None:
        info_payload = ApiProductExtractor._safe_get(api_payload, "info") or {}
        product_info = ApiProductExtractor._safe_get(info_payload, "productInfo") or {}
        for key in ("goodsName", "goods_name", "goodsTitle", "title", "name", "product_name"):
            value = ApiProductExtractor._safe_get(product_info, key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        def _find_in_tree(obj: Any) -> str | None:
            if isinstance(obj, dict):
                for key in ("goodsName", "goods_name"):
                    value = obj.get(key)
                    if isinstance(value, str) and value.strip():
                        return value.strip()
                for nested in obj.values():
                    found = _find_in_tree(nested)
                    if found:
                        return found
            elif isinstance(obj, list):
                for item in obj:
                    found = _find_in_tree(item)
                    if found:
                        return found
            return None

        return _find_in_tree(info_payload) or ApiProductExtractor._safe_get(api_payload, "name")

    @staticmethod
    def _extract_sizes(api_payload: dict[str, Any]) -> list[str]:
        info_payload = ApiProductExtractor._safe_get(api_payload, "info") or {}
        sale_attr = ApiProductExtractor._safe_get(info_payload, "saleAttr") or {}
        multi_level_sale_attr = ApiProductExtractor._safe_get(sale_attr, "multiLevelSaleAttribute") or {}
        attr_groups = ApiProductExtractor._safe_get(multi_level_sale_attr, "skc_sale_attr")
        if not isinstance(attr_groups, list):
            goods_detail = ApiProductExtractor._safe_get(api_payload, "goods_detail") or {}
            return ApiProductExtractor._safe_get(goods_detail, "sizes") or []

        sizes: list[str] = []
        for group in attr_groups:
            if not isinstance(group, dict):
                continue
            attr_name = ApiProductExtractor._safe_get(group, "attr_name") or ApiProductExtractor._safe_get(group, "attr_name_en") or ""
            values = ApiProductExtractor._safe_get(group, "attr_value_list")
            if not isinstance(values, list):
                continue
            if "size" in str(attr_name).lower() or ApiProductExtractor._safe_get(group, "isSize") is True:
                for item in values:
                    if not isinstance(item, dict):
                        continue
                    value = ApiProductExtractor._safe_get(item, "attr_value_name") or ApiProductExtractor._safe_get(item, "attr_value_name_en") or ApiProductExtractor._safe_get(item, "name")
                    if isinstance(value, str) and value.strip():
                        sizes.append(value.strip())
        if sizes:
            return sizes

        goods_detail = ApiProductExtractor._safe_get(api_payload, "goods_detail") or {}
        return ApiProductExtractor._safe_get(goods_detail, "sizes") or []

    @staticmethod
    def _extract_images(api_payload: dict[str, Any]) -> list[str]:
        info_payload = ApiProductExtractor._safe_get(api_payload, "info") or {}
        sale_attr = ApiProductExtractor._safe_get(info_payload, "saleAttr") or {}
        multi_level_sale_attr = ApiProductExtractor._safe_get(sale_attr, "multiLevelSaleAttribute") or {}
        sku_list = ApiProductExtractor._safe_get(multi_level_sale_attr, "sku_list")
        if isinstance(sku_list, list):
            images: list[str] = []
            for sku in sku_list:
                if not isinstance(sku, dict):
                    continue
                sku_sale_attr = ApiProductExtractor._safe_get(sku, "sku_sale_attr")
                if not isinstance(sku_sale_attr, list):
                    continue
                for attr in sku_sale_attr:
                    if not isinstance(attr, dict):
                        continue
                    image_url = ApiProductExtractor._safe_get(attr, "attr_image")
                    if isinstance(image_url, str) and image_url.strip():
                        images.append(image_url.strip())
            if images:
                return images

        goods_detail = ApiProductExtractor._safe_get(api_payload, "goods_detail") or {}
        return ApiProductExtractor._extract_first_image(ApiProductExtractor._safe_get(goods_detail, "images"))

    @staticmethod
    def _extract_description(api_payload: dict[str, Any]) -> str | None:
        info_payload = ApiProductExtractor._safe_get(api_payload, "info") or {}
        product_info = ApiProductExtractor._safe_get(info_payload, "productInfo") or {}
        for key in ("goods_desc", "goodsDesc", "description", "desc"):
            value = ApiProductExtractor._safe_get(product_info, key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        goods_detail = ApiProductExtractor._safe_get(api_payload, "goods_detail") or {}
        description = ApiProductExtractor._safe_get(goods_detail, "goods_desc") or ApiProductExtractor._safe_get(api_payload, "description")
        if isinstance(description, str) and description.strip():
            return description.strip()
        return None

    @staticmethod
    def _extract_return_policy(api_payload: dict[str, Any]) -> str | None:
        info_payload = ApiProductExtractor._safe_get(api_payload, "info") or {}
        product_info = ApiProductExtractor._safe_get(info_payload, "productInfo") or {}
        for key in ("return_title", "return_policy", "returnPolicy"):
            value = ApiProductExtractor._safe_get(product_info, key)
            if isinstance(value, str) and value.strip():
                return value.strip()

        goods_detail = ApiProductExtractor._safe_get(api_payload, "goods_detail") or {}
        return_policy = ApiProductExtractor._safe_get(goods_detail, "return_policy")
        if isinstance(return_policy, str) and return_policy.strip():
            return return_policy.strip()
        return None

    @staticmethod
    def extract(api_payload: dict[str, Any], product_url: str | None = None) -> Product | None:
        """
        Turn the captured SHEIN API payload into a validated `Product` instance.

        Args:
            api_payload: The JSON dictionary returned by PlaywrightFetcher.
            product_url: The original product page URL used to reach the payload.

        Returns:
            A validated `Product` object, or `None` if the payload is insufficient.
        """
        if not isinstance(api_payload, dict):
            logger.warning("Cannot extract a product from a non-dictionary payload.")
            return None

        info_payload = ApiProductExtractor._safe_get(api_payload, "info") or {}
        product_info = ApiProductExtractor._safe_get(info_payload, "productInfo") or {}
        goods_detail = ApiProductExtractor._safe_get(api_payload, "goods_detail") or {}
        sale_price = ApiProductExtractor._safe_get(api_payload, "sale_price") or {}
        retail_price = ApiProductExtractor._safe_get(api_payload, "retail_price") or {}
        store = ApiProductExtractor._safe_get(goods_detail, "store") or {}

        sale_attr = ApiProductExtractor._safe_get(info_payload, "saleAttr") or {}
        multi_level_sale_attr = ApiProductExtractor._safe_get(sale_attr, "multiLevelSaleAttribute") or {}
        sku_list = ApiProductExtractor._safe_get(multi_level_sale_attr, "sku_list")
        first_sku: dict[str, Any] | None = None
        if isinstance(sku_list, list) and sku_list:
            first_sku = sku_list[0] if isinstance(sku_list[0], dict) else None

        # V1 intentionally uses the first SKU for price extraction.
        first_sku_sale_price = ApiProductExtractor._safe_nested_get(first_sku, "priceInfo", "salePrice") if first_sku else None
        first_sku_retail_price = ApiProductExtractor._safe_nested_get(first_sku, "priceInfo", "retailPrice") if first_sku else None

        product_id = ApiProductExtractor._safe_get(product_info, "goods_id") or ApiProductExtractor._safe_get(api_payload, "product_id") or ApiProductExtractor._safe_get(api_payload, "goods_id")
        sku = ApiProductExtractor._safe_get(product_info, "goods_sn") or ApiProductExtractor._safe_get(api_payload, "goods_sn")
        name = ApiProductExtractor._extract_title(api_payload) or ApiProductExtractor._safe_get(goods_detail, "goods_name")
        price_value = ApiProductExtractor._coerce_float(ApiProductExtractor._safe_nested_get(first_sku_sale_price, "amount"))
        if price_value is None:
            price_value = ApiProductExtractor._coerce_float(ApiProductExtractor._safe_get(sale_price, "amount"))
        retail_price_value = ApiProductExtractor._coerce_float(ApiProductExtractor._safe_nested_get(first_sku_retail_price, "amount"))
        if retail_price_value is None:
            retail_price_value = ApiProductExtractor._coerce_float(ApiProductExtractor._safe_get(retail_price, "amount"))
        currency = ApiProductExtractor._safe_get(first_sku_sale_price, "currency") or ApiProductExtractor._safe_get(first_sku_retail_price, "currency") or ApiProductExtractor._safe_get(sale_price, "currency") or ApiProductExtractor._safe_get(retail_price, "currency") or "USD"
        stock = ApiProductExtractor._safe_get(product_info, "stock") or ApiProductExtractor._safe_get(first_sku, "stock") or ApiProductExtractor._safe_get(api_payload, "stock")
        discount = ApiProductExtractor._safe_get(api_payload, "discount")
        description = ApiProductExtractor._extract_description(api_payload)
        images = ApiProductExtractor._extract_images(api_payload)
        sizes = ApiProductExtractor._extract_sizes(api_payload)
        colors = ApiProductExtractor._extract_colors(ApiProductExtractor._safe_get(goods_detail, "colors"))
        rating = ApiProductExtractor._coerce_float(ApiProductExtractor._safe_nested_get(info_payload, "comment", "comments_overview", "comment_rank_average"))
        if rating is None:
            rating = ApiProductExtractor._coerce_float(ApiProductExtractor._safe_get(goods_detail, "rating") or ApiProductExtractor._safe_get(api_payload, "rating"))
        review_count = ApiProductExtractor._coerce_int(ApiProductExtractor._safe_nested_get(info_payload, "comment", "comments_overview", "comment_num_show"))
        if review_count is None:
            review_count = ApiProductExtractor._coerce_int(ApiProductExtractor._safe_get(goods_detail, "review_count") or ApiProductExtractor._safe_get(api_payload, "review_count"))
        store_name = ApiProductExtractor._safe_get(store, "name")
        store_rating = ApiProductExtractor._safe_get(store, "rating")
        sales_count = ApiProductExtractor._safe_get(product_info, "last90DaysSoldNum") or ApiProductExtractor._safe_get(store, "sales_count")
        return_policy = ApiProductExtractor._extract_return_policy(api_payload)

        expected_fields = {
            "product_id": product_id,
            "sku": sku,
            "name": name,
            "price": price_value,
            "currency": currency,
            "stock": stock,
            "images": images,
            "sizes": sizes,
            "description": description,
            "rating": rating,
            "review_count": review_count,
            "store_name": store_name,
            "store_rating": store_rating,
            "sales_count": sales_count,
            "return_policy": return_policy,
        }
        for field_name, field_value in expected_fields.items():
            if field_value is None or field_value == [] or field_value == "":
                logger.warning("Missing expected field during extraction: %s", field_name)

        extracted_data: dict[str, Any] = {
            "name": str(name) if name is not None else "",
            "product_url": product_url or "",
            "product_id": str(product_id) if product_id is not None else "",
            "price": float(price_value) if price_value is not None else 0.0,
            "currency": str(currency) if currency is not None else "USD",
            "sku": str(sku) if sku is not None else "",
            "description": description,
            "images": images,
            "sizes": sizes,
            "color": colors[0] if colors else None,
            "rating": float(rating) if rating is not None else None,
            "review_count": int(review_count) if review_count is not None else None,
            "stock": ApiProductExtractor._coerce_int(stock) if stock is not None else None,
            "discount": float(discount) if discount is not None else None,
            "retail_price": float(retail_price_value) if retail_price_value is not None else None,
            "store_name": store_name,
            "store_rating": ApiProductExtractor._coerce_float(store_rating) if store_rating is not None else None,
            "sales_count": ApiProductExtractor._coerce_int(sales_count) if sales_count is not None else None,
            "return_policy": return_policy,
        }

        try:
            product = Validator.validate(extracted_data)
            logger.info("Successfully validated SHEIN product %s", extracted_data.get("product_id"))
            return product
        except Exception:
            logger.exception("Failed to validate extracted SHEIN product data.")
            return None
