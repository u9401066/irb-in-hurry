# IRB-in-Hurry

> 架構翻新中：新的 `irb_harness` 核心以「組織文件 → 可追溯契約 → 文件／網站 adapter」為模型，
> 預設契約為 KMUH；舊有 `scripts/generators` 仍屬 KFSYSCC 相容層，尚不可視為 KMUH 正式表單。

[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-56%20passed-brightgreen.svg)](#測試)
[![Documentation](https://img.shields.io/badge/docs-GitHub%20Pages-087f8c.svg)](https://u9401066.github.io/irb-in-hurry/)
[![Forms](https://img.shields.io/badge/IRB%20forms-43%2F43-brightgreen.svg)](#表單涵蓋範圍)
[![License: MIT](https://img.shields.io/badge/license-MIT-yellow.svg)](LICENSE)

[和信治癌中心醫院](https://www.kfsyscc.org/) IRB（人體試驗委員會）送審文件自動化產生工具。

填入 YAML 設定檔中的研究資料，執行一行指令，即可產生所有必要的 IRB 送審表單 Word 文件 — 簽名後即可送出。

[English README](README.md)

[說明網站](https://u9401066.github.io/irb-in-hurry/)提供 KMUH 契約架構、證據狀態與 Browser MCP 安全邊界的快速導覽。

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
- **GitHub Pages 說明站**：清楚標示已實作能力、待驗證 KMUH 證據與安全操作方式

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

# 3. KFSYSCC 舊流程才可使用一鍵產生；KMUH 使用 organization contract
make all
uv run irb-contract show
```

### 新契約核心（KMUH 預設）

```bash
# 驗證並查看內建 KMUH 契約、來源與待取回資產
uv run irb-contract show

# 依案件類型、審查軌與流程事件列出適用需求及證據就緒狀態
uv run irb-contract requirements \
  --submission-type new \
  --review-track general \
  --workflow-event submit_new

# 把另一組織提供的 PDF／DOCX／Markdown 編譯成契約草稿與 evidence index
uv run irb-contract compile \
  --institution example \
  --name "Example IRB" \
  --document /path/to/instructions.pdf \
  --document /path/to/forms.docx \
  --output output/contracts/example.yml

# 依內建 KMUH 契約下載一個官方來源，建立不可變快取、evidence manifest
# 與 organizations/kmuh/contract.yml workspace override
uv run irb-contract sync-sources \
  --source kmuh_sop_02_01

# 多次同步既有 override 時，明確允許更新；舊版會先存入 cache snapshot
uv run irb-contract sync-sources \
  --contract organizations/kmuh/contract.yml \
  --form-set kmuh_general_new \
  --update-output

# 人工檢閱 manifest 的 context/hash 後，把規則綁到確切 span；工具會再次核對
# 來源 byte SHA-256 與 span ID，然後才把 locator_status 升為 verified
uv run irb-contract map-evidence \
  --contract organizations/kmuh/contract.yml \
  --manifest '.irb-source-cache/kmuh/manifests/<sha256>.json' \
  --transition administrative_intake \
  --source kmuh_sop_02_01 \
  --span 'kmuh:payload:<sha12>:L35' \
  --update-output

# 需求定義由審閱者明確撰寫；不得把 status 或 evidence_refs 塞進此檔案
cat > /tmp/kmuh-requirement.yml <<'YAML'
requirement_id: kmuh_new_submission_checklist
title: 新案送審文件清單與相應附件
kind: document
required: true
value_type: file
applies_to:
  submission_types: [new]
  review_tracks: [general, expedited]
  workflow_events: [submit_new]
YAML

# 將人工定義的需求綁到人工挑選、且重新核對過的官方 evidence spans
uv run irb-contract map-requirement \
  --contract organizations/kmuh/contract.yml \
  --definition /tmp/kmuh-requirement.yml \
  --manifest '.irb-source-cache/kmuh/manifests/<sha256>.json' \
  --source kmuh_sop_02_01 \
  --span 'kmuh:payload:<sha12>:L35' \
  --replace-requirement \
  --update-output
```

編譯器只做可重現的擷取、雜湊與 line/char locator；不會自行猜測送審規則。規則需由人員依 evidence index 審核後加入契約。
`sync-sources` 只接受契約中宣告的 HTTPS 資產，查詢值會在 manifest 中遮蔽；下載成功仍標為
`retrieved_needs_rule_mapping`，不等同內容已人工驗證。快取位於被 git 忽略的 `.irb-source-cache/`。
工作流程規則只有在 `map-evidence` 同時核對契約來源雜湊、manifest 雜湊與 span ID 後，
才會成為 `locator_status: verified`；工具不會自行猜測應選哪一段。
需求規則同理由 `map-requirement` 寫入：definition 是人員做出的判斷，工具只驗證所選來源與 locator，
並保存 definition、manifest、span text 的雜湊。內建 KMUH 契約先列出 9 項候選需求，全部維持
`needs_evidence`，直到官方檔案實際取回並逐段審核；這些候選項不是已證實的院方規則。

### KMUH eIRB Browser MCP

Browser MCP 不接收帳號或密碼，只會 attach 到人類已登入的專用 Chrome profile。設定方式與安全邊界見
[`docs/kmuh-browser-mcp.md`](docs/kmuh-browser-mcp.md)。

```bash
uv run irb-contract browser-status
uv run irb-contract session-status --site kmuh_eirb
uv run irb-contract map-page --site kmuh_eirb

# 人工比對 mapping 後，才把 portal_field requirement 綁到一個欄位
uv run irb-contract bind-requirement-control \
  --contract organizations/kmuh/contract.yml \
  --requirement '<portal-field-requirement-id>' \
  --site kmuh_eirb \
  --mapping-sha256 '<mapping-sha256>' \
  --control-id '<control-id>' \
  --update-output
```

`map-page` 將 mapping 寫入 git 忽略的 `.irb-web-artifacts/`；保留可操作 selector 與風險類別，
但不保存欄位值、頁面本文或原始 label。送出、撤案、終止與刪除操作沒有 MCP tool。
若同時開了多個高醫分頁，先用 MCP 的 `irb_browser_list_pages` 取得 `page_ref`，再在上述
CLI 加上 `--page-ref c0pN`，可避免選到舊登入頁。
唯讀按鈕操作也預設關閉；人工檢閱 content-addressed mapping 後，另設
`IRB_WEB_CLICK_MODE=reviewed` 才能呼叫 `irb_click_reviewed_control`，而且每次仍需對指定
`control_id` 明確確認。live fingerprint 或風險分類不同就會拒絕執行。
`bind-requirement-control` 只接受 `portal_field` 與 input/select/textarea；頁面 mapping 的雜湊、
selector、風險分類及人工審查決策會寫入契約，但原始 label 和欄位值不會寫入。

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
| `make kmuh-seq` | 已停用；KMUH 是事件分支流程，不是固定線性序列 |
| `make contract-show` | 驗證 KMUH 預設契約與來源就緒度 |
| `make browser-status` | 檢查人類已登入 Chrome 的 CDP bridge |
| `make session-status` | 檢查目前 KMUH eIRB 頁面的登入狀態 |
| `make web-mcp` | 啟動 human-login-gated eIRB MCP |

> `make all`、`make kmuh-seq` 與 `scripts/generators` 是 KFSYSCC 舊相容層。
> 若設定 `institution: kmuh`，程式會明確拒絕沿用 KFSYSCC SF 表單；KMUH 請使用新的 organization contract 流程。

若沒有 `make`，也可以用：

```bash
./bin/irb new
./bin/irb report-kmuh
uv run irb-contract show
```

### 工作流程

```
config.yml → generate_all.py → output/<phase>/*.docx → convert.py → output/<phase>/*.pdf
                                                           → output/<phase>/preview/*.png
                                  checklist.md ← checklist.py
```

若啟用 harness，檔案會輸出到 `output/<phase>/` 子目錄。

KMUH 流程由事件分支構成：新案可能反覆複審；核准後可各自提出變更、持續審查、
安全事件／不遵從報告，最後才可能結案、終止或撤案。以 organization contract 的
`workflow.transitions` 為準，不把它壓成固定線性順序。

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

56 項測試涵蓋契約驗證、來源雜湊與 locator、人工審核 requirement／portal 欄位綁定、
安全下載／ZIP 解包、去識別化頁面 mapping、Browser MCP 安全政策，以及舊 KFSYSCC
表單選取、GitHub Pages 說明站與端對端產生測試。

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
