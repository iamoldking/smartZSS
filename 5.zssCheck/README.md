# ZSS check（readzss.py + zss_check.py）使用說明書

在 **Mac** 執行一個指令，就會自動完成下面 4 件事：

1. SSH 連到 comma four / comma three
2. 測試 10 秒，Mac 畫面即時顯示 **ZSS 0x23** 和**原車 0x25** 的角度
3. 把結果（HTML + CSV）抓回 Mac
4. 打開 HTML 報告（結果表 + 角度圖）

- **只讀不寫**：只監聽 CAN，不送任何 CAN，也不修改 `/data/openpilot`。openpilot 執行中也可以跑。
- 適用：openpilot **0.9.8** 和 **0.11.x**（例如 `iambluefred/openpilot` 的 `op0.11.2-zss`）。
- ZSS factor 固定用 `0.004901594652` deg/count（`toyota_zss.dbc` 的值）。
- 版本：`zss_check.py` v2.0、`readzss.py` v2.1（合併了舊的 `4.zssSdsuCheck_v34`～`4.zssCheck_v36`）。

---

## 1. 檔案

| 檔案 | 在哪裡跑 | 做什麼 |
|---|---|---|
| `readzss.py` | **Mac** | scp → ssh 執行 → scp 抓回 → 打開報告 |
| `zss_check.py` | **comma device**（自動複製到 `/data/zss_check.py`） | 讀 CAN 0x23 / 0x25，產生 HTML + CSV |

兩個檔案要放在同一個資料夾。

> `zss_check.py` 放在 `/data/`，不放在 `/data/openpilot/` 裡面：
> openpilot 更新時會 `git clean -xdff`，`/data/openpilot` 裡沒被 git 追蹤的檔案會被刪掉。

---

## 2. 事前準備（只要做一次）

Mac 要能用 SSH key 登入 comma device。先確認這行可以登入：

```bash
ssh comma@172.20.10.6
```

`172.20.10.6` 是範例，請換成你 comma device 的 IP（comma 上 **Settings → Network** 可以看到）。

---

## 3. 使用步驟

### 3.1 在 Mac 執行

```bash
cd ~/github/bluefred/op0112zss/smartZSS/5.zssCheck
python3 readzss.py 172.20.10.6
```

| 參數 | 意思 |
|---|---|
| `172.20.10.6` | comma device 的 IP（必填） |
| `-t 30` | 測 30 秒（預設 10 秒） |
| `-u comma` | SSH 帳號（預設 `comma`） |
| `--no-open` | 不要自動打開 HTML |

### 3.2 測試時要做的事

看到這行就開始轉方向盤：

```
>>> Turn the steering wheel left and right now (more than 30 deg each way) <<<
```

車子 ON，停著就可以：方向盤**左轉 30° 以上，再右轉 30° 以上**，來回 1–2 次。
（原車角度範圍要超過 20° 才算得出 gain。）

### 3.3 結果放在哪裡

結果會抓回到**你執行指令的那個資料夾**底下的 `zss_reports/`：

```
zss_reports/
├── zss_<日期_時間>.html      結果表 + 角度圖
├── zss_<日期_時間>.csv       每個 0x25 frame 一行：t_s, zss_deg, stock_deg, diff_deg
└── zss_<日期_時間>_raw.csv   每一筆 0x23 和 0x25：t_ns, t_s, addr, raw, deg, hex
```

comma device 上也留一份：`/data/personal_settings/zss_reports/`。

---

## 4. 看懂結果

### 4.1 執行中的畫面（每 0.5 秒一行）

```
  time |   ZSS 0x23 | stock 0x25 |    diff
  0.5s |     12.34° |       4.5° |  +7.84°
  1.0s |     25.10° |      18.0° |  +7.10°
```

- **diff 不會是 0**：ZSS 的 0 = ZSS 開機那一刻方向盤的位置，所以有固定 offset。
- **原車角度 1.5° 一格跳**，diff 在約 ±0.75° 內跳動是正常的。
- 轉方向盤時 **diff 大致不變** → ZSS 正常。

### 4.2 結果表

| 項目 | 結果 | 意思 / 處理 |
|---|---|---|
| `0x23 ZSS found` | OK / NOT FOUND | 新韌體約 100 Hz。NOT FOUND → 檢查 ZSS 電源、CAN 接線、韌體 |
| `0x23 period` | INFO | 0x23 間隔的平均／最小／最大（ms）。新韌體平均約 10 ms |
| `0x25 stock angle found` | OK / NOT FOUND | NOT FOUND → 檢查 comma 和車子的 harness |
| `ZSS gain vs stock` | OK / CHECK / INFO | 1.00 = ZSS 韌體符合 factor（±5% 內 OK）。CHECK → 照 `firmware scale needed xK` 調整韌體的 `SCALE_NUM`（新 = 舊 × K）。INFO → 方向盤轉不夠，再轉大一點 |
| `ZSS offset` | INFO | ZSS 和原車角度的固定差值 |

### 4.3 角度圖（兩張）

| 圖 | 內容 | 怎麼判斷 |
|---|---|---|
| **Steering angle** | 原始角度：藍線 = 原車 0x25，紅線 = ZSS 0x23 | 兩條線有固定間距（offset）。轉方向盤時**間距保持不變** → ZSS 正常 |
| **Steering angle (ZSS − offset)** | 紅線扣掉 offset | **兩條線疊在一起** → ZSS 正常 |

---

## 5. 常見問題

**Q：`ssh: connect to host ... Connection timed out`**
A：IP 不對，或 Mac 和 comma 不在同一個網路。

**Q：`Permission denied (publickey)`**
A：Mac 的 SSH key 還沒加到 comma device，先完成第 2 節。

**Q：ssh 出現 `REMOTE HOST IDENTIFICATION HAS CHANGED`**
A：IP 被別的裝置用過。先備份再刪掉舊的 key：
```bash
cp -p ~/.ssh/known_hosts ~/.ssh/known_hosts.bak
ssh-keygen -R 172.20.10.6
```

**Q：出現 `cannot import openpilot`**
A：comma device 上的 openpilot 不是 0.9.8 / 0.11.x，或 `/data/openpilot` 不存在。

**Q：想手動在 comma device 上跑**
```bash
cd /data/openpilot
PYTHONPATH=/data/openpilot python3 /data/zss_check.py          # 10 秒
PYTHONPATH=/data/openpilot python3 /data/zss_check.py -t 0     # 按 Ctrl+C 結束
```
