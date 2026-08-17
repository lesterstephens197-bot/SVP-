import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# 页面基本配置
st.set_page_config(
    page_title="THD DFC / SVP 销售预测与数据分析工具",
    page_icon="📊",
    layout="wide"
)

st.title("📊 Home Depot DFC / SVP 销售预测与数据分析仪表盘")
st.markdown("上传订单/出货数据表，自动分析历史销售趋势并生成 SVP 申报预估指标。")

# 侧边栏：文件上传与参数设置
st.sidebar.header("⚙️ 1. 上传数据与参数配置")
uploaded_file = st.sidebar.file_uploader("上传 Excel / CSV 文件", type=["xlsx", "xls", "csv"])

# SVP 预测参数设置
st.sidebar.subheader("🎯 SVP 季节性预测参数")
seasonality_ratio = st.sidebar.slider(
    "1–8月销量占全年的比例 (%)",
    min_value=50,
    max_value=95,
    value=80,
    step=1,
    help="除湿机为季节性产品，通常1–8月（含春夏旺季）占全年的 70%–80% 左右。"
) / 100.0

default_wos = st.sidebar.slider(
    "默认期望在手库存周数 (Desired Avg OH WOS)",
    min_value=2,
    max_value=12,
    value=6,
    step=1,
    help="通常推荐 6 周（4-8周均可）。"
)

