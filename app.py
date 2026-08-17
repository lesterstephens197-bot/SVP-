with tab2:
        st.subheader("📋 SVP 申报参数自动生成")
        st.caption(f"当前算法配置：假定上传数据（1–8月）占全年总销量的 **{seasonality_ratio*100:.0f}%**。公式：`Annual = 历史出货量 / {seasonality_ratio:.2f}`，`Weekly = Annual / 52`。")

        # 1. 确保核心列存在并做填充处理，防止 NaN 导致 groupby 丢弃数据
        df_svp = df.copy()
        
        # 确定需要作为分组信息的列
        potential_cols = ['OMS ID', 'Merchant SKU', 'Vendor SKU', '产品名称', '品牌', '运营']
        group_cols = [c for c in potential_cols if c in df_svp.columns]

        if not group_cols:
            st.error("表格中未找到可用于分组的 OMS ID 或 SKU 列！")
            st.stop()

        # 对分组列中的空值填补占位符，避免 Pandas 丢弃包含空值的行
        for col in group_cols:
            df_svp[col] = df_svp[col].fillna("-").astype(str)

        # 2. 核心聚合计算 (dropna=False 确保不丢失任何数据)
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
