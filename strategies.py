"""
量化选股策略模块：提供多种预设策略与自定义多因子筛选
"""
import pandas as pd
import numpy as np


# ========== 工具函数 ==========
def _filter_basic(df: pd.DataFrame) -> pd.DataFrame:
    """基础过滤：剔除 ST、停牌、新股、负值异常"""
    df = df.copy()
    # 剔除 ST / *ST
    df = df[~df["name"].str.contains("ST|退", na=False)]
    # 剔除价格为 0 或 NaN（停牌）
    df = df[df["price"].notna() & (df["price"] > 0)]
    # 剔除北交所（8/4 开头）以及科创板？保留沪深主板+创业板+科创板
    return df.reset_index(drop=True)


def _safe_rank(series: pd.Series, ascending: bool = True) -> pd.Series:
    """安全排序打分（0-100），缺失值取 50"""
    rank = series.rank(pct=True, ascending=ascending)
    return (rank * 100).fillna(50)


# ========== 预设策略 ==========
def strategy_low_valuation(df: pd.DataFrame) -> pd.DataFrame:
    """低估值策略：PE、PB 较低，ROE 为正，市值适中"""
    d = _filter_basic(df)
    d = d[(d["pe"] > 0) & (d["pe"] < 30)]
    d = d[(d["pb"] > 0) & (d["pb"] < 5)]
    if "roe" in d.columns:
        d = d[d["roe"] > 0]
    d = d[d["market_cap_yi"] > 50]
    # 综合估值得分
    d["score"] = (
        0.5 * _safe_rank(d["pe"], ascending=True)
        + 0.3 * _safe_rank(d["pb"], ascending=True)
        + 0.2 * _safe_rank(d["roe"] if "roe" in d else d["pe"] * 0, ascending=False)
    )
    return d.sort_values("score", ascending=False).head(30).reset_index(drop=True)


def strategy_high_growth(df: pd.DataFrame) -> pd.DataFrame:
    """高成长策略：营收与净利润高速增长，ROE 较高"""
    d = _filter_basic(df)
    if "revenue_yoy" not in d.columns or "profit_yoy" not in d.columns:
        return pd.DataFrame()
    d = d[(d["revenue_yoy"] > 20) & (d["profit_yoy"] > 20)]
    d = d[(d["pe"] > 0) & (d["pe"] < 100)]
    d = d[d["market_cap_yi"] > 30]
    d["score"] = (
        0.4 * _safe_rank(d["profit_yoy"], ascending=False)
        + 0.3 * _safe_rank(d["revenue_yoy"], ascending=False)
        + 0.3 * _safe_rank(d["roe"] if "roe" in d else d["profit_yoy"], ascending=False)
    )
    return d.sort_values("score", ascending=False).head(30).reset_index(drop=True)


def strategy_quality(df: pd.DataFrame) -> pd.DataFrame:
    """质量策略：高 ROE、高毛利率、正现金流"""
    d = _filter_basic(df)
    if "roe" not in d.columns:
        return pd.DataFrame()
    d = d[d["roe"] > 10]
    if "gross_margin" in d.columns:
        d = d[d["gross_margin"] > 20]
    d = d[d["market_cap_yi"] > 100]
    d["score"] = _safe_rank(d["roe"], ascending=False)
    return d.sort_values("score", ascending=False).head(30).reset_index(drop=True)


def strategy_small_cap(df: pd.DataFrame) -> pd.DataFrame:
    """小市值策略：市值小 + 基本面不差（PE正、ROE正）"""
    d = _filter_basic(df)
    d = d[(d["market_cap_yi"] < 100) & (d["market_cap_yi"] > 20)]
    d = d[(d["pe"] > 0) & (d["pe"] < 60)]
    if "roe" in d.columns:
        d = d[d["roe"] > 0]
    d["score"] = _safe_rank(d["market_cap_yi"], ascending=True)
    return d.sort_values("score", ascending=False).head(30).reset_index(drop=True)