if uploaded_file is not None:
    # 1. 读取数据
    try:
        if uploaded_file.name.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
        else:
            df = pd.read_excel(uploaded_file)
    except Exception as e:
        st.error(f"读取文件失败，请检查文件格式: {e}")
        st.stop()

    # 检查核心列名（兼容不同拼写与常见表头）
    required_cols = ['Order Date', 'Quantity']
    missing_cols = [col for col in required_cols if col not in df.columns]
    
    # 动态确定唯一识别 SKU 的列
    sku_primary_col = None
    for candidate in ['产品SKU', 'Merchant SKU', 'Vendor SKU', 'OMS ID']:
        if candidate in df.columns:
            sku_primary_col = candidate
            break

    if missing_cols or not sku_primary_col:
        st.error(f"数据集中缺少必要字段！缺少核心列: {missing_cols}，或未找到可标识的 SKU 列（如产品SKU/Merchant SKU/Vendor SKU）。")
        st.info("当前支持的标准表头包含: PO Number, Order Date, Merchant SKU, Vendor SKU, 产品名称, 产品SKU, Description, Unit Cost, Unit Cost Currency, Quantity, Total Cost")
        st.stop()

    # 2. 数据清洗
    df['Order Date'] = pd.to_datetime(df['Order Date'], errors='coerce')
    df = df.dropna(subset=['Order Date'])  # 删除无效日期
    df['Quantity'] = pd.to_numeric(df['Quantity'], errors='coerce').fillna(0)
    
    if 'Unit Cost' in df.columns:
        df['Unit Cost'] = pd.to_numeric(df['Unit Cost'], errors='coerce').fillna(0)
        if 'Total Cost' not in df.columns:
            df['Total Cost'] = df['Quantity'] * df['Unit Cost']
        else:
            df['Total Cost'] = pd.to_numeric(df['Total Cost'], errors='coerce').fillna(df['Quantity'] * df['Unit Cost'])

    df['YearMonth'] = df['Order Date'].dt.to_period('M').astype(str)

    # 顶部 KPI 指标
    total_units = df['Quantity'].sum()
    total_sales = df['Total Cost'].sum() if 'Total Cost' in df.columns else 0
    total_skus = df[sku_primary_col].nunique()

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("总出货件数 (Units)", f"{int(total_units):,}")
    col2.metric("总出货金额 ($)", f"${total_sales:,.2f}")
    col3.metric(f"在售 {sku_primary_col} 数量", f"{total_skus} 个")
    col4.metric("覆盖时间跨度", f"{df['YearMonth'].min()} ~ {df['YearMonth'].max()}")

    st.markdown("---")

    # 3. 标签页划分
    tab1, tab2, tab3 = st.tabs(["📈 历史销售分析", "🔮 SVP 预测导出 (核心)", "🔍 详细数据明细"])

    with tab1:
        st.subheader("1. 整体月度销售趋势")
        monthly_df = df.groupby('YearMonth').agg(
            Total_Units=('Quantity', 'sum'),
            Total_Amount=('Total Cost', 'sum') if 'Total Cost' in df.columns else ('Quantity', 'count')
        ).reset_index()

        fig_monthly = px.bar(
            monthly_df, 
            x='YearMonth', 
            y='Total_Units',
            text='Total_Units',
            title="月度出货件数 (Units) 趋势",
            labels={'YearMonth': '月份', 'Total_Units': '出货件数'},
            color_discrete_sequence=['#FF6F00']
        )
        fig_monthly.update_traces(textposition='outside')
        st.plotly_chart(fig_monthly, use_container_width=True)

        st.subheader(f"2. Top {sku_primary_col} 销售表现")
        name_col = '产品名称' if '产品名称' in df.columns else sku_primary_col
        
        top_skus = df.groupby([sku_primary_col, name_col]).agg(
            Total_Units=('Quantity', 'sum')
        ).reset_index().sort_values(by='Total_Units', ascending=False)

        fig_top = px.bar(
            top_skus.head(15),
            x='Total_Units',
            y=sku_primary_col,
            orientation='h',
            hover_data=[name_col],
            title=f"Top 15 销量最高的 {sku_primary_col}",
            labels={'Total_Units': '出货件数', sku_primary_col: sku_primary_col},
            color='Total_Units',
            color_continuous_scale='Oranges'
        )
        fig_top.update_layout(yaxis={'categoryorder':'total ascending'})
        st.plotly_chart(fig_top, use_container_width=True)

    with tab2:
        st.subheader("📋 SVP 申报参数自动生成")
        st.caption(f"当前算法配置：假定上传数据（1–8月）占全年总销量的 **{seasonality_ratio*100:.0f}%**。公式：`Annual = 历史出货量 / {seasonality_ratio:.2f}`，`Weekly = Annual / 52`。")

        # 1. 根据新的表头筛选需要展示和分组的列
        df_svp = df.copy()
        potential_cols = ['产品SKU', 'Merchant SKU', 'Vendor SKU', '产品名称', 'Description']
        group_cols = [c for c in potential_cols if c in df_svp.columns]

        if not group_cols:
            group_cols = [sku_primary_col]

        # 填充空值，避免 NaN 导致分组行丢失
        for col in group_cols:
            df_svp[col] = df_svp[col].fillna("-").astype(str)

        # 2. 核心聚合计算
        svp_df = df_svp.groupby(group_cols, dropna=False).agg(
            Actual_YTD_Units=('Quantity', 'sum')
        ).reset_index()

        # 3. 计算 SVP 核心指标
        svp_df['Annual Sales Units'] = np.round(svp_df['Actual_YTD_Units'] / seasonality_ratio).astype(int)
        svp_df['Avg Wkly Sales Units'] = np.round(svp_df['Annual Sales Units'] / 52).astype(int)
        svp_df['Desired Avg OH WOS'] = default_wos
        svp_df['Target DFC Inventory (OH)'] = svp_df['Avg Wkly Sales Units'] * svp_df['Desired Avg OH WOS']

        # 按销量降序排列
        svp_df = svp_df.sort_values(by='Annual Sales Units', ascending=False)

        # 4. 显示与导出
        display_cols = group_cols + [
            'Actual_YTD_Units', 
            'Annual Sales Units', 
            'Avg Wkly Sales Units', 
            'Desired Avg OH WOS', 
            'Target DFC Inventory (OH)'
        ]
        
        st.dataframe(svp_df[display_cols], use_container_width=True)

        # 导出 Excel 功能
        @st.cache_data
        def convert_df_to_excel(df_to_exp):
            import io
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                df_to_exp.to_excel(writer, index=False, sheet_name='SVP_Submission_Data')
            return output.getvalue()

        excel_data = convert_df_to_excel(svp_df[display_cols])
        st.download_button(
            label="📥 下载 SVP 预估表格 (Excel 格式)",
            data=excel_data,
            file_name="THD_SVP_Predicted_Submission.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    with tab3:
        st.subheader("📄 过滤与明细查询")
        selected_sku = st.multiselect(f"筛选 {sku_primary_col}", options=df[sku_primary_col].unique())
        
        filtered_df = df.copy()
        if selected_sku:
            filtered_df = filtered_df[filtered_df[sku_primary_col].isin(selected_sku)]

        st.dataframe(filtered_df, use_container_width=True)

else:
    st.info("👈 请在左侧边栏上传您的 Excel/CSV 销售订单文件以开始分析。")
