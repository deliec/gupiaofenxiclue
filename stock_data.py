"""
数据获取模块
- 实时行情：腾讯行情接口（东方财富 push2 在部分网络环境被阻断，腾讯更稳定）
- 财务指标：akshare 业绩报表（东方财富 datacenter，可用）
"""
import random
import time
from typing import Dict, Tuple, List

import requests
from requests.adapters import HTTPAdapter
import akshare as ak
import akshare.utils.request as _ak_request
import pandas as pd
import streamlit as st
from datetime import datetime


# ========== 给 akshare 请求补充浏览器 UA ==========
_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
       "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")


def _request_with_retry(
    url: str,
    params: Dict = None,
    timeout: int = 15,
    max_retries: int = 3,
    base_delay: float = 1.0,
    random_delay_range: Tuple[float, float] = (0.5, 1.5),
) -> requests.Response:
    last_exception = None
    for attempt in range(max_retries):
        try:
            with requests.Session() as session:
                adapter = HTTPAdapter(pool_connections=1, pool_maxsize=1)
                session.mount("http://", adapter)
                session.mount("https://", adapter)
                session.headers.update({"User-Agent": _UA})
                response = session.get(url, params=params, timeout=timeout)
                response.raise_for_status()
                return response
        except (requests.RequestException, ValueError) as e:
            last_exception = e
            if attempt < max_retries - 1:
                delay = base_delay * (2 ** attempt) + random.uniform(*random_delay_range)
                time.sleep(delay)
    raise last_exception


_ak_request.request_with_retry = _request_with_retry
try:
    from akshare.utils import func as _ak_func
    if hasattr(_ak_func, "request_with_retry"):
        _ak_func.request_with_retry = _request_with_retry
except Exception:
    pass


# ========== A 股代码列表 ==========
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24 * 7)
def get_stock_list() -> pd.DataFrame:
    """获取 A 股代码与名称列表"""
    df = ak.stock_info_a_code_name()
    df = df.rename(columns={"code": "code", "name": "name"})
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df


def _code_to_tencent(code: str) -> str:
    """股票代码转腾讯格式：sh/sz 前缀"""
    code = str(code).zfill(6)
    if code.startswith(("6", "9")):
        return f"sh{code}"
    return f"sz{code}"


# ========== 腾讯实时行情 ==========
@st.cache_data(show_spinner=False, ttl=60 * 5)
def get_realtime_quotes() -> pd.DataFrame:
    """通过腾讯接口批量获取 A 股实时行情"""
    stock_list = get_stock_list()
    codes = stock_list["code"].tolist()
    # 排除北交所（8/4 开头非沪深），仅保留沪深
    codes = [c for c in codes if c.startswith(("0", "3", "6"))]

    session = requests.Session()
    session.headers.update({"User-Agent": _UA})

    all_rows = []
    batch_size = 60
    for i in range(0, len(codes), batch_size):
        batch = codes[i:i + batch_size]
        q = ",".join(_code_to_tencent(c) for c in batch)
        try:
            r = session.get(f"https://qt.gtimg.cn/q={q}", timeout=10)
            r.encoding = "gbk"
            for line in r.text.strip().split(";"):
                line = line.strip()
                if not line or "=" not in line:
                    continue
                _, val = line.split("=", 1)
                val = val.strip().strip('"')
                if not val:
                    continue
                f = val.split("~")
                if len(f) < 50:
                    continue
                try:
                    row = {
                        "code": f[2],
                        "name": f[1],
                        "price": float(f[3]) if f[3] else None,
                        "pre_close": float(f[4]) if f[4] else None,
                        "open": float(f[5]) if f[5] else None,
                        "volume": float(f[6]) if f[6] else None,  # 手
                        "chg": float(f[31]) if f[31] else None,
                        "pct_chg": float(f[32]) if f[32] else None,
                        "high": float(f[33]) if f[33] else None,
                        "low": float(f[34]) if f[34] else None,
                        "amount": float(f[37]) if f[37] else None,  # 万元
                        "turnover": float(f[38]) if f[38] else None,  # %
                        "amplitude": float(f[43]) if f[43] else None,  # %
                        "pe": float(f[47]) if f[47] else None,
                        "pb": float(f[46]) if f[46] else None,
                        "market_cap_yi": float(f[44]) if f[44] else None,  # 亿
                        "float_market_cap_yi": float(f[45]) if f[45] else None,  # 亿
                    }
                    all_rows.append(row)
                except (ValueError, IndexError):
                    continue
        except Exception:
            continue
        time.sleep(0.05)

    df = pd.DataFrame(all_rows)
    if df.empty:
        return df
    # 市值单位：腾讯返回的是亿元
    df["market_cap"] = df["market_cap_yi"] * 1e8
    df["float_market_cap"] = df["float_market_cap_yi"] * 1e8
    # 补充缺失列以兼容策略模块
    for col in ["vol_ratio", "pct_chg_5min", "chg_5min", "pct_chg_60d", "pct_chg_ytd"]:
        if col not in df.columns:
            df[col] = None
    return df


