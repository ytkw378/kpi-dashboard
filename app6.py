import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ページの設定
st.set_page_config(
    page_title="病院経営KPIダッシュボード",
    layout="wide",
    initial_sidebar_state="expanded"
)

# --- 一画面化とUI最適化のためのCSS ---
st.markdown("""
<style>
    /* 画面全体の上下左右余白を極限まで詰めて1画面に収める */
    .block-container {
        padding-top: 1.0rem !important;
        padding-bottom: 1.0rem !important;
        padding-left: 2.0rem !important;
        padding-right: 2.0rem !important;
    }
    /* サイドバー上部タイトルの装飾 */
    .sidebar-title {
        font-size: 16px !important;
        font-weight: bold;
        color: #1e3a8a;
        margin-bottom: 5px;
        line-height: 1.2;
    }
    .sidebar-desc {
        font-size: 11px !important;
        color: #4b5563;
        line-height: 1.4;
        margin-bottom: 15px;
    }
    /* サイドバー内のフォントを全体的に小さくする */
    [data-testid="stSidebar"] * {
        font-size: 13px !important;
    }
    /* フォームやセレクトボックス間の余白を小さく */
    .stSelectbox {
        margin-bottom: -10px !important;
    }
    div[data-testid="stExpander"] {
        margin-bottom: 5px !important;
    }
    div[data-testid="stHorizontalBlock"] {
        gap: 10px !important;
    }
    /* ラジオボタン（スイッチ）のデザイン調整 */
    div[role="radiogroup"] {
        margin-bottom: 10px;
        padding-bottom: 10px;
        border-bottom: 1px solid #e5e7eb;
    }
</style>
""", unsafe_allow_html=True)


# --- 定義データ群 ---

# 1. 必須の財務データ
financial_subjects = [
    "医業収益", "給与費", "材料費", "経費", "減価償却費", 
    "医業利益", "経常利益", "固定資産", "貯蔵品", "流動資産", 
    "当座資産", "総資産", "固定負債", "医業未収金", "流動負債", 
    "純資産", "委託費", "医薬品費"
]

# 2. 新設の機能データ
functional_subjects = [
    "長期借入金", "入院延患者数", "新入院患者数", "退院患者数", "入院単価", "入院稼働日数",
    "外来延患者数", "外来単価", "外来診療日数", "全職員数", "医師", "看護師", "薬剤師", "一般事務",
    "病床数", "院外処方率"
]

# 全必須入力科目の統合リスト
required_subjects = financial_subjects + functional_subjects

