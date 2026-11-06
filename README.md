# smartZSS

English ｜ [中文](#smartzss中文說明)

Files for the ZSS (Zorro Steering Sensor) on a Toyota Prius with openpilot
(`iambluefred/openpilot`, branch `op0.11.2-zss`): firmware, housing, schematic and check tools.

## Folders

| Folder | What is inside |
|---|---|
| `1.arduinoCode/ZSS_V02/` | Arduino Nano firmware for the ZSS V0.2 board: reads the LS7366R encoder and sends CAN `0x23`. See its `README.md`. |
| `2.housing/` | Housing 3D model (`ZSS_V2.STL`) |
| `3.schematic/` | Schematic (`ZSS_V0.2.pdf`) |
| `4.zssSdsuCheck/` | Older check tool, runs on the comma device. See its `README.md`. |
| `5.zssCheck/` | **ZSS check from the Mac**: ssh to the comma device, 10 s test with live 0x23 / 0x25 angles, HTML report copied back. See its `README.md`. |

## Quick start: check the ZSS

On the Mac (the comma device IP is an example):

```bash
cd smartZSS/5.zssCheck
python3 readzss.py 172.20.10.6
```

Turn the steering wheel left and right (more than 30 deg each way) during the 10 s test.
The report is saved in `zss_reports/` in the folder where you ran the command.

## CAN signal

`0x23 SECONDARY_STEER_ANGLE`, `ZORRO_STEER : 7|24@0- (0.004901594652,0)` (`opendbc/dbc/toyota_zss.dbc`)

## License

TBD

---

# smartZSS（中文說明）

[English](#smartzss) ｜ 中文

Toyota Prius + openpilot（`iambluefred/openpilot` 的 `op0.11.2-zss` branch）用的 ZSS（Zorro Steering Sensor）相關檔案：韌體、外殼、電路圖、檢查工具。

## 資料夾

| 資料夾 | 內容 |
|---|---|
| `1.arduinoCode/ZSS_V02/` | ZSS V0.2 板子的 Arduino Nano 韌體：讀 LS7366R encoder，送出 CAN `0x23`。說明見裡面的 `README.md`。 |
| `2.housing/` | 外殼 3D 模型（`ZSS_V2.STL`） |
| `3.schematic/` | 電路圖（`ZSS_V0.2.pdf`） |
| `4.zssSdsuCheck/` | 舊版檢查工具，在 comma device 上執行。說明見裡面的 `README.md`。 |
| `5.zssCheck/` | **在 Mac 上檢查 ZSS**：SSH 到 comma device，測 10 秒，即時顯示 0x23 / 0x25 角度，HTML 報告抓回 Mac。說明見裡面的 `README.md`。 |

## 快速開始：檢查 ZSS

在 Mac 執行（IP 是範例）：

```bash
cd smartZSS/5.zssCheck
python3 readzss.py 172.20.10.6
```

測試的 10 秒內，方向盤左右各轉 30° 以上。
報告存在你執行指令的資料夾底下的 `zss_reports/`。

## CAN 訊號

`0x23 SECONDARY_STEER_ANGLE`，`ZORRO_STEER : 7|24@0- (0.004901594652,0)`（`opendbc/dbc/toyota_zss.dbc`）

## 授權

待定