# ========== 财务指标 ==========
@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_latest_financial_report() -> pd.DataFrame:
    """获取最新一期业绩报表"""
    today = datetime.today()
    quarters = []
    for y in range(today.year, today.year - 2, -1):
        for q in ["0331", "0630", "0930", "1231"]:
            quarters.append(f"{y}{q}")
    quarters = sorted(quarters, reverse=True)
    df = None
    for q in quarters:
        try:
            df = ak.stock_yjbb_em(date=q)
            if df is not None and not df.empty:
                break
        except Exception:
            continue
    if df is None or df.empty:
        return pd.DataFrame()

    rename_map = {
        "股票代码": "code",
        "股票简称": "name",
        "每股净资产": "bps",
        "净资产收益率": "roe",
        "净利润-同比增长": "profit_yoy",
        "营业总收入-同比增长": "revenue_yoy",
        "每股经营现金流量": "ocf_ps",
        "销售毛利率": "gross_margin",
        "每股收益": "eps",
    }
    df = df.rename(columns=rename_map)
    # 资产负债率不在 yjbb 里，置空
    df["debt_ratio"] = None
    keep = [c for c in rename_map.values() if c in df.columns] + ["debt_ratio"]
    df = df[keep].copy()
    for c in df.columns:
        if c not in ("code", "name"):
            df[c] = pd.to_numeric(df[c], errors="coerce")
    df["code"] = df["code"].astype(str).str.zfill(6)
    return df


