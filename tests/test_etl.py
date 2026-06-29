import pytest
import pandas as pd
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'etl'))

from validate import validate_orders, validate_order_items, validate_customers, validate_payments

# ── ORDERS TESTS ─────────────────────────────────────────

def test_validate_orders_passes_clean_data():
    clean_df = pd.DataFrame({
        'order_id': ['1', '2', '3'],
        'customer_id': ['a', 'b', 'c'],
        'order_status': ['delivered', 'shipped', 'canceled'],
        'order_purchase_timestamp': ['2023-01-01', '2023-01-02', '2023-01-03']
    })
    assert validate_orders(clean_df) == True

def test_validate_orders_fails_on_duplicates():
    dup_df = pd.DataFrame({
        'order_id': ['1', '1', '3'],
        'customer_id': ['a', 'b', 'c'],
        'order_status': ['delivered', 'shipped', 'canceled'],
        'order_purchase_timestamp': ['2023-01-01', '2023-01-02', '2023-01-03']
    })
    assert validate_orders(dup_df) == False

def test_validate_orders_fails_on_invalid_status():
    bad_df = pd.DataFrame({
        'order_id': ['1', '2', '3'],
        'customer_id': ['a', 'b', 'c'],
        'order_status': ['delivered', 'INVALID_STATUS', 'canceled'],
        'order_purchase_timestamp': ['2023-01-01', '2023-01-02', '2023-01-03']
    })
    assert validate_orders(bad_df) == False

def test_validate_orders_fails_on_missing_column():
    missing_df = pd.DataFrame({
        'order_id': ['1', '2'],
        'customer_id': ['a', 'b'],
        'order_status': ['delivered', 'shipped']
        # missing order_purchase_timestamp
    })
    assert validate_orders(missing_df) == False

# ── ORDER ITEMS TESTS ─────────────────────────────────────

def test_validate_order_items_passes_clean_data():
    clean_df = pd.DataFrame({
        'order_id': ['1', '2', '3'],
        'price': [100.0, 50.0, 75.0],
        'freight_value': [10.0, 5.0, 8.0]
    })
    assert validate_order_items(clean_df) == True

def test_validate_order_items_fails_on_negative_price():
    bad_df = pd.DataFrame({
        'order_id': ['1', '2'],
        'price': [-10.0, 50.0],
        'freight_value': [5.0, 5.0]
    })
    assert validate_order_items(bad_df) == False

def test_validate_order_items_fails_on_negative_freight():
    bad_df = pd.DataFrame({
        'order_id': ['1', '2'],
        'price': [100.0, 50.0],
        'freight_value': [-5.0, 5.0]
    })
    assert validate_order_items(bad_df) == False

# ── CUSTOMERS TESTS ───────────────────────────────────────

def test_validate_customers_passes_clean_data():
    clean_df = pd.DataFrame({
        'customer_id': ['a', 'b', 'c'],
        'customer_unique_id': ['x', 'y', 'z']
    })
    assert validate_customers(clean_df) == True

def test_validate_customers_fails_on_duplicate_id():
    dup_df = pd.DataFrame({
        'customer_id': ['a', 'a', 'c'],
        'customer_unique_id': ['x', 'y', 'z']
    })
    assert validate_customers(dup_df) == False

# ── PAYMENTS TESTS ────────────────────────────────────────

def test_validate_payments_passes_clean_data():
    clean_df = pd.DataFrame({
        'order_id': ['1', '2', '3'],
        'payment_value': [100.0, 50.0, 75.0]
    })
    assert validate_payments(clean_df) == True

def test_validate_payments_fails_on_negative_value():
    bad_df = pd.DataFrame({
        'order_id': ['1', '2'],
        'payment_value': [-10.0, 50.0]
    })
    assert validate_payments(bad_df) == False