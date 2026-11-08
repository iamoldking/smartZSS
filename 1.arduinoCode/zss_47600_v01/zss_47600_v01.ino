/* ===========================================================================
 * zss_47600_v01.ino - ZSS (Zorro Steering Sensor) for Toyota Prius
 *
 * !!! ONLY for the EPS 89650-47600. Do not use with any other EPS part number. !!!
 * !!! 只適合用在 89650-47600 的 EPS，其他 EPS 料號不要使用。                    !!!
 *
 * zss_47600_v01 (was ZSS_V03) = V02 + count scaling so the CAN value matches the DBC factor,
 *       + rate (data[4..6]) added back.
 *
 * Every 10 ms (100 Hz, fixed period): read the LS7366R encoder count and
 * send it as CAN 0x23.
 *
 * Hardware: Arduino Nano (ATmega328P, Old Bootloader, flash at 57600 baud)
 *   SPI: SCK = D13, MOSI = D11, MISO = D12
 *   MCP2515  CS = D9   (8MHz crystal -> MCP_8MHZ)
 *   LS7366R  CS = D7   (ZSS_V0.2 board; the older board used D8)
 *
 * CAN 0x23 SECONDARY_STEER_ANGLE, DLC 8 (toyota_zss.dbc):
 *   data[0..2]  encoder count, 24-bit big-endian signed (ZORRO_STEER 7|24@0-)
 *   data[3]     0
 *   data[4..6]  |count change| since the last frame (scaled counts, not used by openpilot)
 *   data[7]     Toyota checksum
 *
 * Scale: the DBC factor is fixed at 0.004901594652 deg/count (about 204 counts
 *   per degree), same as opendbc/dbc/toyota_zss.dbc in the op0.11.2-zss branch.
 *   The LS7366R (x4 quadrature, AS5047P 4000 steps/rev) gives only about 105
 *   counts per degree on the car (measured 2026-11-08 with ZSS_V02: gain 0.5145
 *   vs stock 0x25 over -118..+48 deg), so the count is multiplied by
 *   SCALE_NUM / SCALE_DEN = 1.9435 before it is sent.
 *   To re-calibrate: run 5.zssCheck/readzss.py (zss_check.py v2.0), read "firmware scale needed xK",
 *   then new SCALE_NUM = old SCALE_NUM * K (keep SCALE_DEN = 10000).
 * Zero: the counter is cleared at power-on, so 0 = wheel position at power-on.
 * ===========================================================================
 */

#include <SPI.h>
// autowp-mcp2515 v1.3.1 (MIT) is bundled in src/mcp2515/, no library install needed
#include "src/mcp2515/can.h"
#include "src/mcp2515/mcp2515.h"

//#define DEBUG_SERIAL        // print each frame (adds time, so CAN rate drops a bit)

#define PIN_CS_ENCODER   7
#define PIN_CS_MCP2515   9

const uint16_t CAN_ID      = 0x23;
const unsigned long TX_PERIOD_US = 10000;   // one CAN frame every 10 ms (100 Hz)
unsigned long nextTxUs = 0;                 // time of the next frame (micros)

// count scaling: 1 / 0.5145 = 1.9435 (see header)
const int32_t SCALE_NUM = 19435;
const int32_t SCALE_DEN = 10000;

int32_t lastCount = 0;              // scaled count sent in the previous frame

// LS7366R commands (datasheet): write MDR0/MDR1, read CNTR, clear CNTR
#define LS_WR_MDR0  0x88
#define LS_WR_MDR1  0x90
#define LS_RD_CNTR  0x60
#define LS_CLR_CNTR 0x20
const SPISettings LS7366R_SPI(1000000, MSBFIRST, SPI_MODE0);
MCP2515        mcp2515(PIN_CS_MCP2515);
struct can_frame msg;



