"""
工具函数模块
"""
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta

def calculate_growth(current_value, previous_value):
    """计算增长率"""
    if previous_value == 0:
        return 0 if current_value == 0 else 100
    return ((current_value - previous_value) / previous_value) * 100

def format_number(num):
    """格式化大数字"""
    if num >= 1000000:
        return f"{num/1000000:.1f}M"
    elif num >= 1000:
        return f"{num/1000:.1f}K"
    else:
        return str(int(num))

def create_metric_card_html(title, value, change=None, change_label="vs 上期"):
    """创建指标卡片 HTML"""
    change_html = ""
    if change is not None:
        color = "green" if change >= 0 else "red"
        arrow = "↑" if change >= 0 else "↓"
        change_html = f'<div style="color: {color}; font-size: 14px;">{arrow} {abs(change):.1f}% {change_label}</div>'

    return f"""
    <div style="background-color: #f0f2f6; padding: 20px; border-radius: 10px; text-align: center;">
        <div style="color: #666; font-size: 14px; margin-bottom: 5px;">{title}</div>
        <div style="font-size: 32px; font-weight: bold; margin-bottom: 5px;">{value}</div>
        {change_html}
    </div>
    """

def create_trend_chart(df, x_col, y_col, title, color='blue'):
    """创建趋势折线图"""
    fig = go.Figure()

    fig.add_trace(go.Scatter(
        x=df[x_col],
        y=df[y_col],
        mode='lines+markers',
        name=title,
        line=dict(color=color, width=2),
        marker=dict(size=6)
    ))

    fig.update_layout(
        title=title,
        xaxis_title=x_col,
        yaxis_title=y_col,
        hovermode='x unified',
        template='plotly_white',
        height=400
    )

    return fig

def create_bar_chart(df, x_col, y_col, title, color='lightblue', top_n=20):
    """创建条形图"""
    df_top = df.nlargest(top_n, y_col)

    fig = go.Figure(data=[
        go.Bar(
            x=df_top[y_col],
            y=df_top[x_col],
            orientation='h',
            marker=dict(color=color)
        )
    ])

    fig.update_layout(
        title=title,
        xaxis_title=y_col,
        yaxis_title=x_col,
        height=600,
        template='plotly_white',
        yaxis={'categoryorder': 'total ascending'}
    )

    return fig

def export_to_excel(df, filename='gsc_export.xlsx'):
    """导出数据到 Excel"""
    from io import BytesIO

    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, index=False, sheet_name='GSC Data')

    return output.getvalue()

def get_date_ranges(days=30):
    """获取日期范围"""
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=days)
    return start_date.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')
