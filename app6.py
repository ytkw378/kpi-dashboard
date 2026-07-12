import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px

# ページの設定
st.set_page_config(
    page_title="病院経営DB",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏥 病院経営ダッシュボード")
st.write("各施設の財務データおよび病院機能データから、収益性・効率性・安全性・稼働性・生産性を多角的に比較分析します。")

# --- 定義データ群 ---

# 1. 必須の財務データ（19項目：院外処方率を除外）
financial_subjects = [
    "医業収益", "給与費", "材料費", "経費", "減価償却費", 
    "医業利益", "経常利益", "固定資産", "貯蔵品", "流動資産", 
    "当座資産", "総資産", "固定負債", "医業未収金", "流動負債", 
    "純資産", "委託費", "医薬品費", "長期借入金"
]

# 2. 新設の機能データ（17項目：院外処方率を含む）
functional_subjects = [
    "入院延患者数", "新入院患者数", "退院患者数", "入院単価", "入院稼働日数",
    "外来延患者数", "外来単価", "外来診療日数", "全職員数", "医師数", "看護師数",
    "病床数", "院外処方率"
]

# 全すべての必須入力科目の統合リスト
required_subjects = financial_subjects + functional_subjects

# 3. KPIのカテゴリ別定義（単位情報や計算式を保持）
kpi_categories = {
    "収益性": {
        "総資産対利益率(ROA)": {"formula": "経常利益 ÷ 総資産 × 100", "unit": "%", "calc": lambda df: (df['経常利益'] / df['総資産'].replace(0, np.nan)) * 100},
        "医業収益対経常利益率": {"formula": "経常利益 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['経常利益'] / df['医業収益'].replace(0, np.nan)) * 100},
        "医業収益対医業利益率": {"formula": "医業利益 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['医業利益'] / df['医業収益'].replace(0, np.nan)) * 100},
        "償却前医業利益率": {"formula": "(医業利益 ＋ 減価償却費) ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: ((df['医業利益'] + df['減価償却費']) / df['医業収益'].replace(0, np.nan)) * 100},
        "材料費率": {"formula": "材料費 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['材料費'] / df['医業収益'].replace(0, np.nan)) * 100},
        "医薬品費率": {"formula": "医薬品費 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['医薬品費'] / df['医業収益'].replace(0, np.nan)) * 100},
        "給与費率": {"formula": "給与費 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['給与費'] / df['医業収益'].replace(0, np.nan)) * 100},
        "委託費率": {"formula": "委託費 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['委託費'] / df['医業収益'].replace(0, np.nan)) * 100},
        "減価償却費率": {"formula": "減価償却費 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['減価償却費'] / df['医業収益'].replace(0, np.nan)) * 100},
        "1床当たり医業収益": {"formula": "医業収益 ÷ 病床数", "unit": "円", "calc": lambda df: df['医業収益'] / df['病床数'].replace(0, np.nan)}
    },
    "効率性": {
        "総資産回転率": {"formula": "医業収益 ÷ 総資産", "unit": "回", "calc": lambda df: df['医業収益'] / df['総資産'].replace(0, np.nan)},
        "固定資産回転率": {"formula": "医業収益 ÷ 固定資産", "unit": "回", "calc": lambda df: df['医業収益'] / df['固定資産'].replace(0, np.nan)},
        "医業未収金回転期間": {"formula": "医業未収金 ÷ (医業収益 ÷ 12)", "unit": "か月", "calc": lambda df: df['医業未収金'] / (df['医業収益'].replace(0, np.nan) / 12)},
        "在庫回転期間": {"formula": "貯蔵品 ÷ (材料費 ÷ 12)", "unit": "か月", "calc": lambda df: df['貯蔵品'] / (df['材料費'].replace(0, np.nan) / 12)}
    },
    "安全性": {
        "流動比率": {"formula": "流動資産 ÷ 流動負債 × 100", "unit": "%", "calc": lambda df: (df['流動資産'] / df['流動負債'].replace(0, np.nan)) * 100},
        "当座比率": {"formula": "当座資産 ÷ 流動負債 × 100", "unit": "%", "calc": lambda df: (df['当座資産'] / df['流動負債'].replace(0, np.nan)) * 100},
        "自己資本比率": {"formula": "純資産 ÷ 総資産 × 100", "unit": "%", "calc": lambda df: (df['純資産'] / df['総資産'].replace(0, np.nan)) * 100},
        "固定比率": {"formula": "固定資産 ÷ 純資産 × 100", "unit": "%", "calc": lambda df: (df['固定資産'] / df['純資産'].replace(0, np.nan)) * 100},
        "固定長期適合率": {"formula": "固定資産 ÷ (純資産 ＋ 固定負債) × 100", "unit": "%", "calc": lambda df: (df['固定資産'] / (df['純資産'] + df['固定負債']).replace(0, np.nan)) * 100},
        "借入金比率": {"formula": "長期借入金 ÷ 医業収益 × 100", "unit": "%", "calc": lambda df: (df['長期借入金'] / df['医業収益'].replace(0, np.nan)) * 100}
    },
    "活動性": {
        "病床稼働率": {"formula": "入院延患者数 ÷ (病床数 × 入院稼働日数) × 100", "unit": "%", "calc": lambda df: (df['入院延患者数'] / (df['病床数'] * df['入院稼働日数']).replace(0, np.nan)) * 100},
        "平均在院日数": {"formula": "入院延患者数 ÷ 新入院患者数", "unit": "日", "calc": lambda df: df['入院延患者数'] / df['新入院患者数'].replace(0, np.nan)},
        "1日平均入院患者数": {"formula": "入院延患者数 ÷ 入院稼働日数", "unit": "人", "calc": lambda df: df['入院延患者数'] / df['入院稼働日数'].replace(0, np.nan)},
        "1日平均外来患者数": {"formula": "外来延患者数 ÷ 外来診療日数", "unit": "人", "calc": lambda df: df['外来延患者数'] / df['外来診療日数'].replace(0, np.nan)}
    },
    "生産性": {
        "職員1人当たり医業収益": {"formula": "医業収益 ÷ 全職員数", "unit": "円", "calc": lambda df: df['医業収益'] / df['全職員数'].replace(0, np.nan)},
        "医師1人当たり医業収益": {"formula": "医業収益 ÷ 医師数", "unit": "円", "calc": lambda df: df['医業収益'] / df['医師数'].replace(0, np.nan)},
        "100床当たり全職員数": {"formula": "全職員数 ÷ 病床数 × 100", "unit": "人", "calc": lambda df: (df['全職員数'] / df['病床数'].replace(0, np.nan)) * 100},
        "100床当たり医師数": {"formula": "医師数 ÷ 病床数 × 100", "unit": "人", "calc": lambda df: (df['医師数'] / df['病床数'].replace(0, np.nan)) * 100},
        "100床当たり看護師数": {"formula": "看護師数 ÷ 病床数 × 100", "unit": "人", "calc": lambda df: (df['看護師数'] / df['病床数'].replace(0, np.nan)) * 100},
        "看護師1人当たり入院延患者数": {"formula": "入院延患者数 ÷ 看護師数", "unit": "人", "calc": lambda df: df['入院延患者数'] / df['看護師数'].replace(0, np.nan)}
    }
}

# フラットなKPI辞書の作成
all_kpis = {}
for cat, kpis in kpi_categories.items():
    all_kpis.update(kpis)


# --- 共通ユーティリティ関数 ---

def get_unit(item_name):
    """項目名から適切な単位（%, 回, か月, 日, 人, 円）を判定して返す"""
    if item_name in all_kpis:
        return all_kpis[item_name]["unit"]
    elif item_name in ["院外処方率"]:
        return "%"
    elif item_name in ["入院稼働日数", "外来診療日数", "平均在院日数"]:
        return "日"
    elif item_name in ["入院延患者数", "新入院患者数", "退院患者数", "外来延患者数", "全職員数", "医師数", "看護師数", "病床数"]:
        return "人"
    elif item_name in financial_subjects or item_name in ["入院単価", "外来単価", "長期借入金"]:
        return "円"
    else:
        return ""

def format_value(val, item_name):
    """値と項目名に応じた美しいフォーマットを返す"""
    if pd.isna(val):
        return "-"
    unit = get_unit(item_name)
    if unit == "%":
        return f"{val:.2f} %"
    elif unit == "回":
        return f"{val:.2f} 回"
    elif unit == "か月":
        return f"{val:.2f} か月"
    elif unit == "日":
        return f"{val:.1f} 日"
    elif unit == "人":
        return f"{val:,.1f} 人" if "100床当たり" in item_name or "人当たり" in item_name else f"{val:,.0f} 人"
    elif unit == "円":
        return f"¥{val:,.0f}"
    else:
        return f"{val:,.2f}"

def get_axis_label(item_name):
    """グラフの軸用のラベル（単位付き）を生成する"""
    unit = get_unit(item_name)
    if unit == "円":
        return f"{item_name} (円)"
    elif unit != "":
        return f"{item_name} ({unit})"
    return item_name

def select_item_ui(key_prefix, title_text, default_cat_idx=0, default_item_idx=0):
    """カテゴリ→詳細項目の2段階選択を行うUIコンポーネント"""
    st.markdown(f"**{title_text}**")
    categories_list = list(kpi_categories.keys()) + ["data財務", "data機能"]
    
    col_c, col_i = st.columns([1, 2])
    with col_c:
        cat = st.selectbox("大分類 (カテゴリ)", categories_list, index=default_cat_idx, key=f"{key_prefix}_cat")
    with col_i:
        if cat == "data財務":
            options = financial_subjects
        elif cat == "data機能":
            options = functional_subjects
        else:
            options = list(kpi_categories[cat].keys())
        
        safe_idx = default_item_idx if default_item_idx < len(options) else 0
        item = st.selectbox("詳細項目を選択", options, index=safe_idx, key=f"{key_prefix}_item")
    
    return item


# --- サイドバーの設定 ---
st.sidebar.header("データのアップロード と 設定")

uploaded_file = st.sidebar.file_uploader(
    "エクセルファイルをアップロード（.xlsx）", 
    type=["xlsx"],
    help="「年度」「施設名」「勘定科目」「金額」の4列を持つデータをアップロードしてください。"
)


# --- メインコンテンツ ---
if uploaded_file is not None:
    try:
        raw_df = pd.read_excel(uploaded_file)
        
        required_cols = ["年度", "施設名", "勘定科目", "金額"]
        if not all(col in raw_df.columns for col in required_cols):
            st.error(f"ファイルの列名が正しくありません。必須: {required_cols}")
            st.stop()
            
        raw_df["勘定科目"] = raw_df["勘定科目"].astype(str).str.strip()
        
        # --- アップロードデータの要約 ---
        st.subheader("📋 アップロードデータの要約")
        with st.expander("🔍 登録データ件数を確認する (クリックで開閉)", expanded=False):
            st.write("各科目の登録件数分布です。0件（ピンク色）の項目はデータが不足しています。")
            summary_pivot = raw_df.pivot_table(
                index="勘定科目", columns="施設名", values="金額", aggfunc="count", fill_value=0
            )
            for sub in required_subjects:
                if sub not in summary_pivot.index:
                    summary_pivot.loc[sub] = 0
            
            summary_pivot = summary_pivot.reindex(required_subjects + [idx for idx in summary_pivot.index if idx not in required_subjects])
            
            def color_missing_cells(val):
                color = '#ca828f' if val == 0 else '#63AF85'
                return f'background-color: {color}'
            
            try:
                styled_summary = summary_pivot.style.map(color_missing_cells)
            except AttributeError:
                styled_summary = summary_pivot.style.applymap(color_missing_cells)
            
            st.dataframe(styled_summary, use_container_width=True)

        # 縦持ちから横持ちへの変換
        df_pivot = raw_df.pivot_table(
            index=["年度", "施設名"], columns="勘定科目", values="金額", aggfunc="sum"
        ).reset_index()
        
        # 不足科目のNaN割り当て
        missing_warnings = []
        for sub in required_subjects:
            if sub not in df_pivot.columns:
                df_pivot[sub] = np.nan
                missing_warnings.append(sub)
        
        if missing_warnings:
            st.warning(f"以下の科目がデータに存在しません。関連する指標は計算されません: {', '.join(missing_warnings)}")

        # 施設フィルター
        all_facilities = df_pivot["施設名"].unique().tolist()
        selected_facilities = st.sidebar.multiselect(
            "比較する施設を選択（デフォルトは全施設）", options=all_facilities, default=all_facilities
        )
        filtered_df = df_pivot[df_pivot["施設名"].isin(selected_facilities)].copy()

        # すべてのKPIを一括計算
        for kpi_name, kpi_info in all_kpis.items():
            filtered_df[kpi_name] = kpi_info["calc"](filtered_df)

        # --- メイン表示エリア ---
        tab_trend_view, tab_scatter_view = st.tabs([
            "📈 単一指標の時系列推移", 
            "📊 2指標の相関分析（マトリクス散布図）"
        ])

        # ====================================================
        # タブ1: 単一指標の時系列推移
        # ====================================================
        with tab_trend_view:
            st.subheader("単一指標の時系列比較")
            
            # 初期表示設定: 収益性 > 1床当たり医業収益 (Index 9)
            selected_trend_item = select_item_ui("trend", "▼ グラフに表示する指標・項目を選択", default_cat_idx=0, default_item_idx=9)
            
            if selected_trend_item in all_kpis:
                st.info(f"**計算式:** `{all_kpis[selected_trend_item]['formula']}`")

            tab_graph, tab_data = st.tabs(["📊 時系列グラフ", "📝 データ一覧"])

            with tab_graph:
                filtered_df["年度_str"] = filtered_df["年度"].astype(str)
                trend_plot_df = filtered_df.sort_values(by="年度").copy()
                
                hover_col = f"{selected_trend_item}_表示用"
                trend_plot_df[hover_col] = trend_plot_df[selected_trend_item].apply(lambda x: format_value(x, selected_trend_item))
                
                fig = px.line(
                    trend_plot_df, x="年度_str", y=selected_trend_item, color="施設名", markers=True,
                    title=f"【時系列】{selected_trend_item} の年度推移",
                    labels={"年度_str": "年度", selected_trend_item: get_axis_label(selected_trend_item)},
                    hover_data={"年度_str": True, hover_col: True, selected_trend_item: False},
                    template="plotly_white"
                )
                
                fig.update_layout(
                    xaxis_title="年度", yaxis_title=get_axis_label(selected_trend_item),
                    legend_title="施設名", hovermode="x unified",
                    title_font=dict(size=16, family="Segoe UI"), font=dict(family="Segoe UI")
                )
                fig.update_traces(line=dict(width=3), marker=dict(size=8), connectgaps=False)
                
                if get_unit(selected_trend_item) == "円":
                    fig.update_yaxes(tickformat=",.0f")
                
                st.plotly_chart(fig, use_container_width=True)

            with tab_data:
                st.subheader("データ一覧")
                display_cols = ["年度", "施設名", selected_trend_item]
                formatted_df = filtered_df[display_cols].copy()
                formatted_df[selected_trend_item] = formatted_df[selected_trend_item].apply(lambda x: format_value(x, selected_trend_item))
                
                st.dataframe(formatted_df, use_container_width=True)


        # ====================================================
        # タブ2: 2指標の相関分析（散布図）
        # ====================================================
        with tab_scatter_view:
            st.subheader("2指標相関分析")
            st.write("縦軸と横軸にそれぞれ指標や基本データを割り当て、各病院の分布状況を分析します。")

            col_x, col_y = st.columns(2)
            with col_x:
                # 初期表示設定: 稼働・活動性 (Index 3) > 病床稼働率 (Index 0)
                x_item = select_item_ui("scatter_x", "▼ X軸（横軸）の設定", default_cat_idx=3, default_item_idx=0)
            with col_y:
                # 初期表示設定: 収益性 (Index 0) > 総資産対利益率(ROA) (Index 0)
                y_item = select_item_ui("scatter_y", "▼ Y軸（縦軸）の設定", default_cat_idx=0, default_item_idx=0)

            all_years = sorted(filtered_df["年度"].unique().tolist())
            selected_years = st.multiselect(
                "📅 表示する年度を選択（デフォルトは全年度）", options=all_years, default=all_years, key="scatter_year_filter"
            )

            x_desc = f"`{all_kpis[x_item]['formula']}`" if x_item in all_kpis else "(生データ)"
            y_desc = f"`{all_kpis[y_item]['formula']}`" if y_item in all_kpis else "(生データ)"
            st.info(f"👉 **横軸 (X) - {x_item}:** {x_desc}  \n👉 **縦軸 (Y) - {y_item}:** {y_desc}")

            scatter_df = filtered_df[filtered_df["年度"].isin(selected_years)].copy()
            scatter_df["年度_str"] = scatter_df["年度"].astype(str)
            valid_scatter_df = scatter_df.dropna(subset=[x_item, y_item]).copy()

            if len(valid_scatter_df) > 0:
                x_label, y_label = get_axis_label(x_item), get_axis_label(y_item)
                
                valid_scatter_df["X軸_hover"] = valid_scatter_df[x_item].apply(lambda v: format_value(v, x_item))
                valid_scatter_df["Y軸_hover"] = valid_scatter_df[y_item].apply(lambda v: format_value(v, y_item))

                fig_scatter = px.scatter(
                    valid_scatter_df, x=x_item, y=y_item, color="施設名", hover_name="施設名",
                    hover_data={"年度_str": True, "X軸_hover": True, "Y軸_hover": True, x_item: False, y_item: False},
                    text="年度_str",
                    title=f"【相関図】 {x_item} × {y_item}",
                    labels={"年度_str": "年度", "X軸_hover": x_label, "Y軸_hover": y_label},
                    template="plotly_white"
                )

                fig_scatter.update_traces(
                    marker=dict(size=13, opacity=0.85, line=dict(width=1, color='DarkSlateGrey')),
                    textposition='top center'
                )

                fig_scatter.update_layout(
                    xaxis_title=x_label, yaxis_title=y_label, legend_title="施設名", font=dict(family="Segoe UI")
                )
                
                # 縦横のグリッド線を明示的にON
                fig_scatter.update_xaxes(showgrid=True, gridcolor='LightGray')
                fig_scatter.update_yaxes(showgrid=True, gridcolor='LightGray')

                if get_unit(x_item) == "円":
                    fig_scatter.update_xaxes(tickformat=",.0f")
                if get_unit(y_item) == "円":
                    fig_scatter.update_yaxes(tickformat=",.0f")

                st.plotly_chart(fig_scatter, use_container_width=True)
                
                with st.expander("📝 このデータを確認する", expanded=False):
                    sub_display_df = valid_scatter_df[["年度", "施設名", x_item, y_item]].copy()
                    sub_display_df[x_item] = sub_display_df[x_item].apply(lambda v: format_value(v, x_item))
                    sub_display_df[y_item] = sub_display_df[y_item].apply(lambda v: format_value(v, y_item))
                    st.dataframe(sub_display_df, use_container_width=True)
            else:
                st.warning("選択された年度または指標で計算可能なデータが存在しません。")

    except Exception as e:
        st.error(f"エラーが発生しました。詳細: {e}")

else:
    st.info("👈 左側のサイドバーからExcelデータをアップロードしてください。")
    st.subheader("💡 システムの特長")
    st.markdown("""
    * **財務×病院機能の実績データ**から、収益・効率・安全・稼働・生産性の高度なKPIを自動計算。
    * **スマートな2段階選択UI**で、目的の指標や生データへ迷わずアクセス。
    * **相関分析モード**で、「職員1人当たり医業収益」×「給与費率」などの戦略的なポジション分析が可能。
    """)