void setup() {
  Serial.begin(115200);
  Serial.println("ZSS START");

  pinMode(PIN_CS_ENCODER, OUTPUT);
  digitalWrite(PIN_CS_ENCODER, HIGH);  // keep LS7366R off the bus while MCP2515 starts
  SPI.begin();

  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);
  mcp2515.setNormalMode();

  initEncoder();
  clearEncoder();                   // 0 = wheel position at power-on
  lastCount = scaleCount(readEncoder());
  nextTxUs = micros();
}


void loop() {
  // wait for the next 10 ms slot (fixed period, does not drift)
  while ((long)(micros() - nextTxUs) < 0) {}
  nextTxUs += TX_PERIOD_US;
  if ((long)(micros() - nextTxUs) > 0) nextTxUs = micros() + TX_PERIOD_US;  // fell behind: resync

  int32_t count = scaleCount(readEncoder());   // DBC counts (0.004901594652 deg each)
  int32_t rate  = abs(count - lastCount);      // abs() around the difference
  lastCount = count;

  msg.can_id  = CAN_ID;
  msg.can_dlc = 8;
  msg.data[0] = (count >> 16) & 0xFF;
  msg.data[1] = (count >>  8) & 0xFF;
  msg.data[2] =  count        & 0xFF;
  msg.data[3] = 0;
  msg.data[4] = (rate >> 16) & 0xFF;
  msg.data[5] = (rate >>  8) & 0xFF;
  msg.data[6] =  rate        & 0xFF;
  msg.data[7] = toyotaChecksum(msg.data, 7, CAN_ID);
  mcp2515.sendMessage(&msg);

#ifdef DEBUG_SERIAL
  Serial.print("count=");
  Serial.print(count);
  Serial.print(" rate=");
  Serial.println(rate);
#endif
}


// raw LS7366R count -> DBC count (64-bit math, no overflow)
int32_t scaleCount(int32_t raw) {
  return (int32_t)(((int64_t)raw * SCALE_NUM) / SCALE_DEN);
}


// Toyota checksum: ID high byte + ID low byte + (len + 1) + data[0..len-1], low 8 bits
uint8_t toyotaChecksum(const uint8_t *data, uint8_t len, uint16_t canId) {
  uint8_t sum = (canId >> 8) + (canId & 0xFF) + len + 1;
  for (uint8_t i = 0; i < len; i++) {
    sum += data[i];
  }
  return sum;
}


// ---- LS7366R driver (replaces the Encoder_Buffer library, same behavior) ----

// MDR0 = 0x03: x4 quadrature, free-running, index off, filter clock /1
// MDR1 = 0x00: 4-byte counter, counting enabled
void initEncoder() {
  SPI.beginTransaction(LS7366R_SPI);
  digitalWrite(PIN_CS_ENCODER, LOW);
  SPI.transfer(LS_WR_MDR0);
  SPI.transfer(0x03);
  digitalWrite(PIN_CS_ENCODER, HIGH);

  digitalWrite(PIN_CS_ENCODER, LOW);
  SPI.transfer(LS_WR_MDR1);
  SPI.transfer(0x00);
  digitalWrite(PIN_CS_ENCODER, HIGH);
  SPI.endTransaction();
}

// Read the 32-bit counter, high byte first
int32_t readEncoder() {
  uint32_t v = 0;
  SPI.beginTransaction(LS7366R_SPI);
  digitalWrite(PIN_CS_ENCODER, LOW);
  SPI.transfer(LS_RD_CNTR);
  for (uint8_t i = 0; i < 4; i++) {
    v = (v << 8) | SPI.transfer(0x00);
  }
  digitalWrite(PIN_CS_ENCODER, HIGH);
  SPI.endTransaction();
  return (int32_t)v;
}

// CLR_CNTR: set the counter to 0
void clearEncoder() {
  SPI.beginTransaction(LS7366R_SPI);
  digitalWrite(PIN_CS_ENCODER, LOW);
  SPI.transfer(LS_CLR_CNTR);
  digitalWrite(PIN_CS_ENCODER, HIGH);
  SPI.endTransaction();
}
