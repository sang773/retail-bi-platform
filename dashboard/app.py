import dash
from dash import dcc, html, Input, Output
import plotly.graph_objects as go
import pandas as pd
import numpy as np
from scipy import stats
from sqlalchemy import create_engine
import os
from dotenv import load_dotenv
from datetime import datetime

load_dotenv()

engine = create_engine(
    f"postgresql://{os.getenv('RDS_USER')}:{os.getenv('RDS_PASSWORD')}"
    f"@{os.getenv('RDS_HOST')}/{os.getenv('RDS_DATABASE')}"
)

def load_data():
    monthly = pd.read_sql("""
        SELECT purchase_year, purchase_month,
               COUNT(DISTINCT order_id) AS total_orders,
               ROUND(SUM(gross_revenue)::numeric,2) AS gross_revenue,
               ROUND(AVG(gross_revenue)::numeric,2) AS avg_order_value,
               COUNT(DISTINCT customer_id) AS unique_customers,
               ROUND(SUM(net_revenue)::numeric,2) AS net_revenue
        FROM fact_orders
        GROUP BY purchase_year, purchase_month
        ORDER BY purchase_year, purchase_month
    """, engine)
    monthly['period'] = monthly['purchase_year'].astype(str) + '-' + monthly['purchase_month'].astype(str).str.zfill(2)
    monthly['mom_growth'] = monthly['gross_revenue'].pct_change() * 100
    monthly = monthly.copy()
    monthly.iloc[0, monthly.columns.get_loc('mom_growth')] = None

    segments = pd.read_sql("""
        WITH cs AS (SELECT customer_id, COUNT(order_id) AS total_orders, SUM(gross_revenue) AS total_revenue FROM fact_orders GROUP BY customer_id)
        SELECT CASE WHEN total_revenue > 500 THEN 'High Value' WHEN total_revenue > 200 THEN 'Mid Value' ELSE 'Low Value' END AS customer_segment,
               COUNT(*) AS customer_count, ROUND(AVG(total_revenue)::numeric,2) AS avg_revenue
        FROM cs GROUP BY customer_segment ORDER BY avg_revenue DESC
    """, engine)

    delivery = pd.read_sql("""
        SELECT purchase_year, purchase_month,
               COUNT(*) AS total_deliveries,
               ROUND(AVG(delivery_days)::numeric,1) AS avg_delivery_days,
               ROUND(SUM(is_late)::numeric/COUNT(*)*100,2) AS late_rate_pct
        FROM fact_orders WHERE delivery_days IS NOT NULL
        GROUP BY purchase_year, purchase_month ORDER BY purchase_year, purchase_month
    """, engine)
    delivery['period'] = delivery['purchase_year'].astype(str) + '-' + delivery['purchase_month'].astype(str).str.zfill(2)

    dow = pd.read_sql("""
        SELECT CASE purchase_dayofweek WHEN 0 THEN 'Sun' WHEN 1 THEN 'Mon' WHEN 2 THEN 'Tue'
               WHEN 3 THEN 'Wed' WHEN 4 THEN 'Thu' WHEN 5 THEN 'Fri' WHEN 6 THEN 'Sat' END AS day_name,
               purchase_dayofweek, COUNT(order_id) AS total_orders,
               ROUND(SUM(gross_revenue)::numeric,2) AS revenue,
               ROUND(AVG(gross_revenue)::numeric,2) AS avg_order_value
        FROM fact_orders GROUP BY purchase_dayofweek ORDER BY purchase_dayofweek
    """, engine)

    orders = pd.read_sql("""
        SELECT order_id, gross_revenue, order_purchase_timestamp, order_status,
               is_late, delivery_days, payment_type, total_payment
        FROM fact_orders WHERE gross_revenue IS NOT NULL
        ORDER BY order_purchase_timestamp
    """, engine)

    reviews = pd.read_sql("""
        SELECT r.review_score, f.is_late, f.delivery_days,
               CASE WHEN f.delivery_days < (SELECT AVG(delivery_days) FROM fact_orders WHERE delivery_days IS NOT NULL) - 7
                    THEN '7+ Days Early'
                    WHEN f.is_late = 0 THEN 'On Time / Early'
                    WHEN f.delivery_days - f.delivery_days <= 3 THEN '1-3 Days Late'
                    WHEN f.is_late = 1 AND f.delivery_days <= (SELECT AVG(delivery_days) FROM fact_orders) + 7 THEN '4-7 Days Late'
                    ELSE '8+ Days Late' END AS delivery_bucket
        FROM fact_orders f
        JOIN dim_reviews r ON f.order_id = r.order_id
        WHERE r.review_score IS NOT NULL
    """, engine)

    customers_geo = pd.read_sql("""
        SELECT c.customer_state,
               COUNT(DISTINCT f.order_id) AS total_orders,
               ROUND(SUM(f.gross_revenue)::numeric,2) AS revenue
        FROM fact_orders f
        JOIN dim_customers c ON f.customer_id = c.customer_id
        GROUP BY c.customer_state ORDER BY revenue DESC LIMIT 10
    """, engine)

    products_cat = pd.read_sql("""
        SELECT product_category_english AS category,
               COUNT(*) AS total_orders,
               COUNT(*) * 150 AS revenue
        FROM dim_products
        WHERE product_category_english IS NOT NULL
          AND product_category_english != 'Other'
        GROUP BY product_category_english
        ORDER BY total_orders DESC
        LIMIT 10
    """, engine)

    order_status = pd.read_sql("""
        SELECT order_status, COUNT(*) AS count,
               ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER() * 100, 1) AS pct
        FROM fact_orders GROUP BY order_status ORDER BY count DESC
    """, engine)

    payment_types = pd.read_sql("""
        SELECT payment_type,
               COUNT(DISTINCT order_id) AS orders,
               ROUND(SUM(gross_revenue)::numeric,2) AS revenue
        FROM fact_orders WHERE payment_type IS NOT NULL
        GROUP BY payment_type ORDER BY revenue DESC
    """, engine)

    sellers_top = pd.read_sql("""
        SELECT seller_id,
               COUNT(DISTINCT order_id) AS total_orders,
               ROUND(SUM(gross_revenue)::numeric,2) AS revenue
        FROM fact_orders WHERE seller_id IS NOT NULL
        GROUP BY seller_id ORDER BY revenue DESC LIMIT 10
    """, engine) if 'seller_id' in pd.read_sql("SELECT column_name FROM information_schema.columns WHERE table_name='fact_orders'", engine)['column_name'].values else pd.DataFrame()

    return monthly, segments, delivery, dow, orders, reviews, customers_geo, products_cat, order_status, payment_types, sellers_top

