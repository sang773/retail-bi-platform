import pandas as pd
import numpy as np
from dotenv import load_dotenv

load_dotenv()

# ── CATEGORY TRANSLATION ──────────────────────────────────────────
CATEGORY_MAP = {
    'cama_mesa_banho': 'Bed & Bath',
    'beleza_saude': 'Beauty & Health',
    'esporte_lazer': 'Sports & Leisure',
    'moveis_decoracao': 'Furniture & Decor',
    'informatica_acessorios': 'Computers & Accessories',
    'utilidades_domesticas': 'Home Utilities',
    'relogios_presentes': 'Watches & Gifts',
    'telefonia': 'Phones',
    'ferramentas_jardim': 'Garden & Tools',
    'automotivo': 'Automotive',
    'brinquedos': 'Toys',
    'cool_stuff': 'Cool Stuff',
    'eletronicos': 'Electronics',
    'livros_interesse_geral': 'Books',
    'construcao_ferramentas_seguranca': 'Construction & Safety',
    'fashion_bolsas_e_acessorios': 'Fashion Bags',
    'malas_acessorios': 'Luggage',
    'musica': 'Music',
    'papelaria': 'Stationery',
    'electrodomesticos': 'Appliances'
}

# ── TRANSFORM ORDERS ─────────────────────────────────────────────
def transform_orders(df):
    print("Transforming orders...")
    
    # Convert all date columns from string to datetime
    date_cols = [
        'order_purchase_timestamp',
        'order_approved_at',
        'order_delivered_carrier_date',
        'order_delivered_customer_date',
        'order_estimated_delivery_date'
    ]
    for col in date_cols:
        df[col] = pd.to_datetime(df[col], errors='coerce')
    
    # Calculate how many days delivery took
    df['delivery_days'] = (
        df['order_delivered_customer_date'] -
        df['order_purchase_timestamp']
    ).dt.days
    
    # Flag late deliveries (delivered after estimated date)
    df['is_late'] = (
        df['order_delivered_customer_date'] >
        df['order_estimated_delivery_date']
    ).astype(int)
    
    # Extract time dimensions for analysis
    df['purchase_year'] = df['order_purchase_timestamp'].dt.year
    df['purchase_month'] = df['order_purchase_timestamp'].dt.month
    df['purchase_quarter'] = df['order_purchase_timestamp'].dt.quarter
    df['purchase_dayofweek'] = df['order_purchase_timestamp'].dt.dayofweek
    df['purchase_hour'] = df['order_purchase_timestamp'].dt.hour
    
    print(f"✅ Orders transformed: {len(df):,} total rows")
    print(f"   Late deliveries: {df['is_late'].sum():,}")
    print(f"   Avg delivery days: {df['delivery_days'].mean():.1f}")
    return df

# ── TRANSFORM PRODUCTS ───────────────────────────────────────────
def transform_products(df):
    print("\nTransforming products...")
    
    # Translate Portuguese categories to English
    df['product_category_english'] = df['product_category_name'].map(CATEGORY_MAP)
    df['product_category_english'].fillna('Other', inplace=True)
    
    # Fill missing product dimensions with median
    dim_cols = [
        'product_weight_g',
        'product_length_cm',
        'product_height_cm',
        'product_width_cm'
    ]
    for col in dim_cols:
        median_val = df[col].median()
        df[col].fillna(median_val, inplace=True)
    
    # Fill missing name length with 0
    df['product_name_lenght'].fillna(0, inplace=True)
    df['product_description_lenght'].fillna(0, inplace=True)
    df['product_photos_qty'].fillna(0, inplace=True)
    
    print(f"✅ Products transformed: {len(df):,} rows")
    print(f"   Categories mapped: {df['product_category_english'].nunique()}")
    return df

# ── TRANSFORM CUSTOMERS ──────────────────────────────────────────
def transform_customers(df):
    print("\nTransforming customers...")
    
    # Standardize state codes to uppercase
    df['customer_state'] = df['customer_state'].str.upper().str.strip()
    df['customer_city'] = df['customer_city'].str.title().str.strip()
    
    print(f"✅ Customers transformed: {len(df):,} rows")
    print(f"   States covered: {df['customer_state'].nunique()}")
    return df

# ── TRANSFORM GEOLOCATION ────────────────────────────────────────
def transform_geolocation(df):
    print("\nTransforming geolocation...")
    
    # Remove duplicate zip codes — keep first occurrence
    before = len(df)
    df = df.drop_duplicates(subset=['geolocation_zip_code_prefix'])
    after = len(df)
    
    print(f"✅ Geolocation transformed: {after:,} rows")
    print(f"   Duplicates removed: {before - after:,}")
    return df

# ── CREATE FACT TABLE ────────────────────────────────────────────
def create_fact_orders(orders, order_items, payments):
    print("\nBuilding fact_orders table...")
    
    # Aggregate payments per order
    payment_agg = payments.groupby('order_id').agg(
        total_payment=('payment_value', 'sum'),
        payment_installments=('payment_installments', 'max'),
        payment_type=('payment_type', lambda x: x.mode()[0])
    ).reset_index()
    
    # Aggregate items per order
    items_agg = order_items.groupby('order_id').agg(
        item_count=('order_item_id', 'count'),
        total_freight=('freight_value', 'sum'),
        total_price=('price', 'sum'),
        unique_products=('product_id', 'nunique'),
        seller_id=('seller_id', 'first') #added new line
    ).reset_index()
    
    # Join orders + payments + items
    fact = orders.merge(payment_agg, on='order_id', how='left')
    fact = fact.merge(items_agg, on='order_id', how='left')
    
    # Calculate revenue metrics
    fact['gross_revenue'] = fact['total_price']
    fact['net_revenue'] = fact['total_payment'] - fact['total_freight']
    fact['avg_item_value'] = fact['total_price'] / fact['item_count']
    
    # Keep only delivered orders for revenue analysis
    fact_delivered = fact[fact['order_status'] == 'delivered'].copy()
    
    print(f"✅ Fact table created: {len(fact_delivered):,} delivered orders")
    print(f"   Total gross revenue: ${fact_delivered['gross_revenue'].sum():,.2f}")
    print(f"   Avg order value: ${fact_delivered['gross_revenue'].mean():.2f}")
    return fact_delivered

# ── RUN ALL TRANSFORMS ───────────────────────────────────────────
def transform_all(tables):
    print("=== TRANSFORMING ALL TABLES ===\n")
    
    orders = transform_orders(tables['orders'])
    products = transform_products(tables['products'])
    customers = transform_customers(tables['customers'])
    geolocation = transform_geolocation(tables['geolocation'])
    
    fact_orders = create_fact_orders(
        orders,
        tables['order_items'],
        tables['payments']
    )
    
    transformed = {
        'fact_orders': fact_orders,
        'dim_customers': customers,
        'dim_products': products,
        'dim_sellers': tables['sellers'],
        'dim_reviews': tables['reviews'],
        'dim_geolocation': geolocation
    }
    
    print(f"\n=== TRANSFORMATION COMPLETE: {len(transformed)} tables ready ===")
    return transformed

if __name__ == '__main__':
    from extract import extract_all
    from validate import validate_all
    
    tables = extract_all()
    print()
    validate_all(tables)
    print()
    transformed = transform_all(tables)
    
    print("\nFinal table shapes:")
    for name, df in transformed.items():
        print(f"  {name}: {df.shape[0]:,} rows, {df.shape[1]} columns")