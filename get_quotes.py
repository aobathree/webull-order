# -*- coding: utf-8 -*-
"""Webull証券 OpenAPI で日本株の直近株価(EODバー)を取得するスクリプト。

対象銘柄:
    4063 信越化学工業
    8058 三菱商事
    5713 住友金属鉱山

必要パッケージ:
    pip install webull-python-sdk-core webull-python-sdk-mdata webull-python-sdk-trade

使い方:
    1. config.ini.sample を config.ini にコピーし、app_key / app_secret を記入
    2. python get_quotes.py
"""
import configparser
import sys
import unicodedata
from pathlib import Path

from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region
from webullsdktrade.api import API

# 取得したい銘柄コード(東証)
SYMBOLS = {
    "4063": "信越化学工業",
    "8058": "三菱商事",
    "5713": "住友金属鉱山",
}

CONFIG_PATH = Path(__file__).parent / "config.ini"


def disp_width(s):
    """全角文字を幅2として文字列の表示幅を返す。"""
    return sum(2 if unicodedata.east_asian_width(c) in "FWA" else 1 for c in s)


def pad(s, width):
    """表示幅ベースで左詰めパディングする。"""
    return s + " " * max(0, width - disp_width(s))


def rpad(s, width):
    """表示幅ベースで右詰めパディングする。"""
    return " " * max(0, width - disp_width(s)) + s


def load_credentials():
    """config.ini から app_key / app_secret を読み込む。"""
    if not CONFIG_PATH.exists():
        sys.exit(
            "エラー: config.ini が見つかりません。\n"
            "config.ini.sample を config.ini にコピーし、"
            "app_key / app_secret を記入してください。"
        )
    cfg = configparser.ConfigParser()
    cfg.read(CONFIG_PATH, encoding="utf-8")
    app_key = cfg.get("webull", "app_key", fallback="").strip()
    app_secret = cfg.get("webull", "app_secret", fallback="").strip()
    if not app_key or "YOUR_APP_KEY" in app_key:
        sys.exit("エラー: config.ini に有効な app_key が設定されていません。")
    if not app_secret or "YOUR_APP_SECRET" in app_secret:
        sys.exit("エラー: config.ini に有効な app_secret が設定されていません。")
    return app_key, app_secret


def main():
    app_key, app_secret = load_credentials()
    api = API(ApiClient(app_key, app_secret, Region.JP.value))

    # 1) 銘柄コード → instrument_id の解決
    res = api.instrument.get_instrument(",".join(SYMBOLS), "JP_STOCK")
    if res.status_code != 200:
        sys.exit(f"銘柄情報の取得に失敗しました: HTTP {res.status_code} {res.text}")

    # instrument_id は文字列に正規化しておく(レスポンス間で型が揺れるため)
    instruments = {str(i["instrument_id"]): i for i in res.json()}
    if not instruments:
        sys.exit("銘柄情報が0件でした。銘柄コードを確認してください。")

    # 2) instrument_id で直近のEOD(日足)株価を取得
    res = api.market_data.get_eod_bar(
        instrument_ids=",".join(instruments), count=1
    )
    if res.status_code != 200:
        sys.exit(f"株価の取得に失敗しました: HTTP {res.status_code} {res.text}")

    header = (pad("コード", 6) + " " + pad("銘柄名", 16) + " "
              + pad("日時(UTC)", 30)
              + rpad("始値", 10) + " " + rpad("高値", 10) + " "
              + rpad("安値", 10) + " " + rpad("終値", 10) + " "
              + rpad("出来高", 12))
    print(header)
    print("-" * disp_width(header))
    for entry in res.json():
        inst = instruments.get(str(entry.get("instrument_id")), {})
        symbol = inst.get("symbol", "?")
        name = SYMBOLS.get(symbol, inst.get("name", ""))
        for bar in entry.get("bars", []):
            print(pad(symbol, 6) + " " + pad(name, 16) + " "
                  + pad(bar["time"], 30)
                  + f"{bar['open']:>10} {bar['high']:>10} {bar['low']:>10} "
                  f"{bar['close']:>10} {bar['volume']:>12}")


if __name__ == "__main__":
    main()
