"""
Google Search Console SEO 关键词看板
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

from gsc_api import GSCClient
from utils import (
    format_number, create_metric_card_html, create_trend_chart,
    create_bar_chart, export_to_excel, calculate_growth, get_date_ranges
)

# 页面配置
st.set_page_config(
    page_title="GSC SEO 关键词看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 36px;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 30px;
    }
    .metric-container {
        display: flex;
        justify-content: space-around;
        margin: 20px 0;
    }
    .stAlert {
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# 初始化 session state
if 'gsc_client' not in st.session_state:
    st.session_state.gsc_client = None
if 'sites' not in st.session_state:
    st.session_state.sites = []
if 'keyword_data' not in st.session_state:
    st.session_state.keyword_data = None
if 'comparison_data' not in st.session_state:
    st.session_state.comparison_data = None

def initialize_client():
    """初始化 GSC 客户端"""
    try:
        if not os.path.exists('credentials.json'):
            st.error("❌ 找不到 credentials.json 文件")
            st.info("请参考 API配置指南.md 配置 Google Search Console API")
            return False

        with st.spinner('正在连接 Google Search Console...'):
            st.session_state.gsc_client = GSCClient()
            st.session_state.sites = st.session_state.gsc_client.get_sites()

        if not st.session_state.sites:
            st.warning("⚠️ 未找到有权限访问的网站")
            return False

        st.success("✅ 连接成功！")
        return True

    except FileNotFoundError as e:
        st.error(f"❌ 文件错误: {e}")
        return False
    except Exception as e:
        st.error(f"❌ 连接失败: {e}")
        return False

def load_keyword_data(site_url, days, device_type, country, row_limit):
    """加载关键词数据"""
    with st.spinner('正在获取数据...'):
        df = st.session_state.gsc_client.get_keyword_data(
            site_url=site_url,
            days=days,
            row_limit=row_limit,
            device_type=device_type if device_type != "全部" else None,
            country=country if country != "全部" else None
        )

        if df.empty:
            st.warning("⚠️ 未找到数据")
            return None

        st.session_state.keyword_data = df
        return df

def load_comparison_data(site_url, days, device_type, country, row_limit):
    """加载对比期数据"""
    end_date = datetime.now().date() - timedelta(days=days)
    start_date = end_date - timedelta(days=days)

    with st.spinner('正在获取对比期数据...'):
        df = st.session_state.gsc_client.query_data(
            site_url=site_url,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            dimensions=['query'],
            row_limit=row_limit,
            device_type=device_type if device_type != "全部" else None,
            country=country if country != "全部" else None
        )

        st.session_state.comparison_data = df
        return df

# 主界面
st.markdown('<div class="main-header">📊 Google Search Console SEO 关键词看板</div>', unsafe_allow_html=True)

# 侧边栏 - 配置
with st.sidebar:
    st.header("⚙️ 配置")

    # 初始化连接
    if st.session_state.gsc_client is None:
        if st.button("连接 Google Search Console", type="primary", use_container_width=True):
            initialize_client()
    else:
        st.success("✅ 已连接")
        if st.button("重新连接", use_container_width=True):
            st.session_state.gsc_client = None
            st.session_state.sites = []
            st.rerun()

    # 网站选择
    if st.session_state.sites:
        st.divider()
        selected_site = st.selectbox(
            "选择网站",
            st.session_state.sites,
            help="选择要分析的网站"
        )

        # 日期范围
        date_options = {
            "最近 7 天": 7,
            "最近 30 天": 30,
            "最近 90 天": 90,
            "最近 180 天": 180
        }
        selected_period = st.selectbox("日期范围", list(date_options.keys()))
        days = date_options[selected_period]

        # 设备类型
        device_type = st.selectbox(
            "设备类型",
            ["全部", "mobile", "desktop", "tablet"],
            help="筛选特定设备类型的数据"
        )

        # 国家/地区
        country = st.text_input(
            "国家/地区代码",
            value="全部",
            help="输入 ISO 3166-1 alpha-3 代码，如 usa, chn, gbr。留空或输入'全部'表示不筛选"
        )

        # 数据行数限制
        row_limit = st.slider(
            "数据行数",
            min_value=100,
            max_value=5000,
            value=1000,
            step=100,
            help="限制返回的关键词数量"
        )

        st.divider()

        # 加载数据按钮
        if st.button("🔄 加载数据", type="primary", use_container_width=True):
            load_keyword_data(selected_site, days, device_type, country, row_limit)
            load_comparison_data(selected_site, days, device_type, country, row_limit)

        # 显示对比期选项
        compare_enabled = st.checkbox("启用同比分析", value=True)

# 主内容区域
if st.session_state.keyword_data is not None:
    df = st.session_state.keyword_data
    df_compare = st.session_state.comparison_data

    # 核心指标卡片
    st.subheader("📈 核心指标")

    col1, col2, col3, col4 = st.columns(4)

    total_clicks = df['clicks'].sum()
    total_impressions = df['impressions'].sum()
    avg_ctr = df['ctr'].mean() * 100
    avg_position = df['position'].mean()

    # 计算变化率（如果有对比数据）
    clicks_change = None
    impressions_change = None
    ctr_change = None
    position_change = None

    if compare_enabled and df_compare is not None and not df_compare.empty:
        prev_clicks = df_compare['clicks'].sum()
        prev_impressions = df_compare['impressions'].sum()
        prev_ctr = df_compare['ctr'].mean() * 100
        prev_position = df_compare['position'].mean()

        clicks_change = calculate_growth(total_clicks, prev_clicks)
        impressions_change = calculate_growth(total_impressions, prev_impressions)
        ctr_change = calculate_growth(avg_ctr, prev_ctr)
        position_change = -calculate_growth(avg_position, prev_position)

    with col1:
        st.markdown(create_metric_card_html(
            "总点击量",
            format_number(total_clicks),
            clicks_change
        ), unsafe_allow_html=True)

    with col2:
        st.markdown(create_metric_card_html(
            "总展现量",
            format_number(total_impressions),
            impressions_change
        ), unsafe_allow_html=True)

    with col3:
        st.markdown(create_metric_card_html(
            "平均 CTR",
            f"{avg_ctr:.2f}%",
            ctr_change
        ), unsafe_allow_html=True)

    with col4:
        st.markdown(create_metric_card_html(
            "平均排名",
            f"{avg_position:.1f}",
            position_change
        ), unsafe_allow_html=True)

    st.divider()

    # 标签页布局
    tab1, tab2, tab3, tab4 = st.tabs(["📊 关键词总览", "🔍 关键词详情", "📈 趋势分析", "📥 数据导出"])

    with tab1:
        st.subheader("Top 20 关键词")

        # 排序选项
        sort_by = st.selectbox(
            "排序依据",
            ["clicks", "impressions", "ctr", "position"],
            format_func=lambda x: {
                "clicks": "点击量",
                "impressions": "展现量",
                "ctr": "CTR",
                "position": "平均排名"
            }[x]
        )

        # Top 20 条形图
        if sort_by == "position":
            df_sorted = df.nsmallest(20, sort_by)
        else:
            df_sorted = df.nlargest(20, sort_by)

        fig = create_bar_chart(
            df_sorted,
            x_col='query',
            y_col=sort_by,
            title=f"Top 20 关键词 - 按{['点击量', '展现量', 'CTR', '平均排名'][['clicks', 'impressions', 'ctr', 'position'].index(sort_by)]}",
            top_n=20
        )
        st.plotly_chart(fig, use_container_width=True)

        # 表格视图
        st.subheader("关键词列表")

        # 格式化显示
        df_display = df.copy()
        df_display['ctr'] = df_display['ctr'].apply(lambda x: f"{x*100:.2f}%")
        df_display['position'] = df_display['position'].apply(lambda x: f"{x:.1f}")
        df_display.columns = ['关键词', '点击量', '展现量', 'CTR', '平均排名']

        st.dataframe(
            df_display,
            use_container_width=True,
            height=400
        )

    with tab2:
        st.subheader("关键词搜索")

        search_query = st.text_input("输入关键词进行搜索", placeholder="例如: SEO")

        if search_query:
            filtered_df = df[df['query'].str.contains(search_query, case=False, na=False)]

            if not filtered_df.empty:
                st.write(f"找到 {len(filtered_df)} 个相关关键词")

                # 显示统计
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总点击量", format_number(filtered_df['clicks'].sum()))
                with col2:
                    st.metric("总展现量", format_number(filtered_df['impressions'].sum()))
                with col3:
                    st.metric("平均 CTR", f"{filtered_df['ctr'].mean()*100:.2f}%")

                # 显示表格
                filtered_display = filtered_df.copy()
                filtered_display['ctr'] = filtered_display['ctr'].apply(lambda x: f"{x*100:.2f}%")
                filtered_display['position'] = filtered_display['position'].apply(lambda x: f"{x:.1f}")
                filtered_display.columns = ['关键词', '点击量', '展现量', 'CTR', '平均排名']

                st.dataframe(filtered_display, use_container_width=True)
            else:
                st.info("未找到匹配的关键词")

    with tab3:
        st.subheader("关键词趋势分析")

        # 选择关键词
        top_keywords = df.nlargest(50, 'clicks')['query'].tolist()
        selected_keyword = st.selectbox(
            "选择关键词",
            top_keywords,
            help="从 Top 50 关键词中选择"
        )

        if selected_keyword:
            trend_days = st.slider("趋势天数", 7, 90, 30)

            trend_df = st.session_state.gsc_client.get_keyword_trend(
                selected_site,
                selected_keyword,
                trend_days
            )

            if not trend_df.empty:
                col1, col2 = st.columns(2)

                with col1:
                    fig_clicks = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='clicks',
                        title='点击量趋势',
                        color='blue'
                    )
                    st.plotly_chart(fig_clicks, use_container_width=True)

                with col2:
                    fig_impressions = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='impressions',
                        title='展现量趋势',
                        color='green'
                    )
                    st.plotly_chart(fig_impressions, use_container_width=True)

                col3, col4 = st.columns(2)

                with col3:
                    fig_ctr = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='ctr',
                        title='CTR 趋势',
                        color='orange'
                    )
                    st.plotly_chart(fig_ctr, use_container_width=True)

                with col4:
                    fig_position = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='position',
                        title='排名趋势',
                        color='red'
                    )
                    st.plotly_chart(fig_position, use_container_width=True)
            else:
                st.warning("该关键词没有趋势数据")

    with tab4:
        st.subheader("导出数据")

        export_format = st.radio("选择导出格式", ["Excel (.xlsx)", "CSV (.csv)"])

        if st.button("下载数据", type="primary"):
            if export_format == "Excel (.xlsx)":
                excel_data = export_to_excel(df)
                st.download_button(
                    label="📥 下载 Excel 文件",
                    data=excel_data,
                    file_name=f"gsc_keywords_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                csv_data = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载 CSV 文件",
                    data=csv_data,
                    file_name=f"gsc_keywords_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

else:
    # 未连接或未加载数据
    if st.session_state.gsc_client is None:
        st.info("👈 请先在侧边栏点击'连接 Google Search Console'按钮")
        st.markdown("""
        ### 快速开始

        1. 确保已完成 API 配置
        2. 点击侧边栏的连接按钮
        3. 按照提示完成授权
        4. 选择网站并加载数据
        """)
    else:
        st.info("👈 请在侧边栏选择网站并点击'加载数据'按钮")

# 页脚
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 12px;">
    Google Search Console SEO 关键词看板 | 数据来源: Google Search Console API
</div>
""", unsafe_allow_html=True)
4. 点击 "Commit changes..." → "Commit changes"

