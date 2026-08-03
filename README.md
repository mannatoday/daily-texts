# 摩拉維亞每日經文（daily-texts）

**Moravian Daily Texts • 中文版**  
以神的話開始每一天


自動抓取 [Moravian Daily Texts](https://www.moravian.org/the-daily-texts/)，將經文對應為繁體中文聖經（RCUV／和合本相關資源），翻譯當日禱告，並輸出 Markdown、HTML、純文字、JSON；可選擇產生靜態網站並部署到 GitHub Pages。

> 本專案為個人靈修整理用途，**非官方出版物**。

## 功能摘要

- 擷取當日舊約／新約守望經文、禱告與讀經進度（經文選讀）
- 經文查詢：信望愛 FHL API（`rcuv`）
- 禱告翻譯：可串接本機 Ollama、OpenAI、Anthropic、Google（複合備援）
- 輸出：`output/{YYYY-MM-DD}/daily-text.{md,html,txt,json}`
- 靜態站：`site/`（每日頁、首頁、歷日檔案、關於頁）→ GitHub Pages
- 靜態站譯本切換（頁面右上，預設 RCUV）：CUV／RCUV／CNVT／CSBT；守望經文內文隨選項切換，URL 為 `?version=RCUV`，並以 localStorage 記住偏好

## 系統需求

- Python **3.11+**
- 可選：Ollama（本機翻譯）、OpenAI／Anthropic／Google API 金鑰

## 安裝

```bash
git clone https://github.com/jyeh14/daily-texts.git
cd daily-texts

python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate

pip install -e ".[dev]"
cp .env.example .env
```

編輯 `.env`：至少設定翻譯相關選項（見下方）。離線測試可設：

```bash
TRANSLATOR=noop
# 或
TRANSLATOR=fallback
```

### 本機翻譯（建議）

```bash
ollama serve
ollama pull qwen2.5:7b
```

`.env` 範例：

```env
TRANSLATOR=composite
TRANSLATORS=local,openai,anthropic,google,fallback
LOCAL_TRANSLATOR_BASE_URL=http://127.0.0.1:11434/v1
LOCAL_TRANSLATOR_MODEL=qwen2.5:7b
```

## 使用方式

```bash
# 抓取「今日」每日經文（依 Moravian 網站當日內容）
daily-texts fetch

# 指定日期（會與網站 widget 日期比對）
daily-texts fetch --date 2026-08-01

# 覆蓋既有 output
daily-texts fetch --force

# 同時寫入 GitHub Pages 用的 site/
PUBLISHERS=static_site daily-texts fetch --force

# 本機定時執行（可選；正式每日發布已改由 GitHub Actions）
daily-texts run-scheduler
```

### 輸出位置

| 路徑 | 說明 |
|------|------|
| `output/{YYYY-MM-DD}/daily-text.md` | Markdown |
| `output/{YYYY-MM-DD}/daily-text.html` | 可閱讀 HTML |
| `output/{YYYY-MM-DD}/daily-text.txt` | 純文字 |
| `output/{YYYY-MM-DD}/daily-text.json` | JSON API 風格資料 |
| `site/{YYYY-MM-DD}.html` | 靜態站每日頁（需 `static_site`） |
| `site/index.html` | 今日入口＋最近三天 |
| `site/archive.html` | 歷日檔案（全部日期） |
| `site/about.html` | 關於頁 |

## GitHub Actions：每日發布與 Pages

預設分支為 **`master`**。每日管線已移到 Actions，不再依賴本機 `run-scheduler`。

### 1. Daily Publish（抓取 → 產生站點 → push）

工作流程：[`.github/workflows/daily-publish.yml`](.github/workflows/daily-publish.yml)

| 觸發 | 說明 |
|------|------|
| `schedule`（cron） | 預設 `0 9 * * *` 與 `0 11 * * *`（UTC）＝台北 17:00／19:00；可直接改 YAML 內 cron |
| `workflow_dispatch` | Actions 頁手動執行；可選 `force`、`expect_date` |

步驟摘要：checkout → Python 3.12 → `pip install -e .` → `daily-texts fetch`（產生 `output/` 的 md／html／txt／json，並以 `PUBLISHERS=static_site` 更新 `site/` 含 `index.html`）→ **僅在 `site/` 有變更時** commit 並 push 回 `master`。

特性：

- **冪等**：內容未變則不 commit；可安全重跑
- **翻譯失敗不中斷**：禱告維持英文（複合鏈末端 `fallback` + use case 備援）
- **網路重試**：Moravian／FHL 等 HTTP 請求依 `HTTP_MAX_RETRIES` 重試
- 日期比對：`--expect-date`（台北當日）＋`--fail-on-skip`；若網站尚未換日，當次失敗、由第二次 cron 重試
- **排程標籤**：log／commit message 會標示 `schedule:0 9 * * *`、`schedule:0 11 * * *` 或 `manual`，方便之後決定只留一個 cron

### 2. Daily Watchdog（兩次發布都失敗才告警）

工作流程：[`.github/workflows/daily-watchdog.yml`](.github/workflows/daily-watchdog.yml)

| 觸發 | 說明 |
|------|------|
| `schedule` | `0 13 * * *`（UTC）＝台北 21:00，在 09:00／11:00 之後 |
| `workflow_dispatch` | 手動檢查；可選 `expect_date` |

檢查 `site/{今日}.html` 是否存在，且 `index.html` 有連到該日。失敗時 Actions 顯示紅燈；若已設定下方郵件 Secrets，會額外寄信。

### 3. Secrets（Settings → Secrets and variables → Actions）

| Secret | 用途 |
|--------|------|
| `OPENAI_API_KEY` | 禱告翻譯（建議） |
| `ANTHROPIC_API_KEY` | 備援翻譯（可選） |
| `GOOGLE_TRANSLATE_API_KEY` | 備援翻譯（可選） |
| `MAIL_USERNAME` / `MAIL_PASSWORD` / `MAIL_TO` | Watchdog 失敗時寄信（三者都設才會寄） |
| `MAIL_FROM` / `MAIL_SERVER` / `MAIL_PORT` | 郵件可選；預設 from＝username、`smtp.gmail.com:465` |

未設定翻譯金鑰時仍會發布：禱告保留英文原文。未設定郵件 Secrets 時，Watchdog 只讓 workflow 失敗（可搭配 GitHub 失敗通知）。

### 4. GitHub Pages 部署（不變）

1. Repo **Settings → Pages → Source: GitHub Actions**
2. Daily Publish push `site/` 後，由 [`.github/workflows/pages.yml`](.github/workflows/pages.yml) 自動部署
3. 亦可本機產生後手動推送：

```bash
PUBLISHERS=static_site daily-texts fetch --force
git add site/
git commit -m "Update daily texts site"
git push origin master
```

站點說明：[`site/README.md`](site/README.md)  
公開網址範例：`https://jyeh14.github.io/daily-texts/`

## 設定重點

完整變數見 [`.env.example`](.env.example)。

| 變數 | 說明 |
|------|------|
| `PROVIDER` | 目前支援 `moravian_html` |
| `FORMATS` | 預設 `markdown,html,text,json` |
| `PUBLISHERS` | `null`、`static_site`；其餘 `line`／`email`／`telegram`／`website` 為 stub |
| `SITE_DIR` | 靜態站目錄，預設 `./site` |
| `TRANSLATOR` / `TRANSLATORS` | 單一翻譯器或複合鏈 |
| `SCHEDULE_TIMEZONE` / `SCHEDULE_HOUR` / `SCHEDULE_RETRY_HOURS` | 本機 `run-scheduler` 排程（可選） |
| `HTTP_MAX_RETRIES` / `HTTP_RETRY_BACKOFF_SECONDS` | HTTP 重試（預設 3 次、1s 指數退避） |

## 架構（簡述）

Clean Architecture（ports & adapters）：

```text
Provider → BibleService + Translator → Formatters → output/
                                         └→ Publishers（如 StaticSitePublisher → site/）
```

Publisher 概念分組：

```text
PublisherRegistry
├── File outputs（formatters → output/）
│     Markdown / HTML / Text / JSON
├── StaticSitePublisher   → GitHub Pages
├── WebsitePublisher      （stub，未來 S3／CMS）
├── EmailPublisher        （stub）
└── LinePublisher         （stub）
```

## 測試

```bash
pytest
```

## 版本紀錄

見 [CHANGELOG.md](CHANGELOG.md)。

## 授權與出處（請注意）

對外公開前請自行確認：

1. Moravian / IBOC 內容使用條款（必要時聯繫 [moravianiboc@mcnp.org](mailto:moravianiboc@mcnp.org)）
2. 聖經譯本／FHL 授權：[信望愛版權說明](https://www.fhl.net/main/fhl/fhl8.html)
3. 站內已標示非官方整理；正式轉載或商業用途請洽原文出版單位

**資料來源**

- 每日內容：[Moravian Daily Texts](https://www.moravian.org/the-daily-texts/)
- 中文經文：FHL Bible API（`version=rcuv` 等）
- 讀經連結：Bible Gateway（和合本 `CUV`）
