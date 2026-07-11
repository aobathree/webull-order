# webull-order

Webull証券(ウィブル証券)の OpenAPI を用いて日本株の株価取得・発注を行うプロジェクトです。

現在は以下の銘柄の直近株価(EOD/日足)取得に対応しています。

| コード | 銘柄名 |
| ------ | ------------ |
| 4063   | 信越化学工業 |
| 8058   | 三菱商事     |
| 5713   | 住友金属鉱山 |

## 必要環境

- **Python 3.11**(執筆時点・2026年7月)
  - Webull Python SDK (v0.1.18) が依存する `grpcio==1.51.1` は Python 3.12以降のビルド済みwheelを提供していません
  - また、SDK内蔵の旧版 requests が Python 3.13 で削除された標準ライブラリ `cgi` を使用しているため、3.13では動作しません
- **[uv](https://docs.astral.sh/uv/)** の使用を推奨
  - Python 3.11 本体の取得から仮想環境の作成・パッケージ導入までを高速に自動化できます
- ウィブル証券の口座および OpenAPI の App Key / App Secret

## セットアップ

### 1. uv のインストール(未導入の場合)

PowerShell:

```powershell
winget install astral-sh.uv
```

### 2. Python 3.11 仮想環境の作成と SDK のインストール

```powershell
cd D:\webull-order
uv venv --python 3.11
uv pip install webull-python-sdk-core webull-python-sdk-quotes-core webull-python-sdk-mdata webull-python-sdk-trade
```

### 3. APIキーの発行

1. [OpenAPI登録ページ](https://www.webull.co.jp/center/manage-app) にログインし、アプリを登録
2. 発行された **App Key** と **App Secret** を控える(App Secret は再表示できない場合があります)

### 4. config.ini の作成

`config.ini.sample` を `config.ini` にコピーし、実際の値を記入します。

```ini
[webull]
app_key = 実際のApp Key
app_secret = 実際のApp Secret
region = jp
```

`config.ini` は `.gitignore` で除外済みです。**絶対にコミットしないでください。**
キーが漏洩した場合は、OpenAPI登録ページで直ちに再発行してください。

## 実行

```powershell
uv run get_quotes.py
```

出力例:

```
コード 銘柄名           日時(UTC)                           始値       高値       安値       終値       出来高
--------------------------------------------------------------------------------------------------------------
4063   信越化学工業     2026-07-09T15:00:00.000+0000     7255.00    7403.00    7216.00    7320.00      8345700
8058   三菱商事         2026-07-09T15:00:00.000+0000      7340.0     7366.0     7224.0     7275.0      2142600
5713   住友金属鉱山     2026-07-09T15:00:00.000+0000      4441.0     4444.0     4361.0     4409.0      7058000
```

## 処理の流れ

1. `/instrument/list` で銘柄コード → `instrument_id` を解決(category=`JP_STOCK`)
2. `/market-data/eod-bars` で `instrument_id` の直近EOD(日足)データを取得

## トラブルシューティング

| 症状 | 原因と対処 |
| ---- | ---------- |
| `pip install` で grpcio のビルドエラー | Python 3.12以降を使用している。uv で Python 3.11 環境を作成する |
| `ModuleNotFoundError: No module named 'cgi'` | Python 3.13 を使用している。同上 |
| `Failed to hardlink files` 警告 | uvのキャッシュと仮想環境が別ドライブにあるだけで無害。気になる場合は環境変数 `UV_LINK_MODE=copy` を設定 |

## 参考リンク

- [Quick Start](https://developer.webull.co.jp/api-doc/prepare/start/)
- [Get Instruments](https://developer.webull.co.jp/api-doc/quote/get/instrument)
- [End-of-day Market](https://developer.webull.co.jp/api-doc/quote/get/eod-bars)
- [Dictionary](https://developer.webull.co.jp/api-doc/develop/dictionary)