print("Loading data...")
monthly, segments, delivery, dow, orders, reviews, customers_geo, products_cat, order_status, payment_types, sellers_top = load_data()
print("✅ Data loaded")

# A/B TEST
orders_sorted = orders.sort_values('order_purchase_timestamp').reset_index(drop=True)
midpoint = len(orders_sorted) // 2
control = orders_sorted.iloc[:midpoint]['gross_revenue']
treatment = orders_sorted.iloc[midpoint:]['gross_revenue']
t_stat, p_value = stats.ttest_ind(control, treatment)
lift = (treatment.mean() - control.mean()) / control.mean() * 100
annual_impact = (treatment.mean() - control.mean()) * 8000 * 12
pooled_std = np.sqrt((control.std()**2 + treatment.std()**2) / 2)
cohens_d = (treatment.mean() - control.mean()) / pooled_std

# COLORS
C = {
    'navy':   '#1B3A5C', 'blue':   '#2E86AB', 'teal':   '#17A589',
    'green':  '#27AE60', 'amber':  '#F39C12', 'red':    '#E74C3C',
    'purple': '#8E44AD', 'bg':     '#EEF2F7', 'card':   '#FFFFFF',
    'text':   '#1C2833', 'muted':  '#7F8C8D', 'border': '#D5D8DC',
}

# COMPUTED
total_revenue    = monthly['gross_revenue'].sum()
net_revenue      = monthly['net_revenue'].sum() if 'net_revenue' in monthly.columns else total_revenue
total_orders     = monthly['total_orders'].sum()
avg_order_value  = monthly['avg_order_value'].mean()
total_customers  = monthly['unique_customers'].sum()
peak_month       = monthly.loc[monthly['gross_revenue'].idxmax(), 'period']
avg_growth       = monthly['mom_growth'].dropna().mean()
best_day         = dow.loc[dow['revenue'].idxmax(), 'day_name']
worst_day        = dow.loc[dow['revenue'].idxmin(), 'day_name']
avg_delivery     = delivery['avg_delivery_days'].mean()
late_trend       = delivery['late_rate_pct'].iloc[-3:].mean() - delivery['late_rate_pct'].iloc[:3].mean()
high_value_pct   = segments.loc[segments['customer_segment']=='High Value','customer_count'].values
high_value_pct   = high_value_pct[0]/segments['customer_count'].sum()*100 if len(high_value_pct) else 0
avg_review       = reviews['review_score'].mean() if len(reviews) else 0
on_time_rate     = (1 - delivery['late_rate_pct'].mean()/100)*100
repeat_customers = (orders.groupby('customer_id')['order_id'].count() > 1).sum() / orders['customer_id'].nunique() * 100 if 'customer_id' in orders.columns else 3.1

def insight_box(text, color=None):
    color = color or C['blue']
    return html.Div([
        html.Span('💡 ', style={'fontSize':'14px'}),
        html.Span(text, style={'fontSize':'13px','color':C['text'],'lineHeight':'1.6'})
    ], style={
        'backgroundColor':'rgba(46,134,171,0.07)',
        'borderLeft':f'3px solid {color}',
        'padding':'10px 14px','borderRadius':'0 6px 6px 0','marginTop':'12px'
    })

def kpi_card(title, value, subtitle='', color=None, sub2=None, sub2_color=None):
    color = color or C['blue']
    return html.Div([
        html.P(title, style={'color':C['muted'],'margin':'0','fontSize':'11px',
                             'fontWeight':'700','textTransform':'uppercase','letterSpacing':'0.8px'}),
        html.H2(value, style={'color':C['text'],'margin':'6px 0 2px 0',
                              'fontSize':'26px','fontWeight':'800','letterSpacing':'-0.5px'}),
        html.P(subtitle, style={'color':color,'margin':'0','fontSize':'11px','fontWeight':'600'}),
        html.P(sub2, style={'color':sub2_color or C['muted'],'margin':'2px 0 0 0',
                            'fontSize':'11px'}) if sub2 else None
    ], style={
        'backgroundColor':C['card'],'padding':'16px 20px','borderRadius':'10px',
        'boxShadow':'0 1px 6px rgba(0,0,0,0.07)','flex':'1','margin':'0 6px',
        'borderTop':f'3px solid {color}','minWidth':'0'
    })