# 3. KPIのカテゴリ別定義（単位情報、経営的な意味、判断基準を統合）
kpi_categories = {
    "収益性": {
        "総資産対利益率(ROA)": {
            "formula": "経常利益 ÷ 総資産 × 100", "unit": "%", 
            "meaning": "病院が保有するすべての資産（医療機器、設備、病棟、運転資金など）をどれだけ効率よく活用して、最終的な「経常利益」を生み出しているかを示す総合的な投資効率の指標です。",
            "benchmark": "一般病院では 2.0%〜3.0% 以上が良好、マイナスは経営不振。設備投資の回収スピードや収益力を総合評価する財務最重要指標の1つです。",
            "calc": lambda df: (df['経常利益'] / df['総資産'].replace(0, np.nan)) * 100
        },
        "医業収益対経常利益率": {
            "formula": "経常利益 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "本業の売上高（医業収益）に対して、補助金や金利などの本業外収支も含めた「病院全体の最終的な手残り利益」の割合を示します。",
            "benchmark": "公的・自治体病院等では 3.0%〜5.0% が優良、0%未満は補助金を加味しても赤字を意味します。病院活動のトータルの収益性を測るのに適しています。",
            "calc": lambda df: (df['経常利益'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "医業収益対医業利益率": {
            "formula": "医業利益 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "純粋な「診療活動（本業）」そのもので、どれだけ効率よく利益を生み出せているかという、純粋なコストパフォーマンスを示します。",
            "benchmark": "一般病院では 2.0%〜3.0% 以上が健全。ここがマイナスの病院は、給与費や材料費など本業を運営するコスト構造（体質）そのものに課題を抱えています。",
            "calc": lambda df: (df['医業利益'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "償却前医業利益率": {
            "formula": "(医業利益 ＋ 減価償却費) ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "実際のキャッシュ流出（口座からの引落し）を伴わない「減価償却費」を利益に足し戻し、病院が本来持っている「キャッシュを生む実質的な力」を測ります。",
            "benchmark": "8.0%〜10.0% 以上が健康。近年高額な新棟建設や機器投資を行って帳簿上の利益（医業利益）が赤字になっている病院の「稼ぐ力」を正確に評価できます。",
            "calc": lambda df: ((df['医業利益'] + df['減価償却費']) / df['医業収益'].replace(0, np.nan)) * 100
        },
        "材料費率": {
            "formula": "材料費 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "診療に用いた医療材料や消耗品の購入にかかった費用の割合です。手術やカテーテル等の診療比率（病院の機能）に連動します。",
            "benchmark": "急性期一般病院では 20%〜25% が標準。仕入れ単価の共同購入交渉や、院内在庫・期限切れによる「廃棄ロス」の徹底管理が重要となります。",
            "calc": lambda df: (df['材料費'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "医薬品費率": {
            "formula": "医薬品費 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "材料費の中でも、特に患者へ投与・処方したお薬（医薬品）にかかったコストの割合を示します。",
            "benchmark": "一般的に 15%〜20% が標準値。院外処方が進んでいる病院ほど、この比率は低くなります。ジェネリック薬の採用率向上や購買価格の見直しが管理の肝です。",
            "calc": lambda df: (df['医薬品費'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "給与費率": {
            "formula": "給与費 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "医師や看護師など全職員の人件費（給与・賞与・法定福利費）の割合。労働集約型である病院経営において最も重要かつコントロールが必須の絶対指標です。",
            "benchmark": "一般的に 50%〜55% が適正な健全ライン。60%を超えると損益分岐点が跳ね上がり高確率で経営不振になります。人員過多、または単価や稼働率の不足が原因です。",
            "calc": lambda df: (df['給与費'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "委託費率": {
            "formula": "委託費 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "清掃、給食、検体検査、システム保守などを外部に委託した費用の割合。自前でやるかアウトソーシングするか、給与費率とのトレードオフになります。",
            "benchmark": "一般病院では 5%〜8% が標準。アウトソーシングを増やした場合は、委託費率が上がる代わりに給与費率がそれ以上に下がっている必要があります。",
            "calc": lambda df: (df['委託費'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "減価償却費率": {
            "formula": "減価償却費 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "建物や高額なCT、MRI等の資産価値減少を費用化した金額の割合。どれだけ大きな投資を行っているか、その「重荷」を計る指標です。",
            "benchmark": "一般病院では 5%〜8% 程度が標準。10%を長期間超えている場合は、病院の身の丈に合わない過大な設備投資を行っているリスク（過大投資）があります。",
            "calc": lambda df: (df['減価償却費'] / df['医業収益'].replace(0, np.nan)) * 100
        },
        "1床当たり医業収益": {
            "formula": "医業収益 ÷ 病床数", "unit": "円", 
            "meaning": "病床1床（ハコとしての基本単位）が年間でどれだけ稼いだか。病床稼働率と診療単価の「掛け合わせ」の結果を評価します。",
            "benchmark": "急性期一般病棟では年間 1,500万〜2,000万円 以上、回復期・療養病棟では低めの値となります。保有する病床のポテンシャルを最大化できているかを見ます。",
            "calc": lambda df: df['医業収益'] / df['病床数'].replace(0, np.nan)
        }
    },
    "効率性": {
        "総資産回転率": {
            "formula": "医業収益 ÷ 総資産", "unit": "回", 
            "meaning": "病院全体のすべての資産が、1年間に何回転して「本業売上」に結びついたかを示す効率性の指標です。",
            "benchmark": "1.0回 以上が健全（資産と同等額の売上を1年でつくる）。遊休固定資産（動いていない病棟や機器）が多い場合、この数値が顕著に低下します。",
            "calc": lambda df: df['医業収益'] / df['総資産'].replace(0, np.nan)
        },
        "固定資産回転率": {
            "formula": "医業収益 ÷ 固定資産", "unit": "回", 
            "meaning": "土地や建物、高額医療機器などの「固定資産」に投じた資金が、どれだけ効率よく収益を生み出しているかを示します。",
            "benchmark": "1.5回〜2.0回 以上が目安。低すぎる場合は、稼働していないベッドや活用されていない医療機器があり、「過大投資」の状態であることを示唆します。",
            "calc": lambda df: df['医業収益'] / df['固定資産'].replace(0, np.nan)
        },
        "医業未収金回転期間": {
            "formula": "医業未収金 ÷ (医業収益 ÷ 12)", "unit": "か月", 
            "meaning": "診療報酬（社保・国保等から入る保険負担分）や患者窓口支払いの未回収金が、月商（1ヶ月の収益）の何か月分たまっているかを示します。",
            "benchmark": "1.0か月〜1.5か月 が標準（診療報酬は請求から2か月後に入金されるため）。2か月を超える場合は、請求ミスの多さや患者未収金の滞留をチェックします。",
            "calc": lambda df: df['医業未収金'] / (df['医業収益'].replace(0, np.nan) / 12)
        },
        "在庫回転期間": {
            "formula": "貯蔵品 ÷ (材料費 ÷ 12)", "unit": "か月", 
            "meaning": "院内に抱えている薬や診療用材料（貯蔵品）の在庫が、普段使う材料費の何ヶ月分に滞留しているかを示す「在庫保管量」の指標です。",
            "benchmark": "一般病院では 0.2か月〜0.5か月（およそ1〜2週間分）が適正。高すぎる（例えば1か月分以上ある）場合は無駄な在庫でお金を死滅させている状態（デッドストック）です。",
            "calc": lambda df: df['貯蔵品'] / (df['材料費'].replace(0, np.nan) / 12)
        }
    },
    "安全性": {
        "流動比率": {
            "formula": "流動資産 ÷ 流動負債 × 100", "unit": "%", 
            "meaning": "1年以内に支払うべき負債（短期借入、未払金など）に対して、1年以内に確実に現金化できる資金（預金、未収金等）がどれだけあるかという、短期の支払能力です。",
            "benchmark": "150% 以上が安全。100%を割り込むと、手元の現金がショートし、取引先や職員への給与支払いができなくなる「黒字倒産（資金ショート）」のリスクが極めて高くなります。",
            "calc": lambda df: (df['流動資産'] / df['流動負債'].replace(0, np.nan)) * 100
        },
        "当座比率": {
            "formula": "当座資産 ÷ 流動負債 × 100", "unit": "%", 
            "meaning": "流動資産から「すぐには売れず現金化しづらい在庫（貯蔵品）」を除き、現金や預金など「今すぐ確実に支払いに使えるお金」に絞って短期返済能力をみる超厳格な支払能力指標です。",
            "benchmark": "100% 以上が望ましい。流動比率は良くても、この当座比率が極端に低い場合は、院内の「不要な過剰在庫」が見掛けの安全性を引き上げていたに過ぎないと分かります。",
            "calc": lambda df: (df['当座資産'] / df['流動負債'].replace(0, np.nan)) * 100
        },
        "自己資本比率": {
            "formula": "純資産 ÷ 総資産 × 100", "unit": "%", 
            "meaning": "病院すべての資産のうち、銀行などから借りた金ではなく「返す必要がない自己資金（これまでの利益の蓄積など）」が占める割合。病院の「不況や災害への体力」です。",
            "benchmark": "30% 以上であれば健全。50%以上で極めて良好な自己経営。10%未満は債務超過に近づいており、不況がくるとすぐに破綻するリスク（債務リスク）を孕みます。",
            "calc": lambda df: (df['純資産'] / df['総資産'].replace(0, np.nan)) * 100
        },
        "固定比率": {
            "formula": "固定資産 ÷ 純資産 × 100", "unit": "%", 
            "meaning": "長期にわたり資金がロックされる「建物や高額医療機器（固定資産）」の購入が、返す必要のない「純資産」だけでどれだけ賄えているかを見る、長期の安全性指標です。",
            "benchmark": "100%以下 が理想（自己資本の中だけで建物を建てる）。しかし病院は巨額な施設投資を伴うため、 150%〜200% 以下であれば実務上許容範囲とされます。",
            "calc": lambda df: (df['固定資産'] / df['純資産'].replace(0, np.nan)) * 100
        },
        "固定長期適合率": {
            "formula": "固定資産 ÷ (純資産 ＋ 固定負債) × 100", "unit": "%", 
            "meaning": "土地や建物等の設備投資（固定資産）が、「返す必要のない自己資本」と「ゆっくり返せばよい長期借入金（固定負債）」の範囲内で安全に収まっているかを示します。",
            "benchmark": "100%以下 が絶対防衛ライン。もし100%を超えている場合、返済猶予が極端に短い「短期の運転資金」を切り崩して建物や機器を買っていることになり、資金繰りがいつ破綻してもおかしくない危険状態です。",
            "calc": lambda df: (df['固定資産'] / (df['純資産'] + df['固定負債']).replace(0, np.nan)) * 100
        },
        "借入金比率": {
            "formula": "長期借入金 ÷ 医業収益 × 100", "unit": "%", 
            "meaning": "ご指定の新規指標。1年間の本業売上高（医業収益）に対して、1年を超える長期の有利子借入金の総額がどの程度の規模であるか（借入金の重荷具合）を示します。",
            "benchmark": "50%以下 が良好な状態。100%（年商と同じ額の借金）を超えてくると、毎月の元金返済と金利負担が本業のキャッシュフローを激しく圧迫し始め、返済懸念が高まります。",
            "calc": lambda df: (df['長期借入金'] / df['医業収益'].replace(0, np.nan)) * 100
        }
    },
    "稼働・活動性": {
        "病床稼働率": {
            "formula": "入院延患者数 ÷ (病床数 × 入院稼働日数) × 100", "unit": "%", 
            "meaning": "保有している病床（ベッド）の稼働状況。病院というホテル業における「客室利用率」にあたり、病院の活動量と損益分岐点を左右する最重要活動性指標です。",
            "benchmark": "急性期病院では 80%〜85% 前後が適正（かつ損益分岐点）。90%を超えすぎると救急等の緊急受け入れができなくなり、70%を割り込むと固定費の重みで確実に大きな赤字が出ます。",
            "calc": lambda df: (df['入院延患者数'] / (df['病床数'] * df['入院稼働日数']).replace(0, np.nan)) * 100
        },
        "平均在院日数": {
            "formula": "入院延患者数 ÷ 新入院患者数", "unit": "日", 
            "meaning": "入院患者1人あたりが、平均して何日間その病床に滞在（入院）していたかを示します。病床の回転スピード、急性期医療の治療密度を表します。",
            "benchmark": "急性期一般病床では 14日以内、特定機能病院等では 10日前後 が標準。日本の医療報酬は入院初期ほど単価が手厚いため、在院日数を短くして回転率を上げる方が収益性が良くなります。",
            "calc": lambda df: df['入院延患者数'] / df['新入院患者数'].replace(0, np.nan)
        },
        "1日平均入院患者数": {
            "formula": "入院延患者数 ÷ 入院稼働日数", "unit": "人", 
            "meaning": "1日あたり平均して、何人の入院患者がその病院のベッドに寝ていたか（入院診療を受けたか）という実数規模です。",
            "benchmark": "病床数（病院の最大サイズ）と病床稼働率に比例します。過去やライバル病院との比較において、入院患者の実際のボリューム感を掴むために活用されます。",
            "calc": lambda df: df['入院延患者数'] / df['入院稼働日数'].replace(0, np.nan)
        },
        "1日平均外来患者数": {
            "formula": "外来延患者数 ÷ 外来診療日数", "unit": "人", 
            "meaning": "1日あたり平均して、何人の外来患者が診療を受けに来院したかを示す実数規模です。",
            "benchmark": "地域への信頼度やクリニックとの棲み分け度合いを示します。急性期総合病院では紹介・逆紹介（クリニックへ移す）を進めるため、この数を抑制する戦略を採る場合もあります。",
            "calc": lambda df: df['外来延患者数'] / df['外来診療日数'].replace(0, np.nan)
        }
    },
    "生産性・人員配置": {
        "職員1人当たり医業収益": {
            "formula": "医業収益 ÷ 全職員数", "unit": "円", 
            "meaning": "職員全員（常勤換算したすべての医師、看護師、事務等）で、1人あたり年間どれだけの収益を稼ぎ出したか。病院経営における最も本質的な「労働生産性（人員効率）」を測ります。",
            "benchmark": "急性期一般病院では年間 1,300万〜1,500万円 以上が良好。給与費率が高く赤字経営の病院でここが低い場合、「働いている人数が多すぎる（人員過剰）」か「単価/稼働率が著しく低い」ことを示します。",
            "calc": lambda df: df['医業収益'] / df['全職員数'].replace(0, np.nan)
        },
        "医師1人当たり医業収益": {
            "formula": "医業収益 ÷ 医師", "unit": "円", 
            "meaning": "本業の主役である「医師」1人あたりが、1年間にどれだけの診療収益をもたらしたかを示す医師の労働生産性指標です。",
            "benchmark": "診療科や外科の有無に大きく左右されますが、病院全体平均では 7,000万〜1億円 以上が目安。医師の効率的な診療体制（手術数や検査枠の最大化）をみるのに活用します。",
            "calc": lambda df: df['医業収益'] / df['医師'].replace(0, np.nan)
        },
        "100床当たり全職員数": {
            "formula": "全職員数 ÷ 病床数 × 100", "unit": "人", 
            "meaning": "病院の規模（100床）を基準として揃えたとき、すべての職種を合計して何名の職員が配置されているか。配置の「濃さ」を見る基本指標です。",
            "benchmark": "提供する医療の質や施設加算に直結します。急性期一般病院では 200〜300人。この数が適正を超えて多い場合は人件費（給与費率）が跳ね上がり、少なすぎると現場が過重労働になります。",
            "calc": lambda df: (df['全職員数'] / df['病床数'].replace(0, np.nan)) * 100
        },
        "100床当たり医師数": {
            "formula": "医師 ÷ 病床数 × 100", "unit": "人", 
            "meaning": "病床100床あたりの常勤換算医師数。病院全体の医療ポテンシャルや診療パワーを示します。",
            "benchmark": "急性期一般では 15〜25人、高度急性期では 40人以上。診療科のカバー範囲や夜間救急体制などの「人的キャパシティ」を競合と比較する際に強力な指標です。",
            "calc": lambda df: (df['医師'] / df['病床数'].replace(0, np.nan)) * 100
        },
        "100床当たり看護師数": {
            "formula": "看護師 ÷ 病床数 × 100", "unit": "人", 
            "meaning": "病床100床あたりの配置看護師数。最も人件費を占める職種であり、国の定める施設配置基準（急性期の7:1配置など）のクリアに直結します。",
            "benchmark": "急性期一般病棟では 100〜120人 が標準。看護師を多く配置すれば高い加算を貰えますが、人件費も増えます。看護不足の中で、いかに適切な看護配置病棟を選択するかが経営の成否を分けます。",
            "calc": lambda df: (df['看護師'] / df['病床数'].replace(0, np.nan)) * 100
        },
        "100床当たり薬剤師数": {
            "formula": "薬剤師 ÷ 病床数 × 100", "unit": "人", 
            "meaning": "病床100床あたりの薬剤師数。院内調剤、服薬指導、病棟薬剤業務における薬剤専門職のマンパワーを示します。",
            "benchmark": "一般病院では 5〜10人 が目安。病棟薬剤業務実施加算などの取得状況に連動します。院外処方を増やした（院内調剤が減った）場合、必要人数は変動します。",
            "calc": lambda df: (df['薬剤師'] / df['病床数'].replace(0, np.nan)) * 100
        },
        "100床当たり一般事務数": {
            "formula": "一般事務 ÷ 病床数 × 100", "unit": "人", 
            "meaning": "病床100床あたりの、受付、管理、医事、情報システム、経営企画などに携わる事務職員の割合です。",
            "benchmark": "15〜25人 が一般的。事務作業のデジタル化（AI・ITツール、院内レセプト等）の推進度合いや、医師や看護師を雑務から解放する「タスク・シフト」を支える体制を評価します。",
            "calc": lambda df: (df['一般事務'] / df['病床数'].replace(0, np.nan)) * 100
        },
        "看護師1人当たり入院延患者数": {
            "formula": "入院延患者数 ÷ 看護師", "unit": "人", 
            "meaning": "看護師1人（年間）が、実際の入院病棟で受け持ち、お世話した延べ入院患者数。看護現場の「実際の業務量・負荷（忙しさ）」を測ります。",
            "benchmark": "看護配置の手厚さと稼働率に大きく依存。数値が高いほど、看護師1人あたりが多数の患者を担当（高効率＝重い負担）していることを意味し、離職防止や安全管理上の目安になります。",
            "calc": lambda df: df['入院延患者数'] / df['看護師'].replace(0, np.nan)
        }
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
    elif item_name in ["入院延患者数", "新入院患者数", "退院患者数", "外来延患者数", "全職員数", "医師", "看護師", "薬剤師", "一般事務", "病床数"]:
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

def select_item_ui(key_prefix, title_text, default_cat_idx=0, default_item_idx=0, allow_none=False):
    """カテゴリ→詳細項目の2段階選択を行うUIコンポーネント（「なし」の選択を可能にする）"""
    st.markdown(f"<span style='font-size:13px; font-weight:bold;'>{title_text}</span>", unsafe_allow_html=True)
    
    categories_list = list(kpi_categories.keys()) + ["財務データ(勘定科目)", "機能データ"]
    if allow_none:
        categories_list = ["(選択なし)"] + categories_list
        default_cat_idx = default_cat_idx + 1 if default_cat_idx is not None else 0
    
    col_c, col_i = st.columns([1, 1.8])
    with col_c:
        cat = st.selectbox("大分類 (カテゴリ)", categories_list, index=default_cat_idx, key=f"{key_prefix}_cat", label_visibility="collapsed")
    
    if cat == "(選択なし)":
        with col_i:
            st.selectbox("詳細項目を選択", ["-"], disabled=True, key=f"{key_prefix}_item", label_visibility="collapsed")
        return None
        
    with col_i:
        if cat == "財務データ(勘定科目)":
            options = financial_subjects
        elif cat == "機能データ":
            options = functional_subjects
        else:
            options = list(kpi_categories[cat].keys())
        
        safe_idx = default_item_idx if default_item_idx < len(options) else 0
        item = st.selectbox("詳細項目を選択", options, index=safe_idx, key=f"{key_prefix}_item", label_visibility="collapsed")
    
    return item

def display_kpi_explanation(item_name, label_text="💡 指標解説"):
    """初学者向けの、経営上の意味と基準値を枠線付きカードで描画する"""
    if not item_name:
        return
        
    info = all_kpis.get(item_name)
    if info:
        formula = info.get("formula", "")
        meaning = info.get("meaning", "解説をロード中...")
        benchmark = info.get("benchmark", "判断基準をロード中...")
        
        st.markdown(f"""
        <div style="background-color: #f0f4f8; padding: 10px 14px; border-radius: 6px; border-left: 4px solid #1e3b8b; margin-top: 10px; margin-bottom: 5px;">
            <div style="font-weight: bold; color: #1e3b8b; font-size: 13px; margin-bottom: 4px;">{label_text}: {item_name}</div>
            <div style="font-size: 11px; margin-bottom: 3px; color: #374151;"><strong>計算式:</strong> <code>{formula}</code></div>
            <div style="font-size: 11px; margin-bottom: 3px; color: #374151; line-height: 1.4;"><strong>経営的な意味:</strong> {meaning}</div>
            <div style="font-size: 11px; color: #374151; line-height: 1.4;"><strong>判断の目安・基準:</strong> {benchmark}</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"""
        <div style="background-color: #f9fafb; padding: 10px 14px; border-radius: 6px; border-left: 4px solid #6b7280; margin-top: 10px; margin-bottom: 5px;">
            <div style="font-weight: bold; color: #4b5563; font-size: 13px; margin-bottom: 4px;">📊 基礎データ解説: {item_name}</div>
            <div style="font-size: 11px; margin-bottom: 3px; color: #4b5563; line-height: 1.4;"><strong>経営的な意味:</strong> 病院機能の実績値そのもの（生データ）です。比率を計算する分母や分子として活用されます。</div>
            <div style="font-size: 11px; color: #4b5563; line-height: 1.4;"><strong>判断の目安・基準:</strong> 実数値単体での普遍的な基準はありません。自施設の過去年度との時系列比較や、競合施設の実数差を比較する際に使用します。</div>
        </div>
        """, unsafe_allow_html=True)

# ポップアップ用の関数（データ登録状況確認）
@st.dialog("🔍 登録データ件数の確認", width="large")
def show_data_summary_dialog(df_raw, req_subjects):
    st.write("アップロードされたデータの科目ごとの登録件数（行数）を表示しています。緑色は正常、赤色はデータが存在しない科目です。")
    summary_pivot = df_raw.pivot_table(
        index="勘定科目", columns="施設名", values="金額", aggfunc="count", fill_value=0
    )
    for sub in req_subjects:
        if sub not in summary_pivot.index:
            summary_pivot.loc[sub] = 0
    
    summary_pivot = summary_pivot.reindex(req_subjects + [idx for idx in summary_pivot.index if idx not in req_subjects])
    
    def color_missing_cells(val):
        color = '#ffccd5' if val == 0 else '#e2f0d9'
        return f'background-color: {color}; color: #333;'
    
    try:
        styled_summary = summary_pivot.style.map(color_missing_cells)
    except AttributeError:
        styled_summary = summary_pivot.style.applymap(color_missing_cells)
    
    st.dataframe(styled_summary, use_container_width=True)

# --- サイドバーの設定 ---
st.sidebar.markdown('<div class="sidebar-title">🏥 病院経営 KPIダッシュボード</div>', unsafe_allow_html=True)
st.sidebar.markdown('<div class="sidebar-desc">各施設の財務データおよび病院機能データから、収益性・効率性・安全性・稼働性・生産性を多角的に比較分析します。</div>', unsafe_allow_html=True)

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
        
        # --- アップロードデータの要約（ボタン押下でポップアップ表示） ---
        if st.sidebar.button("📊 登録データ件数を確認する"):
            show_data_summary_dialog(raw_df, required_subjects)

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
            st.sidebar.warning(f"一部科目のデータが存在しません。")

        # 施設フィルター
        all_facilities = df_pivot["施設名"].unique().tolist()
        selected_facilities = st.sidebar.multiselect(
            "比較する施設を選択（デフォルトは全施設）", options=all_facilities, default=all_facilities
        )
        filtered_df = df_pivot[df_pivot["施設名"].isin(selected_facilities)].copy()

        # すべてのKPIを一括計算
        for kpi_name, kpi_info in all_kpis.items():
            filtered_df[kpi_name] = kpi_info["calc"](filtered_df)

        # --- ラジオボタンによる画面切り替えスイッチ ---
        view_mode = st.radio(
            "表示するグラフを選択",
            ["📈 ２指標の時系列比較 (ダブルY軸対応)", "📊 ２指標相関分析（マトリクス散布図）"],
            horizontal=True,
            label_visibility="collapsed"
        )

        # ====================================================
        # スイッチ1: ２指標の時系列比較
        # ====================================================
        if view_mode == "📈 ２指標の時系列比較 (ダブルY軸対応)":
            col_sel1, col_sel2 = st.columns(2)
            with col_sel1:
                selected_trend_item1 = select_item_ui("trend1", "▼ 指標1（主軸：実線）を選択", default_cat_idx=0, default_item_idx=9)
            with col_sel2:
                selected_trend_item2 = select_item_ui("trend2", "▼ 指標2（第2軸：点線）を選択", default_cat_idx=None, default_item_idx=0, allow_none=True)

            filtered_df["年度_str"] = filtered_df["年度"].astype(str)
            trend_plot_df = filtered_df.sort_values(by="年度").copy()
            
            color_palette = px.colors.qualitative.Plotly
            unique_facilities = filtered_df["施設名"].unique().tolist()
            facility_colors = {fac: color_palette[i % len(color_palette)] for i, fac in enumerate(unique_facilities)}

            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            for fac in unique_facilities:
                fac_df = trend_plot_df[trend_plot_df["施設名"] == fac]
                color = facility_colors[fac]
                
                fig.add_trace(
                    go.Scatter(
                        x=fac_df["年度_str"], y=fac_df[selected_trend_item1],
                        name=f"{fac} ({selected_trend_item1})",
                        mode="lines+markers",
                        line=dict(width=3, dash='solid', color=color),
                        marker=dict(size=7),
                        hovertemplate=f"施設名: {fac}<br>年度: %{{x}}<br>{selected_trend_item1}: %{{y}}<extra></extra>"
                    ),
                    secondary_y=False
                )
                
                if selected_trend_item2:
                    fig.add_trace(
                        go.Scatter(
                            x=fac_df["年度_str"], y=fac_df[selected_trend_item2],
                            name=f"{fac} ({selected_trend_item2})",
                            mode="lines+markers",
                            line=dict(width=3, dash='dot', color=color),
                            marker=dict(size=7),
                            hovertemplate=f"施設名: {fac}<br>年度: %{{x}}<br>{selected_trend_item2}: %{{y}}<extra></extra>"
                        ),
                        secondary_y=True
                    )

            title_text = f"【推移比較】 {selected_trend_item1}"
            if selected_trend_item2:
                title_text += f" (実線) ＆ {selected_trend_item2} (点線)"

            fig.update_layout(
                title=title_text,
                title_font=dict(size=14, family="Segoe UI"),
                font=dict(family="Segoe UI"),
                xaxis_title="年度",
                yaxis_title=get_axis_label(selected_trend_item1),
                hovermode="x unified",
                template="plotly_white",
                height=380,
                # 凡例をグラフの上部に水平配置し、右側のラベルとの干渉を防ぐ
                legend=dict(
                    orientation="h",
                    yanchor="bottom",
                    y=1.05,
                    xanchor="right",
                    x=1
                ),
                # 右側のマージンを少し広げて第2軸ラベルを見やすくする
                margin=dict(l=40, r=60, t=20, b=40)
            )
            
            fig.update_xaxes(showgrid=True, gridcolor='LightGray')
            fig.update_yaxes(showgrid=True, gridcolor='LightGray', secondary_y=False)
            
            if selected_trend_item2:
                fig.update_layout(yaxis2_title=get_axis_label(selected_trend_item2))
                fig.update_yaxes(showgrid=False, secondary_y=True)
            
            if get_unit(selected_trend_item1) == "円":
                fig.update_yaxes(tickformat=",.0f", secondary_y=False)
            if selected_trend_item2 and get_unit(selected_trend_item2) == "円":
                fig.update_yaxes(tickformat=",.0f", secondary_y=True)

            st.plotly_chart(fig, use_container_width=True)

            col_desc1, col_desc2 = st.columns(2)
            with col_desc1:
                display_kpi_explanation(selected_trend_item1, "💡 指標1解説")
            with col_desc2:
                if selected_trend_item2:
                    display_kpi_explanation(selected_trend_item2, "💡 指標2解説")

        # ====================================================
        # スイッチ2: ２指標相関分析（散布図）
        # ====================================================
        else:
            col_sel_y, col_sel_x = st.columns(2)
            with col_sel_y:
                y_item = select_item_ui("scatter_y", "▼ Y軸（縦軸）の設定", default_cat_idx=0, default_item_idx=0)
            with col_sel_x:
                x_item = select_item_ui("scatter_x", "▼ X軸（横軸）の設定", default_cat_idx=3, default_item_idx=0)

            col_years, col_empty = st.columns([2, 1])
            with col_years:
                all_years = sorted(filtered_df["年度"].unique().tolist())
                selected_years = st.multiselect(
                    "📅 表示する年度を選択", options=all_years, default=all_years, key="scatter_year_filter"
                )

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
                    title=f"【相関図】 {x_item} (横軸) × {y_item} (縦軸)",
                    labels={"年度_str": "年度", "X軸_hover": x_label, "Y軸_hover": y_label},
                    template="plotly_white"
                )

                fig_scatter.update_traces(
                    marker=dict(size=12, opacity=0.85, line=dict(width=1, color='DarkSlateGrey')),
                    textposition='top center'
                )

                fig_scatter.update_layout(
                    xaxis_title=x_label, yaxis_title=y_label, 
                    font=dict(family="Segoe UI"), height=380,
                    legend=dict(
                        orientation="h",
                        yanchor="bottom",
                        y=1.05,
                        xanchor="right",
                        x=1
                    ),
                    margin=dict(l=40, r=40, t=20, b=40)
                )
                
                fig_scatter.update_xaxes(showgrid=True, gridcolor='LightGray')
                fig_scatter.update_yaxes(showgrid=True, gridcolor='LightGray')

                if get_unit(x_item) == "円":
                    fig_scatter.update_xaxes(tickformat=",.0f")
                if get_unit(y_item) == "円":
                    fig_scatter.update_yaxes(tickformat=",.0f")

                st.plotly_chart(fig_scatter, use_container_width=True)
                
                col_exp_y, col_exp_x = st.columns(2)
                with col_exp_y:
                    display_kpi_explanation(y_item, "💡 Y軸（縦軸）指標解説")
                with col_exp_x:
                    display_kpi_explanation(x_item, "💡 X軸（横軸）指標解説")
                
            else:
                st.warning("選択された年度または指標で計算可能なデータが存在しません。")

    except Exception as e:
        st.error(f"エラーが発生しました。詳細: {e}")

else:
    st.info("👈 左側のサイドバーからExcelデータをアップロードしてください。")
    st.subheader("💡 システムの特長")
    st.markdown("""
    * **1画面最適化ビュー**: 操作性と一覧性を極限まで高めたUI。
    * **ダブルY軸比較対応**: スケールや単位の異なる2つの指標でも、1つの推移グラフ上で直感的に重ね合わせて比較可能。
    * **本格解説データベース内蔵**: グラフのすぐ下で、その指標が持つ「経営上の意味」と「判断目安・標準基準」をその場で学習可能。
    """)