@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_merged_data() -> pd.DataFrame:
    """合并实时行情与财务指标"""
    quotes = get_realtime_quotes()
    fin = get_latest_financial_report()
    if quotes.empty:
        return pd.DataFrame()
    if fin.empty:
        return quotes
    df = quotes.merge(fin.drop(columns=["name"], errors="ignore"), on="code", how="left")
    return df


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def get_stock_history(code: str, period: str = "day", adjust: str = "qfq") -> pd.DataFrame:
    """获取个股历史行情（腾讯源）
    period: min(分时), day(日K), week(周K), month(月K), year(年K)
    """
    tc_code = _code_to_tencent(code)
    adj = "qfq" if adjust == "qfq" else ("hfq" if adjust == "hfq" else "")

    if period == "min":
        # 分时数据（当日分钟线）
        try:
            r = requests.get(
                "https://web.ifzq.gtimg.cn/appstock/app/minute/query",
                params={"code": tc_code},
                timeout=15,
                headers={"User-Agent": _UA},
            )
            data = r.json()
            mins = data.get("data", {}).get(tc_code, {}).get("data", {}).get("data", [])
            if not mins:
                return pd.DataFrame()
            rows = []
            for item in mins:
                # 格式: "HHMM price" 或 [time, price]
                if isinstance(item, str):
                    parts = item.split()
                    if len(parts) >= 2:
                        rows.append({"time": parts[0], "price": float(parts[1])})
                elif isinstance(item, (list, tuple)) and len(item) >= 2:
                    rows.append({"time": str(item[0]), "price": float(item[1])})
            df = pd.DataFrame(rows)
            if df.empty:
                return df
            df["date"] = pd.to_datetime(datetime.today().strftime("%Y-%m-%d") + " " + df["time"], format="%Y-%m-%d %H%M", errors="coerce")
            df["date"] = df["date"].fillna(pd.to_datetime(datetime.today().strftime("%Y-%m-%d") + " " + df["time"], errors="coerce"))
            df["open"] = df["price"]
            df["close"] = df["price"]
            df["high"] = df["price"]
            df["low"] = df["price"]
            df["volume"] = 0
            return df[["date", "open", "close", "high", "low", "volume"]]
        except Exception:
            return pd.DataFrame()

    # 日/周/月K：腾讯 fqkline 接口
    period_map = {"day": "day", "week": "week", "month": "month", "year": "month"}
    tc_period = period_map.get(period, "day")
    start = "2010-01-01" if period in ("month", "year") else "2023-01-01"
    end = datetime.today().strftime("%Y-%m-%d")
    count = 800 if period == "day" else 600
    try:
        param = f"{tc_code},{tc_period},{start},{end},{count},{adj}"
        r = requests.get(
            "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get",
            params={"param": param},
            timeout=15,
            headers={"User-Agent": _UA},
        )
        data = r.json()
        stock_data = data.get("data", {}).get(tc_code, {})
        key = f"qfq{tc_period}" if adj else tc_period
        klines = stock_data.get(key) or stock_data.get(tc_period) or []
        if not klines:
            return pd.DataFrame()
        # 腾讯格式: [date, open, close, high, low, volume(, 换手率)]，统一只取前6列
        klines = [row[:6] for row in klines]
        df = pd.DataFrame(klines, columns=["date", "open", "close", "high", "low", "volume"])
        df["date"] = pd.to_datetime(df["date"])
        for c in ["open", "close", "high", "low", "volume"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")

        # 年K：从日K重采样
        if period == "year":
            df = df.set_index("date")
            yearly = df.resample("YE").agg({
                "open": "first", "close": "last",
                "high": "max", "low": "min", "volume": "sum",
            }).dropna()
            yearly = yearly.reset_index()
            yearly["date"] = yearly["date"].dt.year
            return yearly
        return df
    except Exception:
        return pd.DataFrame()


# ========== 个股资金流向（新浪财经）==========
@st.cache_data(show_spinner=False, ttl=60 * 30)
def get_fund_flow(code: str, period: str = "day") -> pd.DataFrame:
    """获取个股资金流向历史数据（新浪财经接口）
    period: day / week / month / year
    返回列: date, close, pct_chg, main_net, super_large_net, large_net,
            medium_net, small_net, main_pct
    金额单位：元
    """
    market = "sh" if code.startswith("6") else "sz"
    daima = f"{market}{code}"
    url = "http://vip.stock.finance.sina.com.cn/quotes_service/api/json_v2.php/MoneyFlow.ssl_qsfx_lscjfb"
    headers = {
        "User-Agent": _UA,
        "Referer": "https://finance.sina.com.cn/",
    }
    all_rows = []
    # 分页获取，每页500条，最多取4页（约2000条/8年）
    for page in range(1, 5):
        params = {"page": page, "num": 500, "sort": "opendate",
                  "asc": 0, "daima": daima}
        try:
            r = requests.get(url, params=params, timeout=15, headers=headers)
            data = r.json()
            if not data:
                break
            all_rows.extend(data)
            if len(data) < 500:
                break
        except Exception:
            break
        time.sleep(0.3)

    if not all_rows:
        return pd.DataFrame()

    rows = []
    for d in all_rows:
        try:
            super_large_net = float(d.get("r0_net", 0) or 0)
            large_net = float(d.get("r1_net", 0) or 0)
            medium_net = float(d.get("r2_net", 0) or 0)
            small_net = float(d.get("r3_net", 0) or 0)
            main_net = super_large_net + large_net
            # 主力净占比 = 主力净流入 / (主力+中单+小单 绝对值之和) 近似
            total_abs = abs(super_large_net) + abs(large_net) + abs(medium_net) + abs(small_net)
            main_pct = (main_net / total_abs * 100) if total_abs > 0 else 0
            rows.append({
                "date": d.get("opendate", ""),
                "close": float(d.get("trade", 0) or 0),
                "pct_chg": float(d.get("changeratio", 0) or 0) * 100,
                "main_net": main_net,
                "super_large_net": super_large_net,
                "large_net": large_net,
                "medium_net": medium_net,
                "small_net": small_net,
                "main_pct": main_pct,
            })
        except (ValueError, TypeError):
            continue

    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"], errors="coerce")
    df = df.dropna(subset=["date"]).sort_values("date").reset_index(drop=True)

    # 周期重采样
    if period == "day":
        return df

    df = df.set_index("date")
    agg_dict = {
        "close": "last",
        "main_net": "sum", "super_large_net": "sum", "large_net": "sum",
        "medium_net": "sum", "small_net": "sum",
        "pct_chg": "sum",
    }
    if period == "week":
        res = df.resample("W-FRI").agg(agg_dict).dropna(subset=["close"])
    elif period == "month":
        res = df.resample("ME").agg(agg_dict).dropna(subset=["close"])
    elif period == "year":
        res = df.resample("YE").agg(agg_dict).dropna(subset=["close"])
        res = res.reset_index()
        res["date"] = res["date"].dt.year
        # 重算主力净占比
        res["main_pct"] = 0.0
        return res[["date", "close", "pct_chg", "main_net", "super_large_net",
                    "large_net", "medium_net", "small_net", "main_pct"]]
    else:
        return df.reset_index()

    res = res.reset_index()
    # 重算主力净占比
    total_abs = (res["super_large_net"].abs() + res["large_net"].abs() +
                 res["medium_net"].abs() + res["small_net"].abs())
    res["main_pct"] = res["main_net"] / total_abs.replace(0, 1) * 100
    return res[["date", "close", "pct_chg", "main_net", "super_large_net",
                "large_net", "medium_net", "small_net", "main_pct"]]


def get_market_index() -> pd.DataFrame:
    """获取主要指数行情（腾讯源）"""
    index_map = {
        "sh000001": "上证指数",
        "sz399001": "深证成指",
        "sz399006": "创业板指",
        "sh000688": "科创50",
        "sh000300": "沪深300",
        "sh000905": "中证500",
    }
    q = ",".join(index_map.keys())
    try:
        r = requests.get(f"https://qt.gtimg.cn/q={q}", timeout=10,
                         headers={"User-Agent": _UA})
        r.encoding = "gbk"
        rows = []
        for line in r.text.strip().split(";"):
            line = line.strip()
            if not line or "=" not in line:
                continue
            key, val = line.split("=", 1)
            val = val.strip().strip('"')
            if not val:
                continue
            f = val.split("~")
            if len(f) < 5:
                continue
            code = key.split("_")[-1]
            rows.append({
                "code": code,
                "name": index_map.get(code, f[1]),
                "price": float(f[3]) if f[3] else None,
                "pct_chg": float(f[32]) if f[32] else None,
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()