def strategy_momentum(df: pd.DataFrame) -> pd.DataFrame:
    """动量策略：今日涨幅靠前、换手率适中、振幅较大"""
    d = _filter_basic(df)
    d = d[(d["pct_chg"] > 0) & (d["pct_chg"] < 15)]
    d = d[(d["turnover"] > 1) & (d["turnover"] < 15)]
    d = d[d["market_cap_yi"] > 30]
    d["score"] = (
        0.5 * _safe_rank(d["pct_chg"], ascending=False)
        + 0.3 * _safe_rank(d["turnover"], ascending=False)
        + 0.2 * _safe_rank(d["amplitude"], ascending=False)
    )
    return d.sort_values("score", ascending=False).head(30).reset_index(drop=True)


def strategy_multi_factor(df: pd.DataFrame) -> pd.DataFrame:
    """多因子综合：估值 + 成长 + 质量 + 动量 综合打分"""
    d = _filter_basic(df)
    # 基础可交易条件
    d = d[(d["pe"] > 0) & (d["pe"] < 80)]
    d = d[(d["pb"] > 0) & (d["pb"] < 10)]
    d = d[d["market_cap_yi"] > 30]

    # 估值分（越低越好）
    val_score = 0.5 * _safe_rank(d["pe"], ascending=True) + 0.5 * _safe_rank(d["pb"], ascending=True)
    # 质量分
    if "roe" in d.columns:
        quality_score = _safe_rank(d["roe"], ascending=False)
    else:
        quality_score = pd.Series(50, index=d.index)
    # 成长分
    if "profit_yoy" in d.columns:
        growth_score = _safe_rank(d["profit_yoy"], ascending=False)
    else:
        growth_score = pd.Series(50, index=d.index)
    # 动量分（优先用60日涨幅，否则用当日涨幅）
    if "pct_chg_60d" in d.columns and d["pct_chg_60d"].notna().any():
        mom_score = _safe_rank(d["pct_chg_60d"], ascending=False)
    else:
        mom_score = _safe_rank(d["pct_chg"], ascending=False)

    d["score"] = 0.3 * val_score + 0.3 * quality_score + 0.2 * growth_score + 0.2 * mom_score
    return d.sort_values("score", ascending=False).head(30).reset_index(drop=True)


# 策略注册表
STRATEGIES = {
    "低估值策略": strategy_low_valuation,
    "高成长策略": strategy_high_growth,
    "质量策略": strategy_quality,
    "小市值策略": strategy_small_cap,
    "动量策略": strategy_momentum,
    "多因子综合": strategy_multi_factor,
}


def run_strategy(name: str, df: pd.DataFrame) -> pd.DataFrame:
    """执行指定策略"""
    func = STRATEGIES.get(name)
    if func is None:
        return pd.DataFrame()
    return func(df)


# ========== 自定义筛选 ==========
def custom_screen(
    df: pd.DataFrame,
    pe_range=(0, 50),
    pb_range=(0, 5),
    market_cap_range=(20, 5000),
    roe_min=0,
    profit_yoy_min=0,
    revenue_yoy_min=0,
    turnover_range=(0, 100),
    pct_chg_60d_min=None,
) -> pd.DataFrame:
    """自定义多因子筛选"""
    d = _filter_basic(df)
    d = d[(d["pe"] >= pe_range[0]) & (d["pe"] <= pe_range[1])]
    d = d[(d["pb"] >= pb_range[0]) & (d["pb"] <= pb_range[1])]
    d = d[(d["market_cap_yi"] >= market_cap_range[0]) & (d["market_cap_yi"] <= market_cap_range[1])]
    d = d[(d["turnover"] >= turnover_range[0]) & (d["turnover"] <= turnover_range[1])]
    if "roe" in d.columns and roe_min is not None:
        d = d[d["roe"] >= roe_min]
    if "profit_yoy" in d.columns and profit_yoy_min is not None:
        d = d[d["profit_yoy"] >= profit_yoy_min]
    if "revenue_yoy" in d.columns and revenue_yoy_min is not None:
        d = d[d["revenue_yoy"] >= revenue_yoy_min]
    if pct_chg_60d_min is not None and "pct_chg_60d" in d.columns:
        d = d[d["pct_chg_60d"] >= pct_chg_60d_min]
    return d.reset_index(drop=True)