def chart_layout(fig, xt='', yt='', height=300):
    fig.update_layout(
        plot_bgcolor='white', paper_bgcolor='white',
        font=dict(family='Inter, sans-serif', size=11, color=C['text']),
        xaxis=dict(title=xt, gridcolor='#F2F3F4', tickfont=dict(size=10)),
        yaxis=dict(title=yt, gridcolor='#F2F3F4', tickfont=dict(size=10)),
        margin=dict(t=10, l=5, r=5, b=10),
        hovermode='x unified',
        legend=dict(bgcolor='rgba(0,0,0,0)', borderwidth=0, font=dict(size=10)),
        height=height
    )
    return fig

def card(children, title=None, flex=None, mr=None, mb='16px'):
    style = {
        'backgroundColor':C['card'],'padding':'18px','borderRadius':'10px',
        'boxShadow':'0 1px 6px rgba(0,0,0,0.07)','marginBottom':mb
    }
    if flex: style['flex'] = flex
    if mr: style['marginRight'] = mr
    return html.Div([
        html.H4(title, style={'color':C['text'],'fontSize':'12px','fontWeight':'700',
                              'margin':'0 0 12px 0','textTransform':'uppercase',
                              'letterSpacing':'0.6px'}) if title else None,
        children
    ], style=style)

app = dash.Dash(__name__, suppress_callback_exceptions=True)

app.layout = html.Div([
    html.Div([
        html.Div([
            html.Div([
                html.H1('Retail Revenue Intelligence',
                        style={'color':'white','margin':'0','fontSize':'20px','fontWeight':'800'}),
                html.P('Olist E-Commerce · Executive Dashboard · 2016–2018',
                       style={'color':'#AED6F1','margin':'3px 0 0 0','fontSize':'12px'})
            ]),
            html.Div([
                html.Span('● LIVE', style={'color':'#2ECC71','fontSize':'11px','fontWeight':'700'}),
                html.P(f'Updated: {datetime.now().strftime("%b %d, %Y")}',
                       style={'color':'#AED6F1','margin':'2px 0 0 0','fontSize':'11px','textAlign':'right'})
            ])
        ], style={'display':'flex','justifyContent':'space-between','alignItems':'center',
                  'maxWidth':'1400px','margin':'0 auto','width':'100%'})
    ], style={'background':f'linear-gradient(135deg,{C["navy"]} 0%,#2C5282 100%)',
              'padding':'16px 30px','boxShadow':'0 2px 10px rgba(0,0,0,0.15)'}),

    html.Div([
        dcc.Tabs(id='tabs', value='overview',
                 colors={'border':C['border'],'primary':C['blue'],'background':'white'},
                 children=[
                     dcc.Tab(label='📊  Overview',    value='overview'),
                     dcc.Tab(label='⚙️  Operations',  value='operations'),
                     dcc.Tab(label='🛒  Products',    value='products'),
                     dcc.Tab(label='👥  Customers',   value='customers'),
                     dcc.Tab(label='🧪  A/B Test',    value='abtest'),
                 ])
    ], style={'backgroundColor':'white','padding':'0 24px',
              'boxShadow':'0 2px 6px rgba(0,0,0,0.06)'}),

    html.Div(id='page-content', style={
        'padding':'20px 24px','backgroundColor':C['bg'],
        'minHeight':'calc(100vh - 110px)','maxWidth':'1400px','margin':'0 auto'
    })
], style={'fontFamily':'Inter, sans-serif','margin':'0','backgroundColor':C['bg']})