完成后告诉我：文件3已创建

✅ 很好！第2个文件创建成功！

现在创建第3个文件（最重要的主程序）：

📝 创建第3个文件：app.py
1. 回到仓库主页，点击 "Add file" → "Create new file"

2. 在 "Name your file..." 输入框中输入：

app.py
3. 在下面的大文本框中，复制粘贴以下内容：

（内容比较长，请完整复制）

"""
Google Search Console SEO 关键词看板
"""
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import os

from gsc_api import GSCClient
from utils import (
    format_number, create_metric_card_html, create_trend_chart,
    create_bar_chart, export_to_excel, calculate_growth, get_date_ranges
)

# 页面配置
st.set_page_config(
    page_title="GSC SEO 关键词看板",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 自定义 CSS
st.markdown("""
<style>
    .main-header {
        font-size: 36px;
        font-weight: bold;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 30px;
    }
    .metric-container {
        display: flex;
        justify-content: space-around;
        margin: 20px 0;
    }
    .stAlert {
        margin-top: 20px;
    }
</style>
""", unsafe_allow_html=True)

# 初始化 session state
if 'gsc_client' not in st.session_state:
    st.session_state.gsc_client = None
if 'sites' not in st.session_state:
    st.session_state.sites = []
if 'keyword_data' not in st.session_state:
    st.session_state.keyword_data = None
if 'comparison_data' not in st.session_state:
    st.session_state.comparison_data = None

def initialize_client():
    """初始化 GSC 客户端"""
    try:
        if not os.path.exists('credentials.json'):
            st.error("❌ 找不到 credentials.json 文件")
            st.info("请参考 API配置指南.md 配置 Google Search Console API")
            return False

        with st.spinner('正在连接 Google Search Console...'):
            st.session_state.gsc_client = GSCClient()
            st.session_state.sites = st.session_state.gsc_client.get_sites()

        if not st.session_state.sites:
            st.warning("⚠️ 未找到有权限访问的网站")
            return False

        st.success("✅ 连接成功！")
        return True

    except FileNotFoundError as e:
        st.error(f"❌ 文件错误: {e}")
        return False
    except Exception as e:
        st.error(f"❌ 连接失败: {e}")
        return False

def load_keyword_data(site_url, days, device_type, country, row_limit):
    """加载关键词数据"""
    with st.spinner('正在获取数据...'):
        df = st.session_state.gsc_client.get_keyword_data(
            site_url=site_url,
            days=days,
            row_limit=row_limit,
            device_type=device_type if device_type != "全部" else None,
            country=country if country != "全部" else None
        )

        if df.empty:
            st.warning("⚠️ 未找到数据")
            return None

        st.session_state.keyword_data = df
        return df

def load_comparison_data(site_url, days, device_type, country, row_limit):
    """加载对比期数据"""
    end_date = datetime.now().date() - timedelta(days=days)
    start_date = end_date - timedelta(days=days)

    with st.spinner('正在获取对比期数据...'):
        df = st.session_state.gsc_client.query_data(
            site_url=site_url,
            start_date=start_date.strftime('%Y-%m-%d'),
            end_date=end_date.strftime('%Y-%m-%d'),
            dimensions=['query'],
            row_limit=row_limit,
            device_type=device_type if device_type != "全部" else None,
            country=country if country != "全部" else None
        )

        st.session_state.comparison_data = df
        return df

# 主界面
st.markdown('<div class="main-header">📊 Google Search Console SEO 关键词看板</div>', unsafe_allow_html=True)

# 侧边栏 - 配置
with st.sidebar:
    st.header("⚙️ 配置")

# 初始化连接
    if st.session_state.gsc_client is None:
        if st.button("连接 Google Search Console", type="primary", use_container_width=True):
            initialize_client()
    else:
        st.success("✅ 已连接")
        if st.button("重新连接", use_container_width=True):
            st.session_state.gsc_client = None
            st.session_state.sites = []
            st.rerun()

    # 网站选择
    if st.session_state.sites:
        st.divider()
        selected_site = st.selectbox(
            "选择网站",
            st.session_state.sites,
            help="选择要分析的网站"
        )

        # 日期范围
        date_options = {
            "最近 7 天": 7,
            "最近 30 天": 30,
            "最近 90 天": 90,
            "最近 180 天": 180
        }
        selected_period = st.selectbox("日期范围", list(date_options.keys()))
        days = date_options[selected_period]

        # 设备类型
        device_type = st.selectbox(
            "设备类型",
            ["全部", "mobile", "desktop", "tablet"],
            help="筛选特定设备类型的数据"
        )

        # 国家/地区
        country = st.text_input(
            "国家/地区代码",
            value="全部",
            help="输入 ISO 3166-1 alpha-3 代码，如 usa, chn, gbr。留空或输入'全部'表示不筛选"
        )

        # 数据行数限制
        row_limit = st.slider(
            "数据行数",
            min_value=100,
            max_value=5000,
            value=1000,
            step=100,
            help="限制返回的关键词数量"
        )

        st.divider()

        # 加载数据按钮
        if st.button("🔄 加载数据", type="primary", use_container_width=True):
            load_keyword_data(selected_site, days, device_type, country, row_limit)
            load_comparison_data(selected_site, days, device_type, country, row_limit)

        # 显示对比期选项
        compare_enabled = st.checkbox("启用同比分析", value=True)

# 主内容区域
if st.session_state.keyword_data is not None:
    df = st.session_state.keyword_data
    df_compare = st.session_state.comparison_data

    # 核心指标卡片
    st.subheader("📈 核心指标")

    col1, col2, col3, col4 = st.columns(4)

    total_clicks = df['clicks'].sum()
    total_impressions = df['impressions'].sum()
    avg_ctr = df['ctr'].mean() * 100
    avg_position = df['position'].mean()

    # 计算变化率（如果有对比数据）
    clicks_change = None
    impressions_change = None
    ctr_change = None
    position_change = None

    if compare_enabled and df_compare is not None and not df_compare.empty:
        prev_clicks = df_compare['clicks'].sum()
        prev_impressions = df_compare['impressions'].sum()
        prev_ctr = df_compare['ctr'].mean() * 100
        prev_position = df_compare['position'].mean()

        clicks_change = calculate_growth(total_clicks, prev_clicks)
        impressions_change = calculate_growth(total_impressions, prev_impressions)
        ctr_change = calculate_growth(avg_ctr, prev_ctr)
        position_change = -calculate_growth(avg_position, prev_position)

    with col1:
        st.markdown(create_metric_card_html(
            "总点击量",
            format_number(total_clicks),
            clicks_change
        ), unsafe_allow_html=True)

    with col2:
        st.markdown(create_metric_card_html(
            "总展现量",
            format_number(total_impressions),
            impressions_change
        ), unsafe_allow_html=True)

    with col3:
        st.markdown(create_metric_card_html(
            "平均 CTR",
            f"{avg_ctr:.2f}%",
            ctr_change
        ), unsafe_allow_html=True)

    with col4:
        st.markdown(create_metric_card_html(
            "平均排名",
            f"{avg_position:.1f}",
            position_change
        ), unsafe_allow_html=True)

    st.divider()

    # 标签页布局
    tab1, tab2, tab3, tab4 = st.tabs(["📊 关键词总览", "🔍 关键词详情", "📈 趋势分析", "📥 数据导出"])

    with tab1:
        st.subheader("Top 20 关键词")

        # 排序选项
        sort_by = st.selectbox(
            "排序依据",
            ["clicks", "impressions", "ctr", "position"],
            format_func=lambda x: {
                "clicks": "点击量",
                "impressions": "展现量",
                "ctr": "CTR",
                "position": "平均排名"
            }[x]
        )

        # Top 20 条形图
        if sort_by == "position":
            df_sorted = df.nsmallest(20, sort_by)
        else:
            df_sorted = df.nlargest(20, sort_by)

        fig = create_bar_chart(
            df_sorted,
            x_col='query',
            y_col=sort_by,
            title=f"Top 20 关键词 - 按{['点击量', '展现量', 'CTR', '平均排名'][['clicks', 'impressions', 'ctr', 'position'].index(sort_by)]}",
            top_n=20
        )
        st.plotly_chart(fig, use_container_width=True)

        # 表格视图
        st.subheader("关键词列表")

        # 格式化显示
        df_display = df.copy()
        df_display['ctr'] = df_display['ctr'].apply(lambda x: f"{x*100:.2f}%")
        df_display['position'] = df_display['position'].apply(lambda x: f"{x:.1f}")
        df_display.columns = ['关键词', '点击量', '展现量', 'CTR', '平均排名']

        st.dataframe(
            df_display,
            use_container_width=True,
            height=400
        )

    with tab2:
        st.subheader("关键词搜索")

        search_query = st.text_input("输入关键词进行搜索", placeholder="例如: SEO")

        if search_query:
            filtered_df = df[df['query'].str.contains(search_query, case=False, na=False)]

            if not filtered_df.empty:
                st.write(f"找到 {len(filtered_df)} 个相关关键词")

                # 显示统计
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("总点击量", format_number(filtered_df['clicks'].sum()))
                with col2:
                    st.metric("总展现量", format_number(filtered_df['impressions'].sum()))
                with col3:
                    st.metric("平均 CTR", f"{filtered_df['ctr'].mean()*100:.2f}%")

                # 显示表格
                filtered_display = filtered_df.copy()
                filtered_display['ctr'] = filtered_display['ctr'].apply(lambda x: f"{x*100:.2f}%")
                filtered_display['position'] = filtered_display['position'].apply(lambda x: f"{x:.1f}")
                filtered_display.columns = ['关键词', '点击量', '展现量', 'CTR', '平均排名']

                st.dataframe(filtered_display, use_container_width=True)
            else:
                st.info("未找到匹配的关键词")

    with tab3:
        st.subheader("关键词趋势分析")

        # 选择关键词
        top_keywords = df.nlargest(50, 'clicks')['query'].tolist()
        selected_keyword = st.selectbox(
            "选择关键词",
            top_keywords,
            help="从 Top 50 关键词中选择"
        )

        if selected_keyword:
            trend_days = st.slider("趋势天数", 7, 90, 30)

            trend_df = st.session_state.gsc_client.get_keyword_trend(
                selected_site,
                selected_keyword,
                trend_days
            )

            if not trend_df.empty:
                col1, col2 = st.columns(2)

                with col1:
                    fig_clicks = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='clicks',
                        title='点击量趋势',
                        color='blue'
                    )
                    st.plotly_chart(fig_clicks, use_container_width=True)

                with col2:
                    fig_impressions = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='impressions',
                        title='展现量趋势',
                        color='green'
                    )
                    st.plotly_chart(fig_impressions, use_container_width=True)

