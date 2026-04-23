# IRB-in-Hurry

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-15%20passed-brightgreen.svg)](#測試)
[![Forms](https://img.shields.io/badge/IRB%20forms-43%2F43-brightgreen.svg)](#表單涵蓋範圍)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

[和信治癌中心醫院](https://www.kfsyscc.org/) IRB（人體試驗委員會）送審文件自動化產生工具。

填入 YAML 設定檔中的研究資料，執行一行指令，即可產生所有必要的 IRB 送審表單 Word 文件 — 簽名後即可送出。

[English README](README.md)

---

## 為什麼要做這個

人體試驗委員會（IRB）是醫學研究史上最重要的發明之一。它誕生於紐倫堡審判（1947年）的灰燼之中，經由赫爾辛基宣言（1964年）與貝爾蒙特報告（1979年）確立制度化。IRB 的存在，是為了確保沒有任何人在未經知情同意、適當風險評估與倫理監督的情況下被納入研究。這些是不可妥協的原則。塔斯基吉事件、731 部隊，以及無數醫學實驗的黑暗歷史，都在提醒我們為什麼需要它。

**但在某個時間點，官僚體制吞噬了初衷。**

原本是為了保護受試者的制度，已經僵化成一場文書馬拉松。光是在[和信治癌中心醫院](https://www.kfsyscc.org/human/common_files/1)，研究者就必須面對 **11 類送審類別**、**43 種以上的表單** — 每一份都有自己的版本號、格式要求和勾選慣例。一個單純的回溯性病歷審查（最低風險、不接觸病人、去識別化資料）需要填 5 份表單。臨床試驗？加倍。修正計畫書裡的一個錯字？再來 4 份。

研究者的時間是有限的。每一個花在把 IRB 編號複製貼上到 SF037 表頭的小時，就是一個沒有用來分析資料、撰寫論文、或 — 最重要的 — 照顧病人的小時。表單本身不是問題。問題是填寫它們是一種**無意義的、重複的、容易出錯的勞動**，而這種勞動應該由機器來做。

這個專案不會繞過 IRB。不會跳過倫理審查。不會自動核准任何東西。它只是用你提供的資料，填好 IRB 要求的表單，讓你可以專注在真正需要人類判斷力的部分：研究設計、風險評估，以及保護你的受試者。

> 「研究倫理在於設計，不在於文書。」

**IRB-in-Hurry：因為你的時間應該花在科學上。**

---

## 功能特色

- **涵蓋 11 類 IRB 審查**：新案、修正案、複審、期中、結案、嚴重不良反應、主持人手冊、專案進口、其他、暫停/終止、申覆
- **43 個表單產生器**：依研究類型與送審階段自動選取所需表單
- **智慧判斷**：回溯性研究自動選取簡易審查 + 免取得知情同意相關表單
- **DOCX 產生**：使用 python-docx，標楷體字型、■/□ 勾選格式
- **PDF + PNG 預覽**：轉檔後可視覺化驗證排版
- **純文字清單**：■/□ 追蹤自動產生表單與手動步驟
- **彩色儀表板**：一目了然的送審進度
- **Claude Code 技能**：AI 輔助表單準備
- **GitHub Copilot 指引與 setup workflow**：讓 Copilot cloud agent 可直接使用
- **設定檔驅動的 workflow hooks**：完整約束文件產生與轉檔步驟
- **Asset Aware MCP 轉檔後端**：可將文件輸出交給自訂命令轉成正確格式

## 表單涵蓋範圍

所有表單皆依據 [和信治癌中心醫院 IRB 網站](https://www.kfsyscc.org/human/common_files/1)實作：

| 類別 | 名稱 | 表單 | 狀態 |
|------|------|------|------|
| 新案 | [新案審查](https://www.kfsyscc.org/human/common_files/1) | SF001, SF002, SF094, SF003-005 | ■ 完成 |
| 複審 | [複審案審查](https://www.kfsyscc.org/human/common_files/2) | SF019 | ■ 完成 |
| 修正 | [修正案審查](https://www.kfsyscc.org/human/common_files/3) | SF014, SF015, SF016 | ■ 完成 |
| 期中 | [期中審查](https://www.kfsyscc.org/human/common_files/4) | SF030, SF031, SF032 | ■ 完成 |
| 結案 | [結案審查](https://www.kfsyscc.org/human/common_files/5) | SF036, SF037, SF038, SF023 | ■ 完成 |
| 不良反應 | [嚴重不良反應](https://www.kfsyscc.org/human/common_files/6) | SF079, SF044, SF074, SF080, SF024 | ■ 完成 |
| 主持人手冊 | [主持人手冊](https://www.kfsyscc.org/human/common_files/7) | SF082, SF083, SF084, SF085 | ■ 完成 |
| 專案進口 | [專案進口](https://www.kfsyscc.org/human/common_files/8) | SF066, SF067, SF068, SF093 | ■ 完成 |
| 其他 | [其他表單](https://www.kfsyscc.org/human/common_files/9) | SF076 | ■ 完成 |
| 暫停 | [計畫暫停](https://www.kfsyscc.org/human/common_files/10) | SF047, SF048 | ■ 完成 |
| 申覆 | [申覆案審查](https://www.kfsyscc.org/human/common_files/11) | SF077, SF054 | ■ 完成 |
| 同意書 | — | SF062, SF063, SF075, SF090, SF091, SF092 | ■ 完成 |

## 快速開始

```bash
# 1. 複製並安裝
git clone https://github.com/htlin222/irb-in-hurry.git
cd irb-in-hurry
make setup

# 2. 編輯 config.yml 填入研究資料
#    （或複製範例設定）
cp tests/fixtures/sample_retrospective.yml config.yml

# 2.5 KMUH 對齊建議（建議先跑新案，再進修正 / 期中 / 結案）
#    institution: kmuh
#    harness:
#      group_by_phase: true
#      phases:
#        - new
#        - amendment
#        - continuing
#        - closure

# 3. 一鍵產生所有文件
make all
```

## 使用方式

### Makefile 指令

| 指令 | 說明 |
|------|------|
| `make all` | 產生 DOCX + PDF + 儀表板 |
| `make generate` | 僅產生 DOCX 表單 |
| `make pdf` | 轉換為 PDF + PNG 預覽 |
| `make dashboard` | 顯示送審狀態 |
| `make checklist` | 檢視 ■/□ 清單 |
| `make test` | 執行測試 |
| `make clean` | 清除產生的檔案 |
| `make new` | 切換至新案審查 + 產生 |
| `make closure` | 切換至結案審查 + 產生 |
| `make amendment` | 切換至修正案審查 + 產生 |
| `make continuing` | 切換至期中審查 + 產生 |
| `make kmuh-seq` | 套用 KMUH 全流程（新案→修正→期中→結案）+ 產生 |

若沒有 `make`，也可以用：

```bash
./bin/irb new
./bin/irb kmuh-seq
./bin/irb report-kmuh
```

### 工作流程

```
config.yml → generate_all.py → output/<phase>/*.docx → convert.py → output/<phase>/*.pdf
                                                           → output/<phase>/preview/*.png
                                  checklist.md ← checklist.py
```

若啟用 harness，檔案會輸出到 `output/<phase>/` 子目錄。

KMUH 建議流程順序：
`新案` → `修正案` → `期中審查` → `結案審查`

1. **編輯 `config.yml`** — 填入研究基本資料（IRB 編號、計畫名稱、主持人、日期、研究類型）
2. **`make all`** — 產生 DOCX、轉換 PDF、顯示儀表板
3. **檢查預覽** — 確認 `output/<phase>/preview/*.png` 排版正確
4. **完成手動步驟** — 簽名、附上計畫書、依設定信箱寄送

### 設定檔結構

```yaml
study:
  irb_no: "20250801A"           # IRB 編號
  title_zh: "研究中文標題"        # 中文計畫名稱
  title_en: "English Title"     # 英文計畫名稱
  type: retrospective           # retrospective|prospective|clinical_trial
  review_type: expedited        # exempt|expedited|full_board

pi:
  name: "林協霆"                 # 計畫主持人
  dept: "腫瘤內科部／醫師"        # 單位／職稱
  email: "tmwang@kmuh.org.tw"

subjects:
  planned_n: 300                # 預計收錄人數
  consent_waiver: true          # 回溯性研究自動設為 true

phase: new                     # new|amendment|continuing|closure|sae|...

institution: kmuh             # kfsyscc（預設）或 kmuh

harness:
  group_by_phase: true
  phases:
    - new
    - amendment
    - continuing
    - closure

automation:
  hook_timeout: 120
  hooks:
    before_generate:
      - 'python -c "print(\"generate 前驗證\")"'
    before_form_generate: []
    after_form_generate: []
    after_generate: []
    before_convert: []
    before_docx_to_pdf: []
    after_docx_to_pdf: []
    before_pdf_to_png: []
    after_pdf_to_png: []
    after_convert: []
  conversion:
    backend: libreoffice       # libreoffice|asset_aware_mcp
    command: ""                # backend=asset_aware_mcp 時必填
    timeout: 120
```

### 研究類型 → 表單選取

| 研究類型 | 審查方式 | 自動選取表單 |
|---------|---------|-----------|
| 回溯性病歷審查 | 簡易審查 | SF001、SF002、SF094、SF003、SF005 |
| 前瞻性觀察研究 | 簡易/一般審查 | SF001、SF002、SF094、SF062 |
| 臨床試驗（藥品） | 一般審查 | SF001、SF002、SF094、SF063、SF090、SF022 |
| 基因研究 | 一般審查 | SF001、SF002、SF094、SF075 |

## 測試

```bash
make test
```

15 項測試涵蓋表單選取邏輯、DOCX 內容驗證、清單產生，以及新案與結案的端對端產生測試。

## 系統需求

- Python 3.10+
- [python-docx](https://python-docx.readthedocs.io/) — DOCX 產生
- [PyYAML](https://pyyaml.org/) — 設定檔解析
- [LibreOffice](https://www.libreoffice.org/) — DOCX→PDF 轉換（`brew install --cask libreoffice`）
- [poppler](https://poppler.freedesktop.org/) — PDF→PNG 預覽（`brew install poppler`）

## GitHub Copilot 整合

此專案現在也提供 GitHub Copilot 專用設定：

- [`.github/copilot-instructions.md`](.github/copilot-instructions.md) 提供與 Claude 類似的專案規範
- [`.github/workflows/copilot-setup-steps.yml`](.github/workflows/copilot-setup-steps.yml) 會為 Copilot cloud agent 預先安裝 `uv` 並同步相依套件

## Workflow Hooks 與 Asset Aware MCP

`config.yml` 中可選擇設定以下 hooks，完整約束文件流程：

- `before_generate`、`before_form_generate`、`after_form_generate`、`after_generate`
- `before_convert`、`before_docx_to_pdf`、`after_docx_to_pdf`、`before_pdf_to_png`、`after_pdf_to_png`、`after_convert`

每個 hook 執行時都會帶入環境變數，例如 `IRB_HOOK_CONFIG_PATH`、`IRB_HOOK_OUTPUT_DIR`、`IRB_HOOK_INPUT_PATH`、`IRB_HOOK_OUTPUT_PATH`、`IRB_HOOK_PHASE`、`IRB_HOOK_IRB_NO`。

若要把 DOCX→PDF 轉檔交給 [u9401066/asset-aware-mcp](https://github.com/u9401066/asset-aware-mcp)，可加入：

```yaml
automation:
  conversion:
    backend: asset_aware_mcp
    command: "your asset-aware-mcp command using IRB_HOOK_INPUT_PATH and IRB_HOOK_OUTPUT_PATH"
```

若維持 `libreoffice`，則仍使用原本的 LibreOffice 轉檔流程。

## 參考資料

- [和信治癌中心醫院 IRB 表單下載](https://www.kfsyscc.org/human/common_files/1) — 官方表單
- [紐倫堡守則（1947）](https://zh.wikipedia.org/wiki/%E7%BA%BD%E4%BC%A6%E5%A0%A1%E5%AE%88%E5%88%99) — 研究倫理基石
- [赫爾辛基宣言（1964）](https://www.wma.net/policies-post/wma-declaration-of-helsinki/) — 醫學研究倫理原則
- [貝爾蒙特報告（1979）](https://www.hhs.gov/ohrp/regulations-and-policy/belmont-report/) — 尊重、善行、正義
- [聯邦法規第 45 篇第 46 部分](https://www.hhs.gov/ohrp/regulations-and-policy/regulations/45-cfr-46/) — 美國人體試驗聯邦法規

## 授權條款

MIT