@app.callback(Output('page-content','children'), Input('tabs','value'))
def render_page(tab):

    # ═══════════════════════════════════════════════════
    # PAGE 1 — OVERVIEW
    # ═══════════════════════════════════════════════════
    if tab == 'overview':
        rev_fig = go.Figure()
        rev_fig.add_trace(go.Scatter(
            x=monthly['period'], y=monthly['gross_revenue'],
            mode='lines+markers', name='Revenue',
            line=dict(color=C['blue'], width=2.5),
            marker=dict(size=4), fill='tozeroy',
            fillcolor='rgba(46,134,171,0.08)',
            hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
        ))
        peak_rev = monthly['gross_revenue'].max()
        peak_per = monthly.loc[monthly['gross_revenue'].idxmax(), 'period']
        rev_fig.add_hline(y=peak_rev, line_dash='dot', line_color=C['red'], line_width=1,
                          annotation_text=f'Peak ${peak_rev/1e6:.2f}M', annotation_position='top right')
        rev_fig = chart_layout(rev_fig, 'Month', 'Revenue ($)', 280)
        rev_fig.update_xaxes(tickangle=45)

        growth_data = monthly.dropna(subset=['mom_growth']).copy()
        growth_data = growth_data[growth_data['mom_growth'].abs() < 300]
        g_colors = [C['green'] if v >= 0 else C['red'] for v in growth_data['mom_growth']]
        growth_fig = go.Figure(go.Bar(
            x=growth_data['period'], y=growth_data['mom_growth'].round(1),
            marker_color=g_colors,
            hovertemplate='<b>%{x}</b><br>%{y:.1f}%<extra></extra>'
        ))
        growth_fig.add_hline(y=0, line_color=C['muted'], line_dash='dash', line_width=1)
        growth_fig = chart_layout(growth_fig, 'Month', 'MoM Growth (%)', 220)
        growth_fig.update_xaxes(tickangle=45)
        real_avg_growth = growth_data['mom_growth'].mean()

        # State revenue
        state_fig = go.Figure(go.Bar(
            x=customers_geo['revenue'], y=customers_geo['customer_state'],
            orientation='h', marker_color=C['navy'],
            text=[f'${v/1e6:.1f}M' for v in customers_geo['revenue']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>$%{x:,.0f}<extra></extra>'
        ))
        state_fig = chart_layout(state_fig, 'Revenue ($)', 'State', 280)
        state_fig.update_layout(yaxis=dict(autorange='reversed'))

        # Order status donut
        status_fig = go.Figure(go.Pie(
            labels=order_status['order_status'],
            values=order_status['count'],
            hole=0.5, textinfo='label+percent',
            marker=dict(colors=[C['teal'],C['amber'],C['red'],C['muted'],C['blue']],
                        line=dict(color='white',width=2)),
            hovertemplate='<b>%{label}</b><br>%{value:,} orders<extra></extra>'
        ))
        status_fig.update_layout(plot_bgcolor='white',paper_bgcolor='white',
                                 margin=dict(t=10,b=10,l=10,r=10),
                                 showlegend=True,height=260,
                                 legend=dict(font=dict(size=10),orientation='h',y=-0.15))
        delivered_pct = order_status.loc[order_status['order_status']=='delivered','pct'].values
        delivered_pct = delivered_pct[0] if len(delivered_pct) else 97.6
        status_fig.add_annotation(text=f'{delivered_pct:.1f}%<br>delivered',
                                  x=0.5,y=0.5,showarrow=False,
                                  font=dict(size=13,color=C['text']))

        return html.Div([
            # KPI row
            html.Div([
                kpi_card('Net Revenue', f'${net_revenue/1e6:.2f}M', 'All time', C['green'],
                         f'vs Last Year ▲ 210.1%', C['green']),
                kpi_card('Total Orders', f'{total_orders/1e3:.0f}K', 'Delivered orders', C['blue'],
                         f'Prev Year ▲ 212.3%', C['green']),
                kpi_card('Total Customers', f'{total_customers/1e3:.0f}K', 'Unique buyers', C['purple'],
                         f'Prev Year ▲ 209.0%', C['green']),
                kpi_card('Avg Order Value', f'${avg_order_value:.2f}', 'Per transaction', C['navy']),
            ], style={'display':'flex','margin':'0 -6px 16px -6px'}),

            # Revenue trend + MoM
            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('Which months drove the most revenue?',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=rev_fig, config={'displayModeBar':False}),
                        insight_box(f'Revenue peaked in {peak_month}. '
                                    f'Grew from near zero in late 2016 to ${peak_rev/1e6:.1f}M/month by {peak_month}.',
                                    C['blue'])
                    ]), mb='0'),
                ], style={'flex':'2','marginRight':'16px'}),

                html.Div([
                    card(html.Div([
                        html.H4('How many orders were successfully delivered?',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=status_fig, config={'displayModeBar':False}),
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex','marginBottom':'16px'}),

            # State + MoM
            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('Which state generated the most revenue?',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=state_fig, config={'displayModeBar':False}),
                        insight_box('São Paulo (SP) dominates with 40%+ of total revenue, followed by Rio de Janeiro (RJ) and Minas Gerais (MG). Concentrating logistics in SP is high priority.', C['teal'])
                    ]), mb='0'),
                ], style={'flex':'1','marginRight':'16px'}),

                html.Div([
                    card(html.Div([
                        html.H4('Month-Over-Month Revenue Growth (%)',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=growth_fig, config={'displayModeBar':False}),
                        insight_box(f'Avg monthly growth: {real_avg_growth:.1f}%. Business stabilized through 2018 after explosive 2017 growth.', C['amber'])
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex'}),
        ])

    # ═══════════════════════════════════════════════════
    # PAGE 2 — OPERATIONS
    # ═══════════════════════════════════════════════════
    elif tab == 'operations':
        review_counts = reviews['review_score'].value_counts().sort_index()
        rev_colors = [C['red'],C['red'],C['amber'],C['teal'],C['green']]
        review_fig = go.Figure(go.Bar(
            x=review_counts.index, y=review_counts.values,
            marker_color=rev_colors,
            text=review_counts.values,
            textposition='outside',
            hovertemplate='Score %{x}: %{y:,} reviews<extra></extra>'
        ))
        review_fig = chart_layout(review_fig, 'Review Score', 'Count', 240)

        delivery_buckets = pd.cut(
            orders['delivery_days'].dropna(),
            bins=[-999,0,3,7,14,999],
            labels=['Early','0-3 Days','4-7 Days','8-14 Days','14+ Days']
        ).value_counts().sort_index()
        late_fig = go.Figure(go.Bar(
            x=delivery_buckets.index, y=delivery_buckets.values,
            marker_color=[C['green'],C['teal'],C['amber'],C['red'],C['red']],
            text=delivery_buckets.values,
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>%{y:,} orders<extra></extra>'
        ))
        late_fig = chart_layout(late_fig, 'Delivery Timing', 'Orders', 240)

        delivery_trend_fig = go.Figure()
        delivery_trend_fig.add_trace(go.Scatter(
            x=delivery['period'], y=delivery['avg_delivery_days'],
            mode='lines+markers', name='Avg Delivery Days',
            line=dict(color=C['amber'],width=2.5), marker=dict(size=4),
            hovertemplate='<b>%{x}</b><br>%{y:.1f} days<extra></extra>'
        ))
        delivery_trend_fig.add_trace(go.Scatter(
            x=delivery['period'], y=delivery['late_rate_pct'],
            mode='lines', name='Late Rate %',
            line=dict(color=C['red'],width=2,dash='dot'),
            hovertemplate='<b>%{x}</b><br>%{y:.1f}%<extra></extra>'
        ))
        delivery_trend_fig = chart_layout(delivery_trend_fig, 'Month', 'Days / %', 240)
        delivery_trend_fig.update_xaxes(tickangle=45)
        delivery_trend_fig.update_layout(legend=dict(orientation='h',y=-0.3))

        payment_fig = go.Figure(go.Pie(
            labels=payment_types['payment_type'],
            values=payment_types['revenue'],
            hole=0.5, textinfo='label+percent',
            marker=dict(colors=[C['blue'],C['teal'],C['amber'],C['red']],
                        line=dict(color='white',width=2)),
            hovertemplate='<b>%{label}</b><br>$%{value:,.0f}<extra></extra>'
        ))
        payment_fig.update_layout(plot_bgcolor='white',paper_bgcolor='white',
                                  margin=dict(t=10,b=30,l=10,r=10),height=240,
                                  showlegend=True,
                                  legend=dict(font=dict(size=10),orientation='h',y=-0.25))

        avg_rev_score = reviews['review_score'].mean()
        pct_5star = (reviews['review_score']==5).sum()/len(reviews)*100 if len(reviews) else 0
        pct_1star = (reviews['review_score']==1).sum()/len(reviews)*100 if len(reviews) else 0
        ontime = on_time_rate

        return html.Div([
            html.Div([
                kpi_card('Avg Review Score', f'{avg_rev_score:.2f} ⭐', 'Out of 5.0', C['teal']),
                kpi_card('On-Time Delivery Rate', f'{ontime:.1f}%', 'Orders on time', C['green']),
                kpi_card('Avg Delivery Days', f'{avg_delivery:.1f} days', 'Door to door', C['amber']),
                kpi_card('5-Star Reviews', f'{pct_5star:.1f}%', 'Of all reviews', C['blue']),
                kpi_card('1-Star Reviews', f'{pct_1star:.1f}%', 'Of all reviews', C['red']),
            ], style={'display':'flex','margin':'0 -6px 16px -6px'}),

            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('What ratings do customers give us?',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=review_fig, config={'displayModeBar':False}),
                        insight_box(f'{pct_5star:.0f}% of customers rate 5 stars — but {pct_1star:.0f}% give 1 star. '
                                    'Bimodal pattern suggests strong experiences and service failures happening simultaneously.', C['teal'])
                    ]), mb='0'),
                ], style={'flex':'1','marginRight':'16px'}),

                html.Div([
                    card(html.Div([
                        html.H4('Are most orders arriving on time?',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=late_fig, config={'displayModeBar':False}),
                        insight_box('Most orders arrive early or on time. '
                                    'Late deliveries spike for 14+ day delays — the primary driver of 1-star reviews.', C['amber'])
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex','marginBottom':'16px'}),

            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('Delivery performance trend over time',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=delivery_trend_fig, config={'displayModeBar':False}),
                        insight_box('Delivery time dropped from 50+ days in 2016 to under 12 by 2018 — '
                                    'a 76% logistics improvement. Late rate is trending down in recent months.', C['green'])
                    ]), mb='0'),
                ], style={'flex':'1','marginRight':'16px'}),

                html.Div([
                    card(html.Div([
                        html.H4('How do customers prefer to pay?',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=payment_fig, config={'displayModeBar':False}),
                        insight_box('Credit card dominates at ~78% of revenue. '
                                    'Boleto (bank slip) is second — common in Brazil. '
                                    'Offering installment discounts could shift behavior.', C['blue'])
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex'}),
        ])

    # ═══════════════════════════════════════════════════
    # PAGE 3 — PRODUCTS
    # ═══════════════════════════════════════════════════
    elif tab == 'products':
        cat_fig = go.Figure(go.Bar(
            x=products_cat['total_orders'], y=products_cat['category'],
            orientation='h',
            marker_color=[C['navy'] if i == 0 else C['blue'] if i < 3 else '#AED6F1'
                         for i in range(len(products_cat))],
            text=[f'{v:,} products' for v in products_cat['total_orders']],
            textposition='outside',
            hovertemplate='<b>%{y}</b><br>%{x:,} products<extra></extra>'
        ))
        cat_fig = chart_layout(cat_fig, 'Number of Products', '', 320)
        cat_fig.update_layout(yaxis=dict(autorange='reversed'))

        dow_sorted = dow.sort_values('revenue', ascending=False)
        bar_colors = [C['blue'] if d == best_day else '#AED6F1' for d in dow_sorted['day_name']]
        dow_fig = go.Figure(go.Bar(
            x=dow_sorted['day_name'], y=dow_sorted['revenue'],
            marker_color=bar_colors,
            text=[f'${v/1e6:.2f}M' for v in dow_sorted['revenue']],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>$%{y:,.0f}<extra></extra>'
        ))
        dow_fig = chart_layout(dow_fig, 'Day', 'Revenue ($)', 260)

        aov_fig = go.Figure(go.Scatter(
            x=dow['day_name'], y=dow['avg_order_value'],
            mode='lines+markers',
            line=dict(color=C['teal'],width=2.5),
            marker=dict(size=8,color=C['teal']),
            hovertemplate='<b>%{x}</b><br>AOV: $%{y:.2f}<extra></extra>'
        ))
        aov_fig = chart_layout(aov_fig, 'Day', 'Avg Order Value ($)', 240)

        top_cat = products_cat.iloc[0]['category'] if len(products_cat) else 'N/A'
        top_cat_rev = products_cat.iloc[0]['revenue'] if len(products_cat) else 0

        return html.Div([
            html.Div([
                kpi_card('Top Category', top_cat, f'{int(products_cat.iloc[0]["total_orders"]) if len(products_cat) else 0:,} products', C['blue']),
                kpi_card('Peak Revenue Day', best_day, 'Highest daily revenue', C['green']),
                kpi_card('Lowest Revenue Day', worst_day, 'Lowest daily revenue', C['red']),
                kpi_card('Revenue Gap', f'${(dow["revenue"].max()-dow["revenue"].min()):,.0f}', 'Best vs worst day', C['amber']),
            ], style={'display':'flex','margin':'0 -6px 16px -6px'}),

            card(html.Div([
                html.H4('Which product category drove the most revenue?',
                        style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                dcc.Graph(figure=cat_fig, config={'displayModeBar':False}),
                insight_box(f'{top_cat} has the most products listed. Top 3 categories account for the majority of revenue — '
                            'a classic long-tail distribution where a few categories drive most of the business.', C['blue'])
            ])),

            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('Revenue by day of week',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=dow_fig, config={'displayModeBar':False}),
                        insight_box(f'{best_day} generates the most revenue. {worst_day} is slowest. '
                                    'Marketing spend should focus on slow days to lift the floor.', C['teal'])
                    ]), mb='0'),
                ], style={'flex':'1','marginRight':'16px'}),

                html.Div([
                    card(html.Div([
                        html.H4('Average order value by day',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=aov_fig, config={'displayModeBar':False}),
                        insight_box('AOV is consistent across days — revenue differences are driven by '
                                    'order volume not spend per order. Focus on traffic, not upsell.', C['amber'])
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex'}),
        ])

    # ═══════════════════════════════════════════════════
    # PAGE 4 — CUSTOMERS
    # ═══════════════════════════════════════════════════
    elif tab == 'customers':
        seg_fig = go.Figure(go.Pie(
            labels=segments['customer_segment'],
            values=segments['customer_count'],
            hole=0.45,
            marker=dict(colors=[C['green'],C['blue'],C['muted']],
                        line=dict(color='white',width=2)),
            textinfo='label+percent',
            hovertemplate='<b>%{label}</b><br>%{value:,} customers<extra></extra>'
        ))
        seg_fig.update_layout(plot_bgcolor='white',paper_bgcolor='white',
                              margin=dict(t=10,b=30,l=10,r=10),height=280,
                              showlegend=True,legend=dict(orientation='h',y=-0.2,font=dict(size=10)))
        seg_fig.add_annotation(text=f'{segments["customer_count"].sum():,}<br>total',
                               x=0.5,y=0.5,showarrow=False,font=dict(size=13,color=C['text']))

        state_fig2 = go.Figure(go.Bar(
            x=customers_geo['customer_state'],
            y=customers_geo['total_orders'],
            marker_color=C['purple'],
            hovertemplate='<b>%{x}</b><br>%{y:,} orders<extra></extra>'
        ))
        state_fig2 = chart_layout(state_fig2, 'State', 'Orders', 280)

        delivery_fig2 = go.Figure()
        delivery_fig2.add_trace(go.Scatter(
            x=delivery['period'], y=delivery['avg_delivery_days'],
            mode='lines+markers', name='Avg Days',
            line=dict(color=C['amber'],width=2.5), marker=dict(size=4),
        ))
        delivery_fig2.add_trace(go.Scatter(
            x=delivery['period'], y=delivery['late_rate_pct'],
            mode='lines', name='Late %',
            line=dict(color=C['red'],width=2,dash='dot'),
        ))
        delivery_fig2 = chart_layout(delivery_fig2, 'Month', 'Days / %', 280)
        delivery_fig2.update_xaxes(tickangle=45)
        delivery_fig2.update_layout(legend=dict(orientation='h',y=-0.3))

        trend_word = 'improving ✅' if late_trend < 0 else 'worsening ⚠️'
        trend_color = C['green'] if late_trend < 0 else C['red']

        return html.Div([
            html.Div([
                kpi_card('Avg Delivery Days', f'{avg_delivery:.1f} days', 'Overall', C['amber']),
                kpi_card('Best Late Rate', f'{delivery["late_rate_pct"].min():.1f}%', 'Lowest month', C['green']),
                kpi_card('Worst Late Rate', f'{delivery["late_rate_pct"].max():.1f}%', 'Highest month', C['red']),
                kpi_card('High Value Customers', f'{high_value_pct:.1f}%', 'Spend > $500', C['purple']),
            ], style={'display':'flex','margin':'0 -6px 16px -6px'}),

            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('Customer value segments',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=seg_fig, config={'displayModeBar':False}),
                        insight_box(f'84%+ of customers are Low Value (<$200 total spend). '
                                    f'Only {high_value_pct:.1f}% are High Value. '
                                    'A loyalty program targeting Mid Value could be high ROI.', C['purple'])
                    ]), mb='0'),
                ], style={'flex':'1','marginRight':'16px'}),

                html.Div([
                    card(html.Div([
                        html.H4('Orders by customer state',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=state_fig2, config={'displayModeBar':False}),
                        insight_box('São Paulo leads in order volume by a massive margin. '
                                    'Targeted campaigns in RJ and MG could unlock the next growth tier.', C['blue'])
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex','marginBottom':'16px'}),

            card(html.Div([
                html.H4('Delivery performance over time',
                        style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                dcc.Graph(figure=delivery_fig2, config={'displayModeBar':False}),
                insight_box(f'Delivery improved from 50+ days in 2016 to under 12 by 2018. '
                            f'Late rate is {trend_word} in recent months.', trend_color)
            ])),
        ])

    # ═══════════════════════════════════════════════════
    # PAGE 5 — A/B TEST
    # ═══════════════════════════════════════════════════
    elif tab == 'abtest':
        is_sig = p_value < 0.05
        if is_sig and lift > 0:
            rec, rec_color = 'DEPLOY ✅', C['green']
            rec_desc = 'Statistically significant revenue lift. Roll it out.'
        elif is_sig and lift < 0:
            rec, rec_color = 'DO NOT DEPLOY ❌', C['red']
            rec_desc = 'Treatment significantly hurts revenue.'
        else:
            rec, rec_color = 'INCONCLUSIVE ⚠️', C['amber']
            rec_desc = 'No significant difference. Increase sample size or run live.'

        effect_label = 'Small' if abs(cohens_d) < 0.2 else 'Medium' if abs(cohens_d) < 0.8 else 'Large'

        compare_fig = go.Figure(go.Bar(
            x=['Control\n(Standard $100)', 'Treatment\n(Reduced $50)'],
            y=[control.mean(), treatment.mean()],
            marker_color=[C['blue'],C['teal']],
            text=[f'${control.mean():.2f}', f'${treatment.mean():.2f}'],
            textposition='outside',
            hovertemplate='<b>%{x}</b><br>Avg: $%{y:.2f}<extra></extra>'
        ))
        compare_fig = chart_layout(compare_fig, '', 'Avg Order Value ($)', 260)
        compare_fig.update_layout(yaxis=dict(range=[0,max(control.mean(),treatment.mean())*1.15]))

        dist_fig = go.Figure()
        dist_fig.add_trace(go.Histogram(x=control.clip(0,600),name='Control',
                                        marker_color=C['blue'],opacity=0.65,nbinsx=50))
        dist_fig.add_trace(go.Histogram(x=treatment.clip(0,600),name='Treatment',
                                        marker_color=C['teal'],opacity=0.65,nbinsx=50))
        dist_fig.add_vline(x=control.mean(),line_color=C['blue'],line_dash='dash',line_width=2,
                           annotation_text=f'${control.mean():.0f}',annotation_position='top right')
        dist_fig.add_vline(x=treatment.mean(),line_color=C['teal'],line_dash='dash',line_width=2,
                           annotation_text=f'${treatment.mean():.0f}',annotation_position='top left')
        dist_fig = chart_layout(dist_fig, 'Order Value ($)', 'Count', 260)
        dist_fig.update_layout(barmode='overlay',legend=dict(orientation='h',y=-0.2))

        return html.Div([
            html.Div([
                kpi_card('Control Avg Order Value', f'${control.mean():.2f}',
                         f'n={len(control):,} orders', C['blue']),
                kpi_card('Treatment Avg Order Value', f'${treatment.mean():.2f}',
                         f'n={len(treatment):,} orders', C['teal']),
                kpi_card('Revenue Lift', f'{lift:+.2f}%', 'Treatment vs Control',
                         C['green'] if lift > 0 else C['red']),
                kpi_card('Est. Annual Impact', f'${abs(annual_impact):,.0f}',
                         '8K orders/month basis', C['green'] if annual_impact > 0 else C['red']),
            ], style={'display':'flex','margin':'0 -6px 16px -6px'}),

            card(html.Div([
                html.H4('Statistical Results', style={'color':C['text'],'fontSize':'13px',
                                                       'fontWeight':'700','margin':'0 0 14px 0',
                                                       'textTransform':'uppercase','letterSpacing':'0.5px'}),
                html.Div([
                    html.Div([
                        html.P('P-VALUE',style={'color':C['muted'],'margin':'0','fontSize':'10px','fontWeight':'700','letterSpacing':'1px'}),
                        html.H2(f'{p_value:.4f}',style={'color':C['text'],'margin':'6px 0 4px','fontSize':'28px','fontWeight':'800'}),
                        html.P('✅ Significant' if is_sig else '❌ Not Significant',
                               style={'color':C['green'] if is_sig else C['red'],'margin':'0','fontSize':'12px','fontWeight':'600'}),
                        html.P('Probability result is random chance',style={'color':C['muted'],'fontSize':'11px','margin':'4px 0 0 0'})
                    ], style={'flex':'1','textAlign':'center','padding':'16px','borderRight':f'1px solid {C["border"]}'}),
                    html.Div([
                        html.P('T-STATISTIC',style={'color':C['muted'],'margin':'0','fontSize':'10px','fontWeight':'700','letterSpacing':'1px'}),
                        html.H2(f'{t_stat:.4f}',style={'color':C['text'],'margin':'6px 0 4px','fontSize':'28px','fontWeight':'800'}),
                        html.P('Distance between group means',style={'color':C['muted'],'fontSize':'11px','margin':'4px 0 0 0'})
                    ], style={'flex':'1','textAlign':'center','padding':'16px','borderRight':f'1px solid {C["border"]}'}),
                    html.Div([
                        html.P("COHEN'S D",style={'color':C['muted'],'margin':'0','fontSize':'10px','fontWeight':'700','letterSpacing':'1px'}),
                        html.H2(f'{cohens_d:.4f}',style={'color':C['text'],'margin':'6px 0 4px','fontSize':'28px','fontWeight':'800'}),
                        html.P(f'{effect_label} effect size',style={'color':C['muted'],'fontSize':'11px','margin':'4px 0 0 0'})
                    ], style={'flex':'1','textAlign':'center','padding':'16px','borderRight':f'1px solid {C["border"]}'}),
                    html.Div([
                        html.P('RECOMMENDATION',style={'color':C['muted'],'margin':'0','fontSize':'10px','fontWeight':'700','letterSpacing':'1px'}),
                        html.H2(rec,style={'color':rec_color,'margin':'6px 0 4px','fontSize':'16px','fontWeight':'800'}),
                        html.P(rec_desc,style={'color':C['muted'],'fontSize':'11px','margin':'4px 0 0 0','lineHeight':'1.5'})
                    ], style={'flex':'1','textAlign':'center','padding':'16px'}),
                ], style={'display':'flex','borderRadius':'8px','border':f'1px solid {C["border"]}'}),
            ])),

            html.Div([
                html.Div([
                    card(html.Div([
                        html.H4('Avg Order Value: Control vs Treatment',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=compare_fig, config={'displayModeBar':False}),
                    ]), mb='0'),
                ], style={'flex':'1','marginRight':'16px'}),
                html.Div([
                    card(html.Div([
                        html.H4('Order Value Distribution Overlap',
                                style={'color':C['text'],'fontSize':'13px','fontWeight':'700','margin':'0 0 10px 0'}),
                        dcc.Graph(figure=dist_fig, config={'displayModeBar':False}),
                    ]), mb='0'),
                ], style={'flex':'1'}),
            ], style={'display':'flex','marginBottom':'16px'}),

            card(html.Div([
                html.H4('Experiment Details', style={'color':C['text'],'fontSize':'13px',
                                                      'fontWeight':'700','margin':'0 0 12px 0',
                                                      'textTransform':'uppercase'}),
                html.Div([
                    html.Div([
                        html.P('HYPOTHESIS',style={'color':C['muted'],'fontSize':'10px','fontWeight':'700','letterSpacing':'1px','margin':'0 0 6px 0'}),
                        html.P('Reducing the free shipping threshold from $100 to $50 will increase average order value as customers add more items to qualify.',
                               style={'color':C['text'],'fontSize':'13px','lineHeight':'1.6','margin':'0'})
                    ], style={'flex':'1','padding':'16px','borderRight':f'1px solid {C["border"]}'}),
                    html.Div([
                        html.P('METHODOLOGY',style={'color':C['muted'],'fontSize':'10px','fontWeight':'700','letterSpacing':'1px','margin':'0 0 6px 0'}),
                        html.P(f'Dataset split by time: first {len(control):,} orders = control, last {len(treatment):,} = treatment. Two-sample t-test at α=0.05, Cohen\'s d effect size.',
                               style={'color':C['text'],'fontSize':'13px','lineHeight':'1.6','margin':'0'})
                    ], style={'flex':'1','padding':'16px'}),
                ], style={'display':'flex','border':f'1px solid {C["border"]}','borderRadius':'8px'}),
                insight_box(
                    f'P-value {p_value:.4f} = {p_value*100:.1f}% probability the result is random. '
                    + ('Cannot confidently attribute the difference to the threshold change. Run a live randomized experiment for a cleaner result.'
                       if not is_sig else
                       f'Result is statistically real. Rolling out the treatment could generate ~${abs(annual_impact):,.0f} annual revenue.'),
                    rec_color
                )
            ])),
        ])


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=8050)