col3, col4 = st.columns(2)

                with col3:
                    fig_ctr = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='ctr',
                        title='CTR 趋势',
                        color='orange'
                    )
                    st.plotly_chart(fig_ctr, use_container_width=True)

                with col4:
                    fig_position = create_trend_chart(
                        trend_df,
                        x_col='date',
                        y_col='position',
                        title='排名趋势',
                        color='red'
                    )
                    st.plotly_chart(fig_position, use_container_width=True)
            else:
                st.warning("该关键词没有趋势数据")

    with tab4:
        st.subheader("导出数据")

        export_format = st.radio("选择导出格式", ["Excel (.xlsx)", "CSV (.csv)"])

        if st.button("下载数据", type="primary"):
            if export_format == "Excel (.xlsx)":
                excel_data = export_to_excel(df)
                st.download_button(
                    label="📥 下载 Excel 文件",
                    data=excel_data,
                    file_name=f"gsc_keywords_{datetime.now().strftime('%Y%m%d')}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
            else:
                csv_data = df.to_csv(index=False).encode('utf-8-sig')
                st.download_button(
                    label="📥 下载 CSV 文件",
                    data=csv_data,
                    file_name=f"gsc_keywords_{datetime.now().strftime('%Y%m%d')}.csv",
                    mime="text/csv"
                )

else:
    # 未连接或未加载数据
    if st.session_state.gsc_client is None:
        st.info("👈 请先在侧边栏点击'连接 Google Search Console'按钮")
        st.markdown("""
        ### 快速开始

        1. 确保已完成 API 配置
        2. 点击侧边栏的连接按钮
        3. 按照提示完成授权
        4. 选择网站并加载数据
        """)
    else:
        st.info("👈 请在侧边栏选择网站并点击'加载数据'按钮")

# 页脚
st.divider()
st.markdown("""
<div style="text-align: center; color: #666; font-size: 12px;">
    Google Search Console SEO 关键词看板 | 数据来源: Google Search Console API
</div>
""", unsafe_allow_html=True)
