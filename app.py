"""
A股量化选股系统 - 主界面
大盘概览 → 策略选股 → 个股K线详情 → 策略回测
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px

from stock_data import get_merged_data, get_market_index, get_stock_history
from strategies import STRATEGIES, run_strategy, custom_screen
from backtest import backtest_portfolio, calc_metrics

st.set_page_config(page_title="A股量化选股", page_icon="📈", layout="wide")


def is_dark_theme():
    """检测当前 Streamlit 主题是否为暗色（处理 Dark / Light / System 三种情况）"""
    base = st.get_option("theme.base")
    if base == "dark":
        return True
    if base == "light":
        return False
    # System 主题：通过背景色判断
    bg = st.get_option("theme.backgroundColor") or "#0e1117"
    bg = bg.lstrip("#")
    if len(bg) >= 6:
        try:
            r = int(bg[0:2], 16)
            g = int(bg[2:4], 16)
            b = int(bg[4:6], 16)
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            return luminance < 128
        except ValueError:
            pass
    return True  # 默认暗色


# 根据主题选择配色
if is_dark_theme():
    C = {
        "bg": "#0b1220",
        "bg2": "#0f1a2e",
        "card": "#1e293b",
        "card_alt": "#172033",
        "text": "#e2e8f0",
        "text_dim": "#94a3b8",
        "border": "rgba(148,163,184,0.15)",
        "border_strong": "rgba(148,163,184,0.25)",
        "primary": "#3b82f6",
        "up": "#ef4444",
        "down": "#22c55e",
        "shadow": "rgba(0,0,0,0.25)",
        "shadow_hover": "rgba(0,0,0,0.35)",
        "pos_bg": "rgba(239,68,68,0.15)",
        "neg_bg": "rgba(34,197,94,0.15)",
        "hover_bg": "rgba(59,130,246,0.08)",
        "scroll_track": "rgba(15,23,42,0.3)",
        "scroll_thumb": "rgba(100,116,139,0.5)",
    }
else:
    C = {
        "bg": "#f8fafc",
        "bg2": "#e2e8f0",
        "card": "#ffffff",
        "card_alt": "#f1f5f9",
        "text": "#0f172a",
        "text_dim": "#64748b",
        "border": "rgba(0,0,0,0.1)",
        "border_strong": "rgba(0,0,0,0.2)",
        "primary": "#3b82f6",
        "up": "#dc2626",
        "down": "#16a34a",
        "shadow": "rgba(0,0,0,0.08)",
        "shadow_hover": "rgba(0,0,0,0.12)",
        "pos_bg": "rgba(220,38,38,0.1)",
        "neg_bg": "rgba(22,163,74,0.1)",
        "hover_bg": "rgba(59,130,246,0.08)",
        "scroll_track": "rgba(0,0,0,0.05)",
        "scroll_thumb": "rgba(0,0,0,0.2)",
    }

# ========== 全局样式：根据主题注入实际颜色值 ==========
st.markdown(
    f"""
    <style>
    /* ===== 全局背景与排版 ===== */
    body, .stApp {{
        background: linear-gradient(160deg, {C['bg']} 0%, {C['bg2']} 45%, {C['bg']} 100%) !important;
        background-attachment: fixed !important;
    }}
    .block-container {{
        padding-top: 4rem;
        padding-bottom: 2rem;
        max-width: 1400px;
    }}
    h1, h2, h3, h4 {{
        font-family: "PingFang SC", "Microsoft YaHei", "Helvetica Neue", sans-serif;
        letter-spacing: 0.02em;
        color: {C['text']} !important;
    }}
    [data-testid="stHorizontalBlock"] {{ gap: 1rem; }}

    /* ===== 涨跌色（A股惯例：红涨绿跌） ===== */
    .up   {{ color: {C['up']}; font-weight: 700; }}
    .down {{ color: {C['down']}; font-weight: 700; }}

    /* ===== 大盘指数卡片 ===== */
    .metric-card {{
        background: {C['card']};
        border: 1px solid {C['border']};
        border-radius: 14px;
        padding: 16px 18px;
        text-align: center;
        backdrop-filter: blur(8px);
        box-shadow: 0 4px 20px {C['shadow']}, inset 0 1px 0 rgba(255,255,255,0.04);
        transition: transform 0.2s, box-shadow 0.2s;
    }}
    .metric-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 8px 28px {C['shadow_hover']}, inset 0 1px 0 rgba(255,255,255,0.06);
    }}
    .metric-card .label {{
        color: {C['text_dim']}; font-size: 0.82rem; margin-bottom: 4px;
        letter-spacing: 0.05em;
    }}
    .big-number {{
        font-size: 1.7rem; font-weight: 800; color: {C['text']};
        font-variant-numeric: tabular-nums;
    }}

    /* ===== 个股信息卡片 ===== */
    .info-card {{
        background: {C['card']};
        border: 1px solid {C['border']};
        border-radius: 12px;
        padding: 12px 16px;
        backdrop-filter: blur(6px);
        transition: border-color 0.2s;
    }}
    .info-card:hover {{ border-color: {C['primary']}; }}
    .info-card .label {{ color: {C['text_dim']}; font-size: 0.78rem; letter-spacing: 0.04em; }}
    .info-card .value {{
        font-size: 1.35rem; font-weight: 700; color: {C['text']};
        font-variant-numeric: tabular-nums; margin-top: 2px;
    }}

    /* ===== 按钮美化 ===== */
    .stButton > button {{
        border-radius: 10px !important;
        font-weight: 600 !important;
        letter-spacing: 0.03em;
        transition: all 0.2s !important;
    }}
    .stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {C['primary']}, #2563eb) !important;
        border: none !important;
        box-shadow: 0 4px 14px rgba(59,130,246,0.35) !important;
    }}
    .stButton > button[kind="primary"]:hover {{
        transform: translateY(-1px);
        box-shadow: 0 6px 20px rgba(59,130,246,0.5) !important;
    }}

    /* ===== 输入框 / 下拉框 / 滑块 主题适配 ===== */
    .stTextInput input, .stSelectbox [data-baseweb="select"] > div,
    .stNumberInput input {{
        background: {C['card']} !important;
        border-color: {C['border_strong']} !important;
        color: {C['text']} !important;
        border-radius: 10px !important;
    }}
    .stSlider > div > div > div {{ background: rgba(59,130,246,0.3) !important; }}
    .stSlider [data-testid="stTickBar"] {{ color: {C['text_dim']}; }}

    /* ===== 标题与分隔线 ===== */
    hr {{ border-color: {C['border']} !important; }}
    .stCaption {{ color: {C['text_dim']} !important; }}

    /* ===== 回测 expander ===== */
    .streamlit-expanderHeader {{
        background: {C['card']} !important;
        border-radius: 10px !important;
        border: 1px solid {C['border']} !important;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="正在加载A股数据…", ttl=60 * 30)
def load_all():
    return get_merged_data()


# ========== 标题 ==========
st.title("📈 A股量化选股系统")
st.caption("数据来源：腾讯行情 + akshare财务  ·  仅供学习研究，不构成投资建议")

# ========== 大盘概览 ==========
idx = get_market_index()
if not idx.empty:
    cols = st.columns(len(idx))
    for i, row in idx.iterrows():
        with cols[i % len(cols)]:
            chg = row["pct_chg"]
            color = "up" if chg >= 0 else "down"
            st.markdown(
                f"<div class='metric-card'><div class='label'>{row['name']}</div>"
                f"<div class='big-number'>{row['price']:.2f}</div>"
                f"<div class='{color}' style='font-weight:600'>{chg:+.2f}%</div></div>",
                unsafe_allow_html=True,
            )
    st.divider()

# ========== 主区域：左侧选股，右侧结果 ==========
col_ctrl, col_result = st.columns([1, 3])

with col_ctrl:
    st.subheader("选股方式")
    mode = st.radio(" ", ["预设策略", "自定义筛选"], label_visibility="collapsed")

    if mode == "预设策略":
        strategy_name = st.selectbox("选择策略", list(STRATEGIES.keys()))
        st.markdown(
            {
                "低估值策略": "PE/PB 较低、ROE 为正、市值适中",
                "高成长策略": "营收与净利润增速 >20%、PE 合理",
                "质量策略": "高 ROE、高毛利率、大市值",
                "小市值策略": "市值 20–100 亿、基本面不差",
                "动量策略": "今日涨幅靠前、换手率适中、振幅较大",
                "多因子综合": "估值+成长+质量+动量 综合打分",
            }.get(strategy_name, "")
        )
        run = st.button("开始选股", type="primary", width="stretch")
    else:
        st.write("设置筛选条件：")
        pe_range = st.slider("市盈率 PE", 0, 100, (0, 50))
        pb_range = st.slider("市净率 PB", 0.0, 15.0, (0.0, 5.0))
        mcap_range = st.slider("总市值（亿）", 10, 10000, (50, 2000))
        roe_min = st.number_input("ROE 最小值(%)", value=0.0)
        profit_yoy_min = st.number_input("净利润同比增速(%)", value=0.0)
        turnover_range = st.slider("换手率(%)", 0.0, 50.0, (0.0, 20.0))
        run = st.button("开始筛选", type="primary", width="stretch")

# ========== 执行选股 ==========
with col_result:
    if run or "last_result" in st.session_state:
        df = load_all()
        if mode == "预设策略":
            result = run_strategy(strategy_name, df)
        else:
            result = custom_screen(
                df,
                pe_range=pe_range,
                pb_range=pb_range,
                market_cap_range=mcap_range,
                roe_min=roe_min,
                profit_yoy_min=profit_yoy_min,
                turnover_range=turnover_range,
            )
        st.session_state["last_result"] = result
        st.session_state["last_name"] = strategy_name if mode == "预设策略" else "自定义筛选"

    if "last_result" in st.session_state:
        result = st.session_state["last_result"]
        name = st.session_state.get("last_name", "")
        if result.empty:
            st.warning("没有符合条件的股票，请调整条件后重试。")
        else:
            st.subheader(f"{name} · 筛选结果（{len(result)} 只）")
            show_cols = [c for c in
                ["code", "name", "price", "pct_chg", "pe", "pb", "market_cap_yi",
                 "roe", "profit_yoy", "revenue_yoy", "turnover", "amplitude", "score"]
                if c in result.columns]
            disp = result[show_cols].copy()
            disp = disp.rename(columns={
                "code": "代码", "name": "名称", "price": "现价", "pct_chg": "涨跌幅%",
                "pe": "PE", "pb": "PB", "market_cap_yi": "市值(亿)",
                "roe": "ROE%", "profit_yoy": "净利润增速%", "revenue_yoy": "营收增速%",
                "turnover": "换手率%", "amplitude": "振幅%", "score": "得分",
            })

            # ====== streamlit-aggrid：红涨绿跌 + 行点击 + 列排序 ======
            from st_aggrid import AgGrid, GridOptionsBuilder, JsCode

            color_col_set = {"涨跌幅%", "净利润增速%", "营收增速%", "ROE%"} & set(disp.columns)

            # 搜索过滤
            search_q = st.text_input("搜索代码 / 名称", value="", placeholder="输入代码或名称快速筛选…", label_visibility="collapsed")
            if search_q.strip():
                q = search_q.strip().lower()
                mask = disp["代码"].astype(str).str.lower().str.contains(q) | disp["名称"].astype(str).str.lower().str.contains(q)
                disp = disp[mask].reset_index(drop=True)

            all_codes = result["code"].tolist()

            # 最终选中代码
            sel_code = st.session_state.get("selected_code", "")
            if sel_code not in all_codes:
                sel_code = str(result["code"].iloc[0]) if len(result) > 0 else ""
            st.session_state["selected_code"] = sel_code

            # 构建 AgGrid
            gb = GridOptionsBuilder.from_dataframe(disp)
            gb.configure_default_column(
                sortable=True,
                resizable=True,
                filter=False,
                editable=False,
            )
            # 显式设置每列可排序
            for col in disp.columns:
                gb.configure_column(col, sortable=True)

            # 红涨绿跌单元格样式
            cell_style_jscode = JsCode("""
            function(params) {
                var v = parseFloat(params.value);
                if (v > 0) return {color: '#ef4444', backgroundColor: 'rgba(239,68,68,0.15)'};
                if (v < 0) return {color: '#22c55e', backgroundColor: 'rgba(34,197,94,0.15)'};
                return null;
            }
            """)
            for col in color_col_set:
                gb.configure_column(col, cellStyle=cell_style_jscode)

            # 数值格式
            fmt_cols = [c for c in disp.columns if disp[c].dtype != object and c not in ("代码", "名称")]
            for col in fmt_cols:
                gb.configure_column(col, type=["numericColumn"], valueFormatter="(params.value==null)?'—':Number(params.value).toFixed(2)")

            # 行选择
            gb.configure_selection(selection_mode="single", use_checkbox=False)
            # 高亮选中行
            gb.configure_grid_options(
                rowStyle=JsCode("""
                function(params) {
                    if (params.node.isSelected()) {
                        return {backgroundColor: 'rgba(59,130,246,0.2)'};
                    }
                    return null;
                }
                """)
            )

            grid_options = gb.build()
            response = AgGrid(
                disp,
                gridOptions=grid_options,
                height=min(36 * len(disp) + 40, 520),
                theme="streamlit",
                fit_columns_on_grid_load=True,
                allow_unsafe_jscode=True,
                key="stock_aggrid",
            )

            # 从选中行更新代码
            if response.selected_rows is not None and len(response.selected_rows) > 0:
                ev_code = str(response.selected_rows.iloc[0].get("代码", ""))
                if ev_code in all_codes:
                    st.session_state["selected_code"] = ev_code
                    sel_code = ev_code

            sel_row = result[result["code"] == sel_code]
            if not sel_row.empty:
                sel_row = sel_row.iloc[0]
                sel_name = sel_row.get("name", "")
                st.subheader(f"🔍 个股详情 · {sel_name}（{sel_code}）")
                st.caption("点击上方表格行切换股票")

                # 最新信息卡片
                info_cols = st.columns(4)
                info_items = [
                    ("现价", f"{sel_row.get('price', 0):.2f}"),
                    ("涨跌幅", f"{sel_row.get('pct_chg', 0):+.2f}%"),
                    ("市盈率(PE)", f"{sel_row.get('pe', 0):.2f}" if pd.notna(sel_row.get('pe')) else "—"),
                    ("市净率(PB)", f"{sel_row.get('pb', 0):.2f}" if pd.notna(sel_row.get('pb')) else "—"),
                    ("总市值(亿)", f"{sel_row.get('market_cap_yi', 0):.1f}"),
                    ("换手率", f"{sel_row.get('turnover', 0):.2f}%"),
                    ("振幅", f"{sel_row.get('amplitude', 0):.2f}%"),
                    ("ROE", f"{sel_row.get('roe', 0):.2f}%" if pd.notna(sel_row.get('roe')) else "—"),
                ]
                for ic, (label, val) in zip(info_cols, info_items[:4]):
                    ic.markdown(f"<div class='info-card'><div class='label'>{label}</div><div class='value'>{val}</div></div>", unsafe_allow_html=True)
                for ic, (label, val) in zip(info_cols, info_items[4:]):
                    ic.markdown(f"<div class='info-card'><div class='label'>{label}</div><div class='value'>{val}</div></div>", unsafe_allow_html=True)

                # K线周期切换
                period_map = {"分时": "min", "日K": "day", "周K": "week", "月K": "month", "年K": "year"}
                period_label = st.radio("K线周期", list(period_map.keys()), horizontal=True)
                period = period_map[period_label]

                with st.spinner("正在加载K线数据…"):
                    kdf = get_stock_history(sel_code, period=period)

                if kdf.empty:
                    st.warning("暂无K线数据。")
                else:
                    # 根据 Streamlit 主题选择图表配色
                    if is_dark_theme():
                        chart_bg = "rgba(15,23,42,0.4)"
                        grid_color = "rgba(148,163,184,0.08)"
                        zero_color = "rgba(148,163,184,0.15)"
                        font_color = "#cbd5e1"
                        title_color = "#f1f5f9"
                    else:
                        chart_bg = "rgba(255,255,255,0.6)"
                        grid_color = "rgba(0,0,0,0.06)"
                        zero_color = "rgba(0,0,0,0.1)"
                        font_color = "#334155"
                        title_color = "#0f172a"
                    theme_layout = dict(
                        paper_bgcolor="rgba(0,0,0,0)",
                        plot_bgcolor=chart_bg,
                        font=dict(color=font_color, family="PingFang SC, Microsoft YaHei"),
                        xaxis=dict(gridcolor=grid_color, zerolinecolor=zero_color),
                        yaxis=dict(gridcolor=grid_color, zerolinecolor=zero_color),
                    )
                    if period == "min":
                        # 分时图：折线
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=kdf["date"], y=kdf["close"],
                            mode="lines", name="价格",
                            line=dict(color="#f87171", width=1.8),
                            fill="tozeroy", fillcolor="rgba(248,113,113,0.12)",
                        ))
                        fig.update_layout(
                            title=dict(text=f"{sel_name}（{sel_code}）分时图", font=dict(size=16, color=title_color)),
                            xaxis_title="时间", yaxis_title="价格",
                            height=450, margin=dict(l=10, r=10, t=50, b=10),
                            hovermode="x unified", **theme_layout,
                        )
                    else:
                        # K线图：蜡烛图
                        fig = go.Figure(data=[go.Candlestick(
                            x=kdf["date"],
                            open=kdf["open"], high=kdf["high"],
                            low=kdf["low"], close=kdf["close"],
                            name="K线",
                            increasing_line_color="#f87171", decreasing_line_color="#4ade80",
                            increasing_fillcolor="#f87171", decreasing_fillcolor="#4ade80",
                        )])
                        # 成交量柱状图
                        colors = ["#f87171" if c >= o else "#4ade80"
                                  for c, o in zip(kdf["close"], kdf["open"])]
                        fig.add_trace(go.Bar(
                            x=kdf["date"], y=kdf["volume"],
                            name="成交量", yaxis="y2",
                            marker_color=colors, marker_opacity=0.5,
                        ))
                        fig.update_layout(
                            title=dict(text=f"{sel_name}（{sel_code}）{period_label}", font=dict(size=16, color=title_color)),
                            xaxis_title="日期" if period != "year" else "年份",
                            yaxis_title="价格",
                            yaxis2=dict(title="成交量", overlaying="y", side="right", showgrid=False,
                                        gridcolor=grid_color),
                            height=500, margin=dict(l=10, r=10, t=50, b=10),
                            xaxis_rangeslider_visible=False,
                            hovermode="x unified", **theme_layout,
                        )
                    st.plotly_chart(fig, width="stretch")

            # ========== 回测 ==========
            st.divider()
            with st.expander("📊 对筛选结果进行回测（等权组合）"):
                top_n = st.slider("取前 N 只回测", 3, 20, 10)
                if st.button("运行回测"):
                    codes = result["code"].head(top_n).tolist()
                    with st.spinner("正在回测…"):
                        bt = backtest_portfolio(codes, lookback=250)
                    if bt.empty:
                        st.error("回测失败：无法获取历史数据。")
                    else:
                        metrics = calc_metrics(bt)
                        mcols = st.columns(len(metrics))
                        for mc, (k, v) in zip(mcols, metrics.items()):
                            mc.metric(k, v)
                        fig = px.line(bt, x="date", y="nav", title="组合净值曲线",
                                      labels={"date": "日期", "nav": "净值"})
                        # 回测图表主题适配
                        if is_dark_theme():
                            bt_bg = "rgba(15,23,42,0.4)"
                            bt_grid = "rgba(148,163,184,0.08)"
                            bt_font = "#cbd5e1"
                        else:
                            bt_bg = "rgba(255,255,255,0.6)"
                            bt_grid = "rgba(0,0,0,0.06)"
                            bt_font = "#334155"
                        fig.update_layout(
                            height=350, margin=dict(l=10, r=10, t=50, b=10),
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor=bt_bg,
                            font=dict(color=bt_font),
                            xaxis=dict(gridcolor=bt_grid),
                            yaxis=dict(gridcolor=bt_grid),
                        )
                        fig.update_traces(line=dict(color="#3b82f6", width=2))
                        st.plotly_chart(fig, width="stretch")
    else:
        st.info("👈 请在左侧选择策略并点击「开始选股」")

# ========== 页脚 ==========
st.divider()
st.caption("⚠️ 本工具仅用于量化策略学习与研究，历史表现不代表未来收益，投资有风险。")
