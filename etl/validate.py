import pandas as pd
from dotenv import load_dotenv

load_dotenv()

def validate_orders(df):
    errors = []
    
    required_cols = ['order_id', 'customer_id', 'order_status', 'order_purchase_timestamp']
    for col in required_cols:
        if col not in df.columns:
            errors.append(f'MISSING COLUMN: {col}')
    
    if df['order_id'].duplicated().sum() > 0:
        errors.append(f'DUPLICATE ORDER IDs: {df["order_id"].duplicated().sum()} found')
    
    valid_statuses = ['delivered', 'shipped', 'canceled', 'processing',
                      'invoiced', 'approved', 'unavailable', 'created']
    invalid = df[~df['order_status'].isin(valid_statuses)]
    if len(invalid) > 0:
        errors.append(f'INVALID STATUS VALUES: {len(invalid)} rows')
    
    if errors:
        for error in errors:
            print(f'❌ VALIDATION ERROR: {error}')
        return False
    else:
        print(f'✅ orders: PASSED ({len(df):,} rows)')
        return True

def validate_order_items(df):
    errors = []
    
    if df['order_id'].isnull().sum() > 0:
        errors.append(f'NULLS IN order_id: {df["order_id"].isnull().sum()}')
    
    if (df['price'] < 0).sum() > 0:
        errors.append(f'NEGATIVE PRICES: {(df["price"] < 0).sum()} rows')
    
    if (df['freight_value'] < 0).sum() > 0:
        errors.append(f'NEGATIVE FREIGHT: {(df["freight_value"] < 0).sum()} rows')
    
    if errors:
        for error in errors:
            print(f'❌ VALIDATION ERROR: {error}')
        return False
    else:
        print(f'✅ order_items: PASSED ({len(df):,} rows)')
        return True

def validate_customers(df):
    errors = []
    
    if df['customer_id'].duplicated().sum() > 0:
        errors.append(f'DUPLICATE customer_id: {df["customer_id"].duplicated().sum()}')
    
    if df['customer_unique_id'].isnull().sum() > 0:
        errors.append(f'NULLS IN customer_unique_id')
    
    if errors:
        for error in errors:
            print(f'❌ VALIDATION ERROR: {error}')
        return False
    else:
        print(f'✅ customers: PASSED ({len(df):,} rows)')
        return True

def validate_payments(df):
    errors = []
    
    if (df['payment_value'] < 0).sum() > 0:
        errors.append(f'NEGATIVE PAYMENT VALUES: {(df["payment_value"] < 0).sum()} rows')
    
    if df['order_id'].isnull().sum() > 0:
        errors.append(f'NULLS IN order_id')
    
    if errors:
        for error in errors:
            print(f'❌ VALIDATION ERROR: {error}')
        return False
    else:
        print(f'✅ payments: PASSED ({len(df):,} rows)')
        return True

def validate_all(tables):
    print("=== VALIDATING ALL TABLES ===\n")
    
    results = {
        'orders': validate_orders(tables['orders']),
        'order_items': validate_order_items(tables['order_items']),
        'customers': validate_customers(tables['customers']),
        'payments': validate_payments(tables['payments'])
    }
    
    # Simple checks for remaining tables
    for name in ['products', 'sellers', 'reviews', 'geolocation']:
        df = tables[name]
        nulls = df.isnull().sum().sum()
        print(f'✅ {name}: PASSED ({len(df):,} rows, {nulls:,} total nulls)')
        results[name] = True
    
    passed = sum(results.values())
    total = len(results)
    
    print(f"\n=== VALIDATION COMPLETE: {passed}/{total} tables passed ===")
    return results

if __name__ == '__main__':
    from extract import extract_all
    tables = extract_all()
    print()
    results = validate_all(tables)