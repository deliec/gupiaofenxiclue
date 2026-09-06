"""
策略回测模块：对筛选出的股票组合进行简单等权回测
"""
import pandas as pd
import numpy as np
from stock_data import get_stock_history


def backtest_portfolio(codes: list, rebalance_days: int = 20, lookback: int = 250) -> pd.DataFrame:
    """
    等权组合回测
    - codes: 股票代码列表
    - rebalance_days: 调仓周期（交易日）
    - lookback: 回看交易日数
    返回每日组合净值曲线 DataFrame
    """
    if not codes:
        return pd.DataFrame()

    all_returns = []
    for code in codes[:20]:  # 最多回测前20只
        hist = get_stock_history(code)
        if hist.empty:
            continue
        hist = hist.sort_values("date").tail(lookback).copy()
        hist["ret"] = hist["close"].pct_change()
        hist = hist.set_index("date")
        all_returns.append(hist["ret"].rename(code))

    if not all_returns:
        return pd.DataFrame()

    ret_df = pd.concat(all_returns, axis=1).dropna(how="all")
    # 等权
    n = ret_df.shape[1]
    port_ret = ret_df.fillna(0).mean(axis=1)
    nav = (1 + port_ret).cumprod()
    result = pd.DataFrame({"date": nav.index, "nav": nav.values, "daily_ret": port_ret.values})
    return result


def calc_metrics(result: pd.DataFrame) -> dict:
    """计算回测绩效指标"""
    if result.empty:
        return {}
    nav = result["nav"]
    ret = result["daily_ret"].fillna(0)
    total_return = nav.iloc[-1] / nav.iloc[0] - 1
    n_days = len(result)
    annual_return = (1 + total_return) ** (252 / n_days) - 1 if n_days > 0 else 0
    annual_vol = ret.std() * np.sqrt(252)
    sharpe = annual_return / annual_vol if annual_vol > 0 else 0
    max_drawdown = ((nav / nav.cummax()) - 1).min()
    win_rate = (ret > 0).mean()
    return {
        "累计收益率": f"{total_return*100:.2f}%",
        "年化收益率": f"{annual_return*100:.2f}%",
        "年化波动率": f"{annual_vol*100:.2f}%",
        "夏普比率": f"{sharpe:.2f}",
        "最大回撤": f"{max_drawdown*100:.2f}%",
        "日胜率": f"{win_rate*100:.2f}%",
    }
