# smartZSS

A small diagnostic tool for reading the ZSS (Zorro Secondary Steering Angle
Sensor) signal on a comma three running openpilot. It subscribes to the
`can` messaging topic, decodes CAN ID `0x23` (`SECONDARY_STEER_ANGLE`) using
`toyota_zss.dbc`, and prints the `ZORRO_STEER` value to the terminal in
real time.

## Prerequisites

## Requirements

- SSH into the comma three
- Clone this repo under `/data/openpilot`:
  ```bash
  cd /data/openpilot
  git clone https://github.com/iamoldking/smartZSS.git
  ```

## Usage

```bash
python3 readzss.py
```

If the ZSS is wired to a CAN bus other than 0:

```bash
python3 readzss.py --bus 1
```

Press `Ctrl+C` to exit.

## License

TBD

---

# smartZSS（中文說明）

一個小型診斷工具，用來在執行 openpilot 的 comma three 上讀取 ZSS
（Zorro 副轉向角感測器）訊號。它會讀取 `can` 這個 messaging topic，用
`toyota_zss.dbc` 解碼 CAN ID `0x23`（`SECONDARY_STEER_ANGLE`），即時把
`ZORRO_STEER` 的數值印在終端機上。

## 事前準備

## 需求

使用 comma three 登入，在 `/data/openpilot` 目錄下執行：

```bash
cd /data/openpilot
git clone https://github.com/iamoldking/smartZSS.git
```

## 使用方式

在終端機下打：

```bash
python3 readzss.py
```

如果 ZSS 接在非 0 的 CAN bus 上：

```bash
python3 readzss.py --bus 1
```

離開為 `Ctrl + C`。

## 授權

待定
