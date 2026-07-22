import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ページの設定
st.set_page_config(
    page_title="病院経営ダッシュボード",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 一画面化とUI最適化のためのCSS ---
st.markdown("""
<style>
    .block-container {
        padding-top: 3.0rem !important; 
        padding-bottom: 1.0rem !important;
        padding-left: 2.0rem !important;
        padding-right: 2.0rem !important;
    }
            
    /* ▼▼ 修正： [data-testid="stSidebar"] を付けて優先度を上げ、上書きを防ぐ ▼▼ */
    [data-testid="stSidebar"] .sidebar-title {
        font-size: 18px !important;     /* 15pxから+3px大きく */
        font-weight: bold;
        color: #3b82f6 !important;      /* ライト・ダーク両方で視認性が高い鮮やかなブルーへ変更 */
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
        line-height: 1.5 !important;
        display: block;
    }
    [data-testid="stSidebar"] .sidebar-desc {
        font-size: 11.5px !important;
        color: var(--text-color) !important;    /* 環境に合わせて自動で切り替わるテキスト色を使用 */
        line-height: 1.5 !important;
        margin-bottom: 0.2rem !important;
        display: block;
        opacity: 0.8;       /* 少しだけ透明にしてサブテキスト感を出す */
    }
    
    /* サイドバーの基本フォントサイズ（上記2つ以外に適用される） */
    [data-testid="stSidebar"] * {
        font-size: 13px !important;
    }
    
    
    /* ▼▼ サイドバー専用の余白圧縮設定 ▼▼ */
    [data-testid="stSidebar"] div[data-testid="stVerticalBlock"] {
        gap: 0.5rem !important; 
    }
    [data-testid="stSidebar"] hr {
        margin-top: 0.3rem !important;
        margin-bottom: 0.3rem !important;
    }
    /* ▲▲ ここまで ▲▲ */
    
    .stSelectbox {
        margin-bottom: 0px !important;
    }
    div[data-testid="stExpander"] {
        margin-bottom: 5px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 10px !important;
    }
    
    /* ラジオボタンの背景枠と余白をスリム化 */
    div[role="radiogroup"] {
        /* ダーク・ライトモードで自動的に切り替わる背景色変数を使用 */
        background-color: var(--secondary-background-color) !important;
        padding: 6px 10px !important;
        border-radius: 8px;
        margin-top: 2px !important;
        margin-bottom: 2px !important;
        border: 1px solid rgba(128, 128, 128, 0.2); /* 輪郭をうっすらつけて視認性を向上 */
    }
</style>
""", unsafe_allow_html=True)


# --- サイドバーの固定基本表示 ---
st.sidebar.markdown('<div class="sidebar-title">🏥 病院経営 ダッシュボード</div>', unsafe_allow_html=True)
# st.sidebar.markdown('<div class="sidebar-desc">Excelから定義マスターと実績データを一括読み込みし、多角的な経営分析を行います。</div>', unsafe_allow_html=True)
# st.sidebar.header("データのアップロード と 設定")

uploaded_file = st.sidebar.file_uploader(
    "▼Excelファイルをアップロード", 
    type=["xlsx"],
    help="data, subjects, kpi_categories, units の4シートを含むエクセルを選択してください。"
)

# ポップアップ用関数（データ登録状況確認）
@st.dialog("🔍 登録データ件数の確認", width="large")
def show_data_summary_dialog(df_raw, req_subjects):
    st.write("アップロードされたデータの科目ごとの登録件数（行数）を表示しています。緑色は最大値（揃っている）、黄色は一部不足、赤色はデータなしを示します。")
    summary_pivot = df_raw.pivot_table(
        index="勘定科目", columns="施設名", values="金額", aggfunc="count", fill_value=0
    )
    for sub in req_subjects:
        if sub not in summary_pivot.index:
            summary_pivot.loc[sub] = 0
    summary_pivot = summary_pivot.reindex(req_subjects + [idx for idx in summary_pivot.index if idx not in req_subjects])
    
    # --- 修正部分：行ごとの最大値を基準に色を判定する関数 ---
    def color_cells_by_row_max(row):
        row_max = row.max()
        colors = []
        for val in row:
            if val == 0:
                colors.append('background-color: #ffccd5; color: #333;') # 赤色 (データなし)
            elif val < row_max:
                colors.append('background-color: #fff2cc; color: #333;') # 黄色 (0より大きく、最大値未満)
            else:
                colors.append('background-color: #e2f0d9; color: #333;') # 緑色 (最大値)
        return colors
        
    st.dataframe(summary_pivot.style.apply(color_cells_by_row_max, axis=1), use_container_width=True)


# --- メインロジック ---
if uploaded_file is not None:
    try:
        # 1. 全4シートの読み込み
        xl = pd.ExcelFile(uploaded_file)
        required_sheets = ["data", "subjects", "kpi_categories", "units"]
        if not all(sh in xl.sheet_names for sh in required_sheets):
            st.error(f"Excelファイルに必要なシートが不足しています。必須: {required_sheets}")
            st.stop()
            
        df_data = xl.parse("data")
        df_subjects = xl.parse("subjects")
        df_kpis = xl.parse("kpi_categories")
        df_units = xl.parse("units")
        
        # 2. Excelマスターから各種定義変数を動的にパース・生成
        financial_subjects = df_subjects[df_subjects["種類"] == "financial"]["科目名"].astype(str).str.strip().tolist()
        functional_subjects = df_subjects[df_subjects["種類"] == "functional"]["科目名"].astype(str).str.strip().tolist()
        required_subjects = financial_subjects + functional_subjects
        
        kpi_categories = {}
        all_kpis = {}
        for _, row in df_kpis.iterrows():
            cat = str(row["カテゴリ"]).strip()
            kpi_name = str(row["KPI名"]).strip()
            kpi_info = {
                "formula": str(row["計算式"]),
                "unit": str(row["単位"]),
                "meaning": str(row["経営的な意味"]),
                "benchmark": str(row["判断の目安・基準"]),
                "calc_str": str(row["計算ロジック"])
            }
            if cat not in kpi_categories:
                kpi_categories[cat] = {}
            kpi_categories[cat][kpi_name] = kpi_info
            all_kpis[kpi_name] = kpi_info

        unit_rules = dict(zip(df_units["判定キーワード"].astype(str), df_units["単位"].astype(str)))

        # --- 選択状態を保持するためのSession State初期化 ---
        if "item1_cat" not in st.session_state:
            st.session_state["item1_cat"] = list(kpi_categories.keys())[0] if kpi_categories else "財務データ"
        if "item2_cat" not in st.session_state:
            st.session_state["item2_cat"] = list(kpi_categories.keys())[0] if kpi_categories else "財務データ"

        # 3. 動的関数定義
        def get_unit(item_name):
            if item_name in all_kpis:
                return all_kpis[item_name]["unit"]
            for keyword, unit_val in unit_rules.items():
                if keyword in item_name:
                    return unit_val
            return ""

        def format_value(val, item_name):
            if pd.isna(val): return "-"
            unit = get_unit(item_name)
            if unit == "%": return f"{val:.2f} %"
            elif unit == "回": return f"{val:.2f} 回"
            elif unit == "か月": return f"{val:.2f} か月"
            elif unit == "日": return f"{val:.1f} 日"
            elif unit == "人": return f"{val:,.1f} 人" if "100床当たり" in item_name or "人当たり" in item_name else f"{val:,.0f} 人"
            elif unit == "円": return f"¥{val:,.0f}"
            return f"{val:,.2f}"

        def get_axis_label(item_name):
            unit = get_unit(item_name)
            return f"{item_name} ({unit})" if unit else item_name

        def select_item_ui(key_prefix, title_text, allow_none=False):
            st.markdown(f"<span style='font-size:13px; font-weight:bold;'>{title_text}</span>", unsafe_allow_html=True)
            categories_list = list(kpi_categories.keys()) + ["財務データ", "機能データ"]
            if allow_none:
                categories_list = ["(選択なし)"] + categories_list
            
            if not allow_none and st.session_state.get(f"{key_prefix}_cat") == "(選択なし)":
                st.session_state[f"{key_prefix}_cat"] = list(kpi_categories.keys())[0]
            
            if st.session_state.get(f"{key_prefix}_cat") not in categories_list:
                st.session_state[f"{key_prefix}_cat"] = categories_list[0] if categories_list else ""

            col_c, col_i = st.columns([1, 1.8])
            with col_c:
                def on_cat_change():
                    if f"{key_prefix}_item" in st.session_state:
                        del st.session_state[f"{key_prefix}_item"]
                
                cat = st.selectbox("大分類", categories_list, key=f"{key_prefix}_cat", label_visibility="collapsed", on_change=on_cat_change)
            
            if cat == "(選択なし)":
                with col_i: 
                    st.selectbox("詳細", ["-"], disabled=True, key=f"{key_prefix}_item_disabled", label_visibility="collapsed")
                return None
            
            with col_i:
                options = financial_subjects if cat == "財務データ" else functional_subjects if cat == "機能データ" else list(kpi_categories[cat].keys())
                
                if f"{key_prefix}_item" not in st.session_state or st.session_state[f"{key_prefix}_item"] not in options:
                    if key_prefix == "item2" and len(options) > 1:
                        st.session_state[f"{key_prefix}_item"] = options[1]
                    else:
                        st.session_state[f"{key_prefix}_item"] = options[0] if options else ""
                        
                item = st.selectbox("詳細項目", options, key=f"{key_prefix}_item", label_visibility="collapsed")
                
            return item

        def display_kpi_explanation(item_name, label_text="💡 指標"):
            if not item_name: return
            info = all_kpis.get(item_name)
            if info:
                st.markdown(f"""
                <div style="background-color: #f0f4f8; padding: 10px 14px; border-radius: 6px; border-left: 4px solid #1e3b8b; margin-top: 10px; margin-bottom: 5px;">
                    <div style="font-weight: bold; color: #1e3b8b; font-size: 13px; margin-bottom: 4px;">{label_text}: {item_name}</div>
                    <div style="font-size: 13px; margin-bottom: 3px; color: #374151;"><strong>計算式:</strong> <code>{info['formula']}</code></div>
                    <div style="font-size: 11px; margin-bottom: 3px; color: #374151; line-height: 1.4;"><strong>経営的な意味:</strong> {info['meaning']}</div>
                    <div style="font-size: 11px; color: #374151; line-height: 1.4;"><strong>判断の目安・基準:</strong> {info['benchmark']}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div style="background-color: #f9fafb; padding: 10px 14px; border-radius: 6px; border-left: 4px solid #6b7280; margin-top: 10px; margin-bottom: 5px;">
                    <div style="font-weight: bold; color: #4b5563; font-size: 13px; margin-bottom: 4px;">📊 データ: {item_name}</div>
                    <div style="font-size: 11px; color: #4b5563; line-height: 1.4;"><strong>経営的な意味:</strong> 実績値（生データ）です。時系列比較や規模確認に活用します。</div>
                </div>
                """, unsafe_allow_html=True)

        # 4. 実績データのクリーニングと計算
        df_data["勘定科目"] = df_data["勘定科目"].astype(str).str.strip()
        
        if st.sidebar.button("📊 登録データ件数を確認する"):
            show_data_summary_dialog(df_data, required_subjects)

        df_pivot = df_data.pivot_table(index=["年度", "施設名"], columns="勘定科目", values="金額", aggfunc="sum").reset_index()
        
        for sub in required_subjects:
            if sub not in df_pivot.columns:
                df_pivot[sub] = np.nan

        # 施設選択フィルター
        st.sidebar.markdown("---")
        all_facilities = df_pivot["施設名"].unique().tolist()
        selected_facilities = st.sidebar.multiselect("比較する施設を選択", options=all_facilities, default=all_facilities)
        filtered_df = df_pivot[df_pivot["施設名"].isin(selected_facilities)].copy()

        # 表示ビュー切り替え
        st.sidebar.markdown("---")
        view_mode = st.sidebar.radio(
            "📊 ダッシュボード表示ビュー切り替え",
            ["📈 ２指標の時系列比較", "📊 ２指標相関分析"]
        )

        # 【追加】時系列グラフの場合のみ、グラフ種類の選択を表示
        chart_type1, chart_type2 = "折れ線グラフ", "折れ線グラフ"
        if view_mode == "📈 ２指標の時系列比較":
            st.sidebar.markdown("---")
            st.sidebar.markdown('<div class="sidebar-title">📈 グラフ種類の選択</div>', unsafe_allow_html=True)
            chart_type1 = st.sidebar.radio("指標1 (主軸)", ["折れ線グラフ", "棒グラフ"], horizontal=True)
            chart_type2 = st.sidebar.radio("指標2 (第2軸)", ["折れ線グラフ", "棒グラフ"], horizontal=True)

        # KPI一括計算
        for kpi_name, kpi_info in all_kpis.items():
            try:
                filtered_df[kpi_name] = eval(kpi_info["calc_str"], {"df": filtered_df, "np": np})
            except Exception:
                filtered_df[kpi_name] = np.nan


        # ====================================================
        # ビュー1: ２指標の時系列比較
        # ====================================================
        if view_mode == "📈 ２指標の時系列比較":
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                selected_trend_item1 = select_item_ui("item1", "▼ 指標1（主軸）を選択", allow_none=False)
            with col_sel2:
                selected_trend_item2 = select_item_ui("item2", "▼ 指標2（第2軸）を選択", allow_none=True)

            filtered_df["年度_str"] = filtered_df["年度"].astype(str)
            trend_plot_df = filtered_df.sort_values(by="年度").copy()
            
            color_palette = px.colors.qualitative.Plotly
            unique_facilities = filtered_df["施設名"].unique().tolist()
            facility_colors = {fac: color_palette[i % len(color_palette)] for i, fac in enumerate(unique_facilities)}

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            for fac in unique_facilities:
                fac_df = trend_plot_df[trend_plot_df["施設名"] == fac]
                color = facility_colors[fac]

                # --- 修正: 指標1の値が 0 の場合は NaN に置換し、描画をスキップする ---
                y_val1 = fac_df[selected_trend_item1].replace(0, np.nan)
                
                # 【追加】指標1の描画処理（折れ線・棒グラフの切り替え）
                if chart_type1 == "折れ線グラフ":
                    trace1 = go.Scatter(
                        x=fac_df["年度_str"], y=y_val1,
                        name=f"{fac}: {selected_trend_item1}",
                        mode="lines+markers",
                        line=dict(width=3, dash='solid', color=color),
                        marker=dict(size=7),
                        connectgaps=False, # NaN（データなし）の前後で線を繋がず途切れさせる
                        hovertemplate=f"施設: {fac}<br>年度: %{{x}}<br>{selected_trend_item1}: %{{y}}<extra></extra>"
                    )
                else:
                    trace1 = go.Bar(
                        x=fac_df["年度_str"], y=y_val1,
                        name=f"{fac}: {selected_trend_item1}",
                        marker_color=color,
                        opacity=0.75,
                        hovertemplate=f"施設: {fac}<br>年度: %{{x}}<br>{selected_trend_item1}: %{{y}}<extra></extra>"
                    )
                fig.add_trace(trace1, secondary_y=False)
                
                # 【追加】指標2の描画処理（折れ線・棒グラフの切り替え）
                if selected_trend_item2:
                    # --- 修正: 指標2の値が 0 の場合も NaN に置換 ---
                    y_val2 = fac_df[selected_trend_item2].replace(0, np.nan)
                    
                    if chart_type2 == "折れ線グラフ":
                        trace2 = go.Scatter(
                            x=fac_df["年度_str"], y=y_val2,
                            name=f"{fac}: {selected_trend_item2}",
                            mode="lines+markers",
                            line=dict(width=2, dash='dot', color=color),
                            marker=dict(size=7),
                            connectgaps=False, # NaN（データなし）の前後で線を繋がず途切れさせる
                            hovertemplate=f"施設: {fac}<br>年度: %{{x}}<br>{selected_trend_item2}: %{{y}}<extra></extra>"
                        )
                    else:
                        trace2 = go.Bar(
                            x=fac_df["年度_str"], y=y_val2,
                            name=f"{fac}: {selected_trend_item2}",
                            marker_color=color,
                            opacity=0.6,
                            hovertemplate=f"施設: {fac}<br>年度: %{{x}}<br>{selected_trend_item2}: %{{y}}<extra></extra>"
                        )
                    fig.add_trace(trace2, secondary_y=True)

            title_text = f"【推移比較】 {selected_trend_item1}"
            if selected_trend_item2:
                title_text += f" と {selected_trend_item2}"

            fig.update_layout(
                title=title_text,
                title_font=dict(size=14, family="Segoe UI"),
                font=dict(family="Segoe UI"),
                xaxis_title="年度",
                yaxis_title=get_axis_label(selected_trend_item1),
                template="plotly_white",
                height=500,
                barmode='group', # 複数施設の棒グラフが並んで表示されるように設定
                legend=dict(
                    orientation="v",
                    yanchor="top", y=1,
                    xanchor="left", x=1.05
                ),
                margin=dict(l=50, r=120, t=50, b=50)
            )
            
            fig.update_xaxes(showgrid=True, gridcolor='LightGray')
            fig.update_yaxes(showgrid=True, gridcolor='LightGray', secondary_y=False)
            
            if selected_trend_item2:
                fig.update_layout(yaxis2_title=get_axis_label(selected_trend_item2))
                fig.update_yaxes(showgrid=False, secondary_y=True)
            
            if get_unit(selected_trend_item1) == "円": fig.update_yaxes(tickformat=",.0f", secondary_y=False)
            if selected_trend_item2 and get_unit(selected_trend_item2) == "円": fig.update_yaxes(tickformat=",.0f", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)

            col_desc1, col_desc2 = st.columns(2)
            with col_desc1: display_kpi_explanation(selected_trend_item1, "💡指標1")
            with col_desc2: display_kpi_explanation(selected_trend_item2, "💡指標2")


        # ====================================================
        # ビュー2: ２指標相関分析（散布図）
        # ====================================================
        else:
            col_sel_y, col_sel_x = st.columns(2)
            with col_sel_y: 
                y_item = select_item_ui("item1", "▼ Y軸（縦軸）の設定", allow_none=False)
            with col_sel_x: 
                x_item = select_item_ui("item2", "▼ X軸（横軸）の設定", allow_none=False)

            col_years, _ = st.columns([2, 1])
            with col_years:
                all_years = sorted(filtered_df["年度"].unique().tolist())
                selected_years = st.multiselect("📅 表示する年度を選択", options=all_years, default=all_years, key="scatter_year_filter")

            scatter_df = filtered_df[filtered_df["年度"].isin(selected_years)].copy()
            scatter_df["年度_str"] = scatter_df["年度"].astype(str)
            valid_scatter_df = scatter_df.dropna(subset=[x_item, y_item]).copy()

            if len(valid_scatter_df) > 0 and x_item and y_item:
                x_label, y_label = get_axis_label(x_item), get_axis_label(y_item)
                valid_scatter_df["X軸_hover"] = valid_scatter_df[x_item].apply(lambda v: format_value(v, x_item))
                valid_scatter_df["Y軸_hover"] = valid_scatter_df[y_item].apply(lambda v: format_value(v, y_item))

                fig_scatter = px.scatter(
                    valid_scatter_df, x=x_item, y=y_item, color="施設名", hover_name="施設名",
                    hover_data={"年度_str": True, "X軸_hover": True, "Y軸_hover": True, x_item: False, y_item: False},
                    text="年度_str", title=f"【相関図】 {x_item} (横軸) × {y_item} (縦軸)", template="plotly_white"
                )
                fig_scatter.update_traces(marker=dict(size=12, opacity=0.85, line=dict(width=1, color='DarkSlateGrey')), textposition='top center')
                fig_scatter.update_layout(
                    xaxis_title=x_label, yaxis_title=y_label, font=dict(family="Segoe UI"), height=500,
                    legend=dict(orientation="v", yanchor="top", y=1, xanchor="left", x=1.05),
                    margin=dict(l=50, r=120, t=50, b=50)
                )
                fig_scatter.update_xaxes(showgrid=True, gridcolor='LightGray')
                fig_scatter.update_yaxes(showgrid=True, gridcolor='LightGray')

                if get_unit(x_item) == "円": fig_scatter.update_xaxes(tickformat=",.0f")
                if get_unit(y_item) == "円": fig_scatter.update_yaxes(tickformat=",.0f")

                st.plotly_chart(fig_scatter, use_container_width=True)
                
                col_exp_y, col_exp_x = st.columns(2)
                with col_exp_y: display_kpi_explanation(y_item, "💡 Y軸（縦軸）指標")
                with col_exp_x: display_kpi_explanation(x_item, "💡 X軸（横軸）指標")
            else:
                st.warning("選択された年度または指標で計算可能なデータが存在しません。")

    except Exception as e:
        st.error(f"Excelの読み込みまたは計算中にエラーが発生しました。シート名や列名を確認してください。詳細: {e}")
else:
    st.info("👈 左側のサイドバーから、定義シートが含まれた新しい仕様のExcelファイルをアップロードしてください。")
