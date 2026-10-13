# zss_sdsu_check.py 使用說明書

在 comma four 上檢查 **ZSS**（0x23）和 **sDSU**（0x2FF）是否正常的小工具。

- **只讀不寫**：只監聽 CAN，不送任何 CAN，也不修改 `/data/openpilot`。openpilot 執行中也可以跑。
- 適用 branch：`iambluefred/openpilot` 的 `op0.11.2-zss`（Toyota Prius + ZSS + sDSU）。

---

## 1. 會檢查什麼

| 項目 | 怎麼判斷 |
|---|---|
| **0x23 ZSS** | 有沒有收到、頻率（新韌體約 98 Hz） |
| **0x25 原車角度** | 有沒有收到。只讀 `STEER_ANGLE`（1.5° 一格，不加 `STEER_FRACTION`） |
| **ZSS gain** | ZSS 角度 ÷ 原車角度的斜率。**1.00 = DBC factor 正確**；不是 1.00 時會算出建議的 factor |
| **0x2FF sDSU** | 有沒有收到；頻率 **≥ 50 Hz** 判為 **PASS** |

ZSS 角度用的 factor **直接從 comma four 上的 `toyota_zss.dbc` 讀取**，和 openpilot 用的完全一樣：

```
/data/openpilot/opendbc_repo/opendbc/dbc/toyota_zss.dbc
```

---

## 2. 檔案放哪裡

| 位置 | 路徑 |
|---|---|
| **Mac（這個 repo）** | `smartZSS/4.zssSdsuCheck/zss_sdsu_check.py` |
| **comma four：程式** | `/data/zss_sdsu_check.py` |
| **comma four：結果** | `/data/personal_settings/zss_sdsu_reports/` |

> ⚠️ **不要把程式放在 `/data/openpilot/` 裡面。**
> openpilot 更新時會執行 `git clean -xdff`，`/data/openpilot` 裡沒被 git 追蹤的檔案都會被刪掉。
> `/data/` 和 `/data/personal_settings/` 不受更新影響。

---

## 3. 使用步驟

### 3.1 把程式複製到 comma four（在 Mac 執行）

```bash
cd smartZSS/4.zssSdsuCheck
scp zss_sdsu_check.py comma@<comma-four-IP>:/data/
```

`<comma-four-IP>` 在 comma four 的 **Settings → network** 可以看到，例如 `172.20.10.3`。

### 3.2 SSH 進 comma four 執行

```bash
ssh comma@<comma-four-IP>
cd /data/openpilot
PYTHONPATH=/data/openpilot python3 /data/zss_sdsu_check.py -t 30
```

| 參數 | 意思 |
|---|---|
| `-t 30` | 跑 30 秒後自動結束 |
| 不加 `-t` | 一直跑，按 **Ctrl+C** 結束 |

### 3.3 測試時要做的事

車子發動（ON），停著就可以：

1. 方向盤**慢慢**左轉到底，再**慢慢**右轉到底，來回 2–3 次
2. 最後回正，停幾秒

（方向盤要轉超過 20° 才算得出 gain。sDSU 不用操作。）

### 3.4 把結果拿回 Mac（在 Mac 執行）

```bash
cd smartZSS/4.zssSdsuCheck
scp -r comma@<comma-four-IP>:/data/personal_settings/zss_sdsu_reports ./
open zss_sdsu_reports/
```

> 注意：`scp` 要在 **Mac 的 Terminal** 執行，不是在 comma four 上。
> 在 comma four 上執行會出現 `Permission denied (publickey)`。

---

## 4. 看懂結果

### 4.1 執行中的畫面（每 0.5 秒一行）

```
ZSS factor 0.004901594652 deg/count from /data/openpilot/opendbc_repo/opendbc/dbc/toyota_zss.dbc
  time |   ZSS 0x23 | stock 0x25 |    diff
  0.5s |     12.34° |      12.0° |  +0.34°
  1.0s |     25.10° |      25.5° |  -0.40°
```

- **diff 不會是 0**：ZSS 的 0 點是 ZSS 開機那一刻方向盤的位置，所以有固定 offset。
- **原車角度是 1.5° 一格跳**，所以 diff 會在約 ±0.75° 內跳動，這是正常的。
- 判斷方式：**轉方向盤時，diff 大致保持不變** → ZSS 正常。

### 4.2 結束時的結果

```
==== result ====
0x23 ZSS found           OK        2952 frames, 98.4 Hz
0x25 stock angle found   OK        2491 frames, 83.0 Hz
ZSS gain vs stock        INFO      1.002 (1.00 = DBC factor right; suggested factor 0.009519)
0x2FF sDSU found         OK        1516 frames
0x2FF sDSU >= 50 Hz      PASS      50.5 Hz (need >= 50 Hz)
```

| 結果 | 意思 | 處理 |
|---|---|---|
| `0x23 ... NOT FOUND` | 沒收到 ZSS | 檢查 ZSS 電源、CAN 接線、韌體 |
| `0x25 ... NOT FOUND` | 沒收到原車角度 | 檢查 comma 與車子的連接（harness） |
| `ZSS gain` 不是 1.00 | DBC factor 不對 | 把 `toyota_zss.dbc` 的 `ZORRO_STEER` factor 改成 suggested factor |
| `0x2FF ... NOT FOUND` | 沒收到 sDSU | sDSU 沒裝、沒電、或接線錯 |
| `0x2FF ... FAIL`（49.x Hz） | sDSU 頻率稍低 | sDSU 韌體設計約 52 Hz，實測 50–51 Hz。49.x Hz 多半是量測誤差，可把程式裡 `SDSU_MIN_HZ` 改成 `45` |

### 4.3 輸出檔案

每次執行在 `/data/personal_settings/zss_sdsu_reports/` 產生兩個檔：

| 檔案 | 內容 |
|---|---|
| `zss_sdsu_<日期_時間>.html` | 結果表 + 角度對照圖（藍線 = 原車 0x25，紅線 = ZSS 0x23） |
| `zss_sdsu_<日期_時間>.csv` | 每個 0x25 frame 一行：`t_s, zss_deg, stock_deg, diff_deg` |

---

## 5. 可以調整的設定（程式最上面）

| 變數 | 預設 | 說明 |
|---|---|---|
| `ZSS_DBC` | `/data/openpilot/opendbc_repo/opendbc/dbc/toyota_zss.dbc` | ZSS factor 從這個 DBC 讀 |
| `ZSS_FACTOR_DEFAULT` | `0.004901594652` | DBC 讀不到時才用 |
| `SDSU_MIN_HZ` | `50.0` | sDSU PASS 門檻 |
| `PRINT_EVERY_S` | `0.5` | 畫面多久印一行 |
| `OUT_DIR` | `/data/personal_settings/zss_sdsu_reports` | 結果存放位置 |

---

## 6. 常見問題

**Q：出現 `cannot import openpilot`**
A：要先 `cd /data/openpilot`，並在指令前加 `PYTHONPATH=/data/openpilot`。

**Q：ssh 出現 `REMOTE HOST IDENTIFICATION HAS CHANGED`**
A：IP 被別的裝置用過。在 Mac 先備份再刪掉舊的 key：
```bash
cp -p ~/.ssh/known_hosts ~/.ssh/known_hosts.bak
ssh-keygen -R <comma-four-IP>
```
