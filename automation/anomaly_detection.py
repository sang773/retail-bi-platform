import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv

load_dotenv()

def get_engine():
    return create_engine(
        f"postgresql://{os.getenv('RDS_USER')}:{os.getenv('RDS_PASSWORD')}"
        f"@{os.getenv('RDS_HOST')}/{os.getenv('RDS_DATABASE')}"
    )

def detect_revenue_anomalies():
    """Flag days where revenue is unusually high or low"""
    print("=== RUNNING ANOMALY DETECTION ===\n")
    
    engine = get_engine()
    
    df = pd.read_sql("""
        SELECT
            DATE(order_purchase_timestamp) AS date,
            COUNT(order_id) AS daily_orders,
            ROUND(SUM(gross_revenue)::numeric, 2) AS daily_revenue,
            ROUND(AVG(gross_revenue)::numeric, 2) AS avg_order_value
        FROM fact_orders
        WHERE order_purchase_timestamp IS NOT NULL
        GROUP BY DATE(order_purchase_timestamp)
        ORDER BY date
    """, engine)
    
    # Calculate 7-day rolling mean and std
    df['rolling_mean'] = df['daily_revenue'].rolling(window=7, min_periods=3).mean()
    df['rolling_std']  = df['daily_revenue'].rolling(window=7, min_periods=3).std()
    
    # Flag anomalies: more than 2 std deviations from rolling mean
    df['upper_bound'] = df['rolling_mean'] + 2 * df['rolling_std']
    df['lower_bound'] = df['rolling_mean'] - 2 * df['rolling_std']
    df['is_anomaly']  = (
        (df['daily_revenue'] > df['upper_bound']) |
        (df['daily_revenue'] < df['lower_bound'])
    )
    df['anomaly_type'] = None
    df.loc[df['daily_revenue'] > df['upper_bound'], 'anomaly_type'] = 'SPIKE ⬆️'
    df.loc[df['daily_revenue'] < df['lower_bound'], 'anomaly_type'] = 'DROP ⬇️'
    
    anomalies = df[df['is_anomaly'] == True].copy()
    
    print(f"Total days analyzed: {len(df):,}")
    print(f"Anomalies detected: {len(anomalies)}\n")
    
    if len(anomalies) > 0:
        print("ANOMALY REPORT:")
        print("-" * 60)
        for _, row in anomalies.iterrows():
            print(f"{row['anomaly_type']} {row['date']} | "
                  f"Revenue: ${row['daily_revenue']:,.2f} | "
                  f"Expected: ${row['rolling_mean']:,.2f} | "
                  f"Orders: {row['daily_orders']}")
    else:
        print("✅ No anomalies detected — revenue within normal range")
    
    print("\n=== ANOMALY DETECTION COMPLETE ===")
    return anomalies

def detect_order_volume_anomalies():
    """Flag days with unusually low or high order counts"""
    print("\n=== ORDER VOLUME ANOMALY CHECK ===\n")
    
    engine = get_engine()
    
    df = pd.read_sql("""
        SELECT
            DATE(order_purchase_timestamp) AS date,
            COUNT(order_id) AS daily_orders
        FROM fact_orders
        GROUP BY DATE(order_purchase_timestamp)
        ORDER BY date
    """, engine)
    
    df['rolling_mean'] = df['daily_orders'].rolling(window=7, min_periods=3).mean()
    df['rolling_std']  = df['daily_orders'].rolling(window=7, min_periods=3).std()
    df['is_anomaly']   = (
        (df['daily_orders'] > df['rolling_mean'] + 2 * df['rolling_std']) |
        (df['daily_orders'] < df['rolling_mean'] - 2 * df['rolling_std'])
    )
    
    anomalies = df[df['is_anomaly'] == True]
    print(f"Order volume anomalies: {len(anomalies)}")
    
    if len(anomalies) > 0:
        for _, row in anomalies.iterrows():
            direction = '⬆️ SPIKE' if row['daily_orders'] > row['rolling_mean'] else '⬇️ DROP'
            print(f"{direction} {row['date']} | "
                  f"Orders: {row['daily_orders']} | "
                  f"Expected: {row['rolling_mean']:.0f}")
    
    return anomalies

if __name__ == '__main__':
    revenue_anomalies = detect_revenue_anomalies()
    order_anomalies   = detect_order_volume_anomalies()
    
    total = len(revenue_anomalies) + len(order_anomalies)
    print(f"\n📊 SUMMARY: {total} total anomalies flagged")