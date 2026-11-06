# ZSS_V02 — Arduino firmware for ZSS V0.2

English ｜ [中文](#中文說明)

ZSS (Zorro Steering Sensor) for Toyota Prius.
Every 10 ms the board reads the LS7366R encoder count and sends it on CAN as `0x23`.

## Hardware

| Item | Value |
|---|---|
| MCU | Arduino Nano (ATmega328P, **Old Bootloader**, 57600 baud) |
| SPI | SCK = D13, MOSI = D11, MISO = D12 |
| MCP2515 CS | D9 (8 MHz crystal, CAN 500 kbps) |
| LS7366R CS | D7 (ZSS_V0.2 board; the older board used D8) |

## CAN message

`0x23 SECONDARY_STEER_ANGLE`, DLC 8 (`toyota_zss.dbc`)

| Byte | Content |
|---|---|
| data[0..2] | encoder count, 24-bit big-endian signed (`ZORRO_STEER 7\|24@0-`) |
| data[3] | 0 |
| data[4..6] | \|count change\| since the last frame (not used by openpilot) |
| data[7] | Toyota checksum |

- Scale: DBC factor `0.004901594652` deg/count (about 204 counts per degree),
  same as `opendbc/dbc/toyota_zss.dbc` in the `op0.11.2-zss` branch:
  `ZORRO_STEER : 7|24@0- (0.004901594652,0)`.
- Zero: the counter is cleared at power-on, so 0 = wheel position at power-on.

## Build and upload

No library install is needed. Everything is inside this folder.

1. Open `ZSS_V02.ino` in the Arduino IDE.
2. Board: **Arduino Nano**. Processor: **ATmega328P (Old Bootloader)**.
3. Click Verify, then Upload.

Only `SPI.h` is used from outside this folder. It comes with the Arduino AVR core.

## Folder layout

```
ZSS_V02/
├── ZSS_V02.ino          main sketch + LS7366R driver
└── src/mcp2515/         autowp-mcp2515 v1.3.1 (MIT license)
    ├── can.h
    ├── mcp2515.h
    ├── mcp2515.cpp
    └── LICENSE.md
```

## Changes in branch `zss-v02-compile-fix`

The old sketch did not compile on a new machine:
`Encoder_Buffer.h: No such file or directory` and then `can.h: No such file or directory`.

- Moved `ZSS_V02.ino` into its own sketch folder `ZSS_V02/` (the Arduino IDE needs this).
- Removed the `Encoder_Buffer` library. The LS7366R driver is now in the sketch
  (`initEncoder()`, `readEncoder()`, `clearEncoder()`), with the same settings:
  MDR0 = `0x03` (x4 quadrature, free-running), MDR1 = `0x00` (4-byte counter).
- Each encoder access uses `SPI.beginTransaction()` (1 MHz, mode 0),
  so the MCP2515 SPI settings do not affect it.
- D7 (LS7366R CS) is set HIGH at the start of `setup()`,
  so the encoder stays off the SPI bus while the MCP2515 starts.
- Bundled `autowp-mcp2515` v1.3.1 in `src/mcp2515/`.

Not changed: CAN ID, frame format, 10 ms period, pins.

Tested: compiles with avr-gcc 7.3.0 for ATmega328P (flash 5,920 bytes, RAM 274 bytes).

---

# 中文說明

[English](#zss_v02--arduino-firmware-for-zss-v02) ｜ 中文

## 這是什麼

ZSS（Zorro Steering Sensor）給 Toyota Prius 用的 Arduino firmware。
每 10 ms 讀一次 LS7366R encoder 的 count，用 CAN `0x23` 送出去。

## 硬體

| 項目 | 設定 |
|---|---|
| MCU | Arduino Nano（ATmega328P，**Old Bootloader**，57600 baud） |
| SPI | SCK = D13、MOSI = D11、MISO = D12 |
| MCP2515 CS | D9（8 MHz 石英震盪器，CAN 500 kbps） |
| LS7366R CS | D7（ZSS_V0.2 板子；舊板子是 D8） |

## CAN 訊息

`0x23 SECONDARY_STEER_ANGLE`，DLC 8（`toyota_zss.dbc`）

| Byte | 內容 |
|---|---|
| data[0..2] | encoder count，24-bit big-endian signed（`ZORRO_STEER 7\|24@0-`） |
| data[3] | 0 |
| data[4..6] | 跟上一個 frame 相比的 count 變化量（取絕對值，openpilot 沒用到） |
| data[7] | Toyota checksum |

- 比例：DBC factor `0.004901594652` deg/count（大約每 1 度 204 counts），
  以 `op0.11.2-zss` branch 的 `opendbc/dbc/toyota_zss.dbc` 為準：
  `ZORRO_STEER : 7|24@0- (0.004901594652,0)`。
- 歸零：開機時 counter 清成 0，所以 0 = 開機那一刻方向盤的位置。

## Compile 與 Upload

不用另外安裝任何 library，需要的 code 都在這個資料夾裡。

1. 用 Arduino IDE 打開 `ZSS_V02.ino`。
2. 開發板選 **Arduino Nano**，處理器選 **ATmega328P (Old Bootloader)**。
3. 按 Verify（✓），再按 Upload（→）。

只有 `SPI.h` 來自資料夾外面，它是 Arduino AVR core 內建的。

## 資料夾結構

```
ZSS_V02/
├── ZSS_V02.ino          主程式 + LS7366R driver
└── src/mcp2515/         autowp-mcp2515 v1.3.1（MIT license）
    ├── can.h
    ├── mcp2515.h
    ├── mcp2515.cpp
    └── LICENSE.md
```

## `zss-v02-compile-fix` branch 改了什麼

舊版 sketch 在新電腦上 compile 不過：
先出現 `Encoder_Buffer.h: No such file or directory`，修掉後又出現 `can.h: No such file or directory`。

- 把 `ZSS_V02.ino` 搬進同名資料夾 `ZSS_V02/`（Arduino IDE 規定要這樣放）。
- 拿掉 `Encoder_Buffer` library，LS7366R driver 直接寫在 sketch 裡
  （`initEncoder()`、`readEncoder()`、`clearEncoder()`），設定跟原本一樣：
  MDR0 = `0x03`（x4 quadrature、free-running），MDR1 = `0x00`（4-byte counter）。
- 每次讀寫 encoder 都用 `SPI.beginTransaction()`（1 MHz、mode 0），
  不會被 MCP2515 的 SPI 設定影響。
- `setup()` 一開始先把 D7（LS7366R CS）設成 HIGH，
  MCP2515 啟動時 encoder 不會佔用 SPI bus。
- 把 `autowp-mcp2515` v1.3.1 放進 `src/mcp2515/`。

沒有改的：CAN ID、frame 格式、10 ms 週期、pin 腳。

測試：用 avr-gcc 7.3.0 compile ATmega328P 成功（Flash 5,920 bytes、RAM 274 bytes）。
