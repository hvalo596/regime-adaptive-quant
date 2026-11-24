"""Thin Tushare Pro client for China futures (fut_basic, fut_daily, fut_mapping, fut_holding, trade_cal).

Design:
  * The token is read from the environment (`TUSHARE_TOKEN`) and is never written to disk or logs.
  * A `transport` callable does the actual request, so tests and the offline fallback inject a fake
    (see `fake_tushare.py`) and exercise the same paging/rate-limit code as the real path.
  * Row caps per call (measured in internal/tushare-access-check.md): fut_daily 2000, fut_mapping 5000,
    fut_holding 4000. Paging walks backwards over the date axis until a page is not full.
  * Rate limit: `max_calls_per_min` (default 150, below the measured 200/min of fut_basic/fut_holding/trade_cal).
"""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Callable

import pandas as pd

ENDPOINT = "http://api.tushare.pro"
ROW_CAPS = {"fut_daily": 2000, "fut_mapping": 5000, "fut_holding": 4000, "fut_settle": 4000, "fut_basic": 10**9, "trade_cal": 10**9}

Transport = Callable[[str, dict, str], pd.DataFrame]


class TushareError(RuntimeError):
    pass


class MissingTokenError(TushareError):
    pass


@dataclass(frozen=True)
class TushareConfig:
    token: str | None = field(default=None, repr=False)  # repr=False: never echoed into logs
    endpoint: str = ENDPOINT
    max_calls_per_min: int = 150
    timeout_s: float = 30.0
    retries: int = 4

    @classmethod
    def from_env(cls, **overrides) -> "TushareConfig":
        return cls(token=os.environ.get("TUSHARE_TOKEN") or None, **overrides)

    def require_token(self) -> str:
        if not self.token:
            raise MissingTokenError(
                "TUSHARE_TOKEN is not set in the environment. Set it as a secret/env var (it is never read from files); "
                "without it use the synthetic fallback (scripts/run_step2.py --synthetic)."
            )
        return self.token


def http_transport(config: TushareConfig) -> Transport:
    token = config.require_token()

    def call(api: str, params: dict, fields: str = "") -> pd.DataFrame:
        body = json.dumps({"api_name": api, "token": token, "params": params, "fields": fields}).encode()
        req = urllib.request.Request(config.endpoint, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=config.timeout_s) as resp:
            payload = json.loads(resp.read().decode())
        if payload.get("code") != 0:
            raise TushareError(f"{api}: code={payload.get('code')} msg={payload.get('msg')}")
        data = payload["data"]
        return pd.DataFrame(data["items"], columns=data["fields"])

    return call


class RateLimiter:
    def __init__(self, max_calls_per_min: int, clock=time.monotonic, sleep=time.sleep):
        self.min_interval = 60.0 / max(max_calls_per_min, 1)
        self._clock, self._sleep = clock, sleep
        self._last = None

    def wait(self) -> None:
        now = self._clock()
        if self._last is not None:
            gap = self.min_interval - (now - self._last)
            if gap > 0:
                self._sleep(gap)
                now = self._clock()
        self._last = now


def _prev_day(yyyymmdd: str) -> str:
    return (pd.Timestamp(yyyymmdd) - pd.Timedelta(days=1)).strftime("%Y%m%d")


class TushareClient:
    def __init__(
        self,
        config: TushareConfig | None = None,
        transport: Transport | None = None,
        sleep: Callable[[float], None] = time.sleep,
        row_caps: dict[str, int] | None = None,
    ):
        self.row_caps = {**ROW_CAPS, **(row_caps or {})}
        self.config = config or TushareConfig.from_env()
        self._transport = transport or http_transport(self.config)
        self._sleep = sleep
        self._limiter = RateLimiter(self.config.max_calls_per_min, sleep=sleep)
        self.n_calls = 0

    def query(self, api: str, fields: str = "", **params) -> pd.DataFrame:
        params = {k: v for k, v in params.items() if v is not None}
        last_err: Exception | None = None
        for attempt in range(self.config.retries):
            self._limiter.wait()
            self.n_calls += 1
            try:
                return self._transport(api, params, fields)
            except Exception as e:  # noqa: BLE001 - transport errors vary (HTTP, JSON, API code)
                last_err = e
                msg = str(e)
                if "权限" in msg or "token" in msg.lower():
                    raise
                self._sleep(min(2.0**attempt * 2.0, 30.0) + (30.0 if "频率" in msg or "每分钟" in msg else 0.0))
        raise TushareError(f"{api} failed after {self.config.retries} attempts: {last_err}")

    def _paged_back(self, api: str, date_col: str, start: str, end: str, **params) -> pd.DataFrame:
        """Walk backwards from `end` until a page is shorter than the row cap. Dedup on all columns."""
        cap = self.row_caps[api]
        pages, cur_end = [], end
        while True:
            df = self.query(api, start_date=start, end_date=cur_end, **params)
            if df.empty:
                break
            pages.append(df)
            if len(df) < cap:
                break
            oldest = df[date_col].min()
            if oldest <= start:
                break
            cur_end = _prev_day(oldest)  # one row per (ts_code, date), so no row can straddle two pages
        if not pages:
            return pd.DataFrame()
        out = pd.concat(pages, ignore_index=True).drop_duplicates()
        return out.sort_values(date_col).reset_index(drop=True)

    def fut_basic(self, exchange: str, fut_type: str = "1") -> pd.DataFrame:
        return self.query("fut_basic", exchange=exchange, fut_type=fut_type)

    def trade_cal(self, exchange: str, start: str, end: str) -> pd.DataFrame:
        return self.query("trade_cal", exchange=exchange, start_date=start, end_date=end)

    def fut_daily(self, ts_code: str, start: str = "19900101", end: str | None = None) -> pd.DataFrame:
        end = end or pd.Timestamp.today().strftime("%Y%m%d")
        return self._paged_back("fut_daily", "trade_date", start, end, ts_code=ts_code)

    def fut_mapping(self, ts_code: str, start: str = "19900101", end: str | None = None) -> pd.DataFrame:
        end = end or pd.Timestamp.today().strftime("%Y%m%d")
        return self._paged_back("fut_mapping", "trade_date", start, end, ts_code=ts_code)

    def fut_holding(self, trade_date: str, exchange: str) -> pd.DataFrame:
        """Member long/short ranking for one day and exchange. A full page means rows may have been truncated
        (4000-row cap) -- the caller gets a `truncated` attribute so this is never silent."""
        df = self.query("fut_holding", trade_date=trade_date, exchange=exchange)
        df.attrs["truncated"] = len(df) >= self.row_caps["fut_holding"]
        return df

    def fut_settle(self, trade_date: str, exchange: str) -> pd.DataFrame:
        """Exchange settlement parameters (margin rates, fees) for one day and exchange; `truncated` attr as for fut_holding."""
        df = self.query("fut_settle", trade_date=trade_date, exchange=exchange)
        df.attrs["truncated"] = len(df) >= self.row_caps["fut_settle"]
        return df
