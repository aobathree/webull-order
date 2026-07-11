# -*- coding: utf-8 -*-
"""Webull証券 OpenAPI 日本株の成行買い発注スクリプト。

起動後の流れ:
    1. 口座残高を取得して表示
    2. 銘柄コード(4桁)を入力
    3. 株数を入力
    4. 注文内容を表示し、y を入力した場合のみ発注(成行・買い・当日限り)

必要パッケージ・config.ini は get_quotes.py と共通(README.md 参照)。
"""
import configparser
import re
import sys
import uuid
from pathlib import Path

from webullsdkcore.client import ApiClient
from webullsdkcore.common.region import Region
from webullsdkcore.exception.exceptions import ClientException, ServerException
from webullsdktrade.api import API

CONFIG_PATH = Path(__file__).parent / "config.ini"

# APIエラーコード → 日本語メッセージ
# 実際のコードには OAUTH_OPENAPI_ 等の接頭辞が付くことがあるため、後方一致で照合する
ERROR_JA = {
    "ORDER_BUYING_POWER_NOT_ENOUGH": "買付余力が不足しています。",
    "AVAILABLE_FUNDS_NOT_ENOUGH": "証拠金が不足しています。",
    "ACCOUNT_IS_DENY": "この口座は現在取引できません。",
    "ACCOUNT_NOT_FOUND": "口座が見つかりません。",
    "ACCOUNT_NOT_OPEN_SPECIFIC": "特定口座が開設されていません。config.ini の account_tax_type を GENERAL に変更してください。",
    "ACCOUNT_ONLY_CLOSE": "この口座は現在、返済(決済)注文のみ可能です。",
    "NO_TRADING_DAY": "本日は非営業日のため発注できません。",
    "NO_TRADING_TIME": "取引時間外のため発注できません。",
    "ORDER_MKT_ONLY_ALLOW_IN_CORE_TIME": "成行注文は取引時間中(ザラ場)のみ発注できます。",
    "ORDER_QTY_EXCEED_LIMIT": "注文数量が上限を超えています。",
    "ORDER_AMOUNT_EXCEED_LIMIT": "注文金額が上限を超えています。",
    "ORDER_QTY_NOT_MATCH_LOT_SIZE": "注文数量が売買単位(単元株)の倍数ではありません。",
    "ORDER_PRICE_ILLEGAL": "注文価格が不正です。",
    "TICKER_IS_HALT": "この銘柄は売買停止中のため、成行注文を発注できません。",
    "TICKER_IS_DENY": "この銘柄は現在取引できません。",
    "TICKER_ONLY_CLOSE": "この銘柄は新規建てが制限されています。",
    "TICKER_NOT_FOUND": "銘柄が見つかりません。",
    "CAN_SELL_QTY_NOT_ENOUGH": "売却可能な保有株数が不足しています。",
    "QUOTE_ASK_PRICE_IS_NULL": "気配値が取得できないため成行注文を受け付けられません。指値注文をご検討ください。",
    "CHANNEL_REJECT": "執行先の証券会社に注文が拒否されました。",
    "INVALID_TOKEN": "認証トークンが無効です。APIキーの権限・有効期限を確認してください。",
    "UNAUTHORIZED": "APIキーが無効か期限切れです。OpenAPI登録ページで確認してください。",
    "INCORRECT_SIGN": "署名の検証に失敗しました。app_secret が正しいか確認してください。",
    "IP_NOT_ALLOWED": "このIPアドレスからのアクセスは許可されていません。",
    "TOO_MANY_REQUESTS": "短時間にリクエストが集中しました。しばらく待って再実行してください。",
    "REQUEST_TOTAL_COUNT_EXCEEDED": "APIの呼び出し回数上限に達しました。",
    "ILLEGAL_PARAMETER": "リクエストパラメータが不正です。",
    "INVALID_SYMBOL": "銘柄コードが不正です。",
    "SYSTEM_ERROR": "Webull側のシステムが一時的に利用できません。しばらく待って再実行してください。",
    "INTERNAL_ERROR": "Webull側で内部エラーが発生しました。しばらく待って再実行してください。",
}


def describe_error(e):
    """SDK例外をわかりやすい日本語メッセージに変換する。"""
    if isinstance(e, ServerException):
        code = e.get_error_code() or ""
        # 接頭辞(OAUTH_OPENAPI_ 等)を考慮して後方一致で探す
        msg = None
        for key, ja in ERROR_JA.items():
            if code.endswith(key):
                msg = ja
                break
        if msg is None:
            msg = f"APIエラーが発生しました: {e.get_error_msg()}"
        detail = f"(コード: {code}"
        if e.get_request_id():
            detail += f", リクエストID: {e.get_request_id()}"
        detail += ")"
        return f"{msg} {detail}"
    if isinstance(e, ClientException):
        return (f"通信エラーが発生しました。ネットワーク接続を確認してください。"
                f"(詳細: {e.get_error_msg()})")
    return f"予期しないエラーが発生しました: {e}"


def load_credentials():
    """config.ini から app_key / app_secret / account_tax_type を読み込む。"""
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
    tax_type = cfg.get("webull", "account_tax_type", fallback="GENERAL").strip()
    if not app_key or "YOUR_APP_KEY" in app_key:
        sys.exit("エラー: config.ini に有効な app_key が設定されていません。")
    if not app_secret or "YOUR_APP_SECRET" in app_secret:
        sys.exit("エラー: config.ini に有効な app_secret が設定されていません。")
    if tax_type not in ("GENERAL", "SPECIFIC"):
        sys.exit("エラー: account_tax_type は GENERAL または SPECIFIC を指定してください。")
    return app_key, app_secret, tax_type


