# Changelog

本專案遵循 [Keep a Changelog](https://keepachangelog.com/zh-TW/1.1.0/) 精神，版本號採 [Semantic Versioning](https://semver.org/lang/zh-TW/)。

## [Unreleased]

### Added

- GitHub Actions 每日發布工作流程（`.github/workflows/daily-publish.yml`）：cron + 手動觸發，產生 `site/` 後 commit／push 至 `master`；run／commit 標示 schedule 來源
- Daily Watchdog（`.github/workflows/daily-watchdog.yml`）：兩次 publish 之後檢查當日頁；失敗可選 SMTP 寄信
- HTTP 請求重試（`HTTP_MAX_RETRIES`／`HTTP_RETRY_BACKOFF_SECONDS`）用於 Moravian、FHL、Google Translate
- CLI：`--expect-date`、`--fail-on-skip`（供 CI 使用）
- 靜態站多譯本守望經文：fetch 時向 FHL 查 CUV／RCUV／CNVT／CSBT（CCBT 無 FHL 來源時暫用英文），嵌入 `day-data`；頁面以 `?version=`＋picker＋localStorage 切換內文（預設 RCUV）
- 主日「本週守望經文」（Watchword for the week）：解析、多譯本中文化並顯示於 HTML／Markdown／純文字／JSON 輸出

### Fixed

- Moravian 解析：主日版面（教會年／Watchword for the week）不再誤把非經文段當 OT／NT；改以 BibleGateway 連結定位守望經文
- 經文參考中文化支援逗號分段（如 `Psalm 145:8-9,14-21` → `詩篇 145:8–9,14–21`）

### Planned

- 真實 `LinePublisher` / `EmailPublisher`
- `WebsitePublisher`（S3／CMS 等，有別於靜態站）
- 授權合規閘道（`REQUIRE_LICENSE_ACK`）與正式 attribution
- 其他 Provider（如 Email inbox）

---

## [0.1.0] — 2026-08-01

首個可用的中文每日經文管線與靜態站。

### Added

- Moravian HTML sidebar Provider：抓取當日日期、舊約／新約、禱告、詩篇與讀經進度
- FHL RCUV 經文查詢；支援經節範圍與逗號經節（如 `Galatians 5:16,17`）
- 經文參考中文化（含跨章範圍）；經文選讀連結 Bible Gateway 和合本（`CUV`）
- 禱告翻譯複合鏈：Local（Ollama）→ OpenAI → Anthropic → Google → Fallback
- 輸出格式：Markdown、HTML、純文字、JSON（`output/{date}/`）
- 純文字／各格式中文日期標題（如 `2026 年 8 月 1 日（星期六）`）與【經文選讀】區塊
- `StaticSitePublisher`：`site/{YYYY-MM-DD}.html`、`index.html`、`about.html`、`styles.css`
- 靜態站閱讀體驗：前後日導覽、歷日檔案、關於頁、深色模式與列印樣式、無障礙 skip link
- GitHub Actions Pages 部署（`.github/workflows/pages.yml`，分支 `master`）
- CLI：`daily-texts fetch`、`daily-texts run-scheduler`（含日期重試時段）
- Publisher stub：`line`、`email`、`telegram`、`website`；預設 `null`

### Notes

- 品牌名稱：**摩拉維亞每日經文**（Moravian Daily Texts • 中文版）
- 本版本以個人靈修／開發用途為主；對外發布前請確認內容與譯本授權

[Unreleased]: https://github.com/jyeh14/daily-texts/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/jyeh14/daily-texts/releases/tag/v0.1.0