def get_account_id(api):
    """口座一覧を取得し、最初の口座の account_id を返す。"""
    try:
        res = api.account_v2.get_account_list()
    except (ServerException, ClientException) as e:
        sys.exit(f"口座一覧を取得できませんでした。\n{describe_error(e)}")
    if res.status_code != 200:
        sys.exit(f"口座一覧を取得できませんでした。(HTTP {res.status_code})")
    accounts = res.json()
    if not accounts:
        sys.exit("利用可能な口座がありません。")
    acc = accounts[0]
    print(f"口座番号   : {acc.get('account_number')}")
    print(f"口座種別   : {acc.get('account_type')}")
    return acc["account_id"]


def print_balance(api, account_id):
    """口座残高を取得して表示する。"""
    try:
        res = api.account_v2.get_account_balance(account_id)
    except (ServerException, ClientException) as e:
        sys.exit(f"口座残高を取得できませんでした。\n{describe_error(e)}")
    if res.status_code != 200:
        sys.exit(f"口座残高を取得できませんでした。(HTTP {res.status_code})")
    bal = res.json()
    print("\n===== 口座残高 =====")
    print(f"現金残高   : {bal.get('total_cash_balance')} "
          f"{bal.get('total_asset_currency', 'JPY')}")
    print(f"評価損益   : {bal.get('total_unrealized_profit_loss')}")
    for ca in bal.get("account_currency_assets", []):
        print(f"[{ca.get('currency')}] 現金残高: {ca.get('cash_balance')}  "
              f"買付余力: {ca.get('buying_power')}  "
              f"評価損益: {ca.get('unrealized_profit_loss')}")
    print("====================\n")


def input_symbol(api):
    """銘柄コード(4桁)を入力させ、銘柄情報を確認して返す。"""
    while True:
        code = input("銘柄コード(4桁)を入力してください: ").strip()
        if not re.fullmatch(r"\d{4}", code):
            print("  → 4桁の数字で入力してください。")
            continue
        try:
            res = api.instrument.get_instrument(code, "JP_STOCK")
        except (ServerException, ClientException) as e:
            print(f"  → 銘柄情報を取得できませんでした。{describe_error(e)}")
            continue
        if res.status_code != 200:
            print(f"  → 銘柄情報の取得に失敗しました。(HTTP {res.status_code})")
            continue
        instruments = res.json()
        if not instruments:
            print(f"  → 銘柄コード {code} が見つかりません。")
            continue
        inst = instruments[0]
        print(f"  銘柄: {inst.get('name')} ({inst.get('symbol')} / "
              f"{inst.get('exchange_code')})")
        return code, inst


def input_quantity():
    """株数を入力させて返す。"""
    while True:
        qty = input("株数を入力してください: ").strip()
        if not qty.isdigit() or int(qty) <= 0:
            print("  → 正の整数で入力してください。")
            continue
        if int(qty) % 100 != 0:
            ans = input("  → 東証の売買単位は通常100株です。このまま続けますか? (y/n): ")
            if ans.strip().lower() != "y":
                continue
        return qty


def confirm_and_place(api, account_id, symbol, name, qty, tax_type):
    """注文内容を表示し、確認後に発注する。"""
    print("\n===== 注文内容の確認 =====")
    print(f"銘柄     : {symbol} {name}")
    print(f"売買     : 買い")
    print(f"注文種別 : 成行")
    print(f"株数     : {qty}")
    print(f"執行条件 : 当日限り (DAY)")
    print(f"口座区分 : {tax_type}")
    print("==========================")
    ans = input("この内容で発注しますか? (y/n): ").strip().lower()
    if ans != "y":
        print("発注をキャンセルしました。")
        return

    client_order_id = uuid.uuid4().hex
    new_orders = {
        "client_order_id": client_order_id,
        "symbol": symbol,
        "instrument_type": "EQUITY",
        "market": "JP",
        "order_type": "MARKET",
        "quantity": qty,
        "support_trading_session": "N",
        "side": "BUY",
        "time_in_force": "DAY",
        "entrust_type": "QTY",
        "account_tax_type": tax_type,
    }
    try:
        res = api.order_v2.place_order(account_id=account_id, new_orders=new_orders)
    except (ServerException, ClientException) as e:
        print("\n×× 発注できませんでした ××")
        print(describe_error(e))
        return
    if res.status_code == 200:
        result = res.json()
        print("\n○○ 発注が完了しました ○○")
        print(f"注文ID          : {result.get('order_id')}")
        print(f"クライアント注文ID: {result.get('client_order_id')}")
    else:
        print("\n×× 発注できませんでした ××")
        print(f"(HTTP {res.status_code}) {res.text}")


def main():
    app_key, app_secret, tax_type = load_credentials()
    api = API(ApiClient(app_key, app_secret, Region.JP.value))

    account_id = get_account_id(api)
    print_balance(api, account_id)

    symbol, inst = input_symbol(api)
    qty = input_quantity()
    confirm_and_place(api, account_id, symbol, inst.get("name", ""), qty, tax_type)


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, EOFError):
        print("\n中断しました。発注は行われていません。")
        sys.exit(130)
    except Exception as e:  # 想定外のエラーでもTracebackは出さない
        print(f"\n予期しないエラーが発生しました: {type(e).__name__}: {e}")
        sys.exit(1)
