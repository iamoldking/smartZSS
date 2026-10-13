/* ===========================================================================
 * priusAngleFred.ino — ZSS (Zorro Steering Sensor) for Toyota Prius
 * ---------------------------------------------------------------------------
 * Purpose:
 *   Reads the steering angle count from an LS7366R quadrature encoder,
 *   applies an EMA filter, packs the result into a Toyota-format CAN frame,
 *   and transmits it on the vehicle CAN bus via MCP2515. Provides openpilot
 *   with a high-resolution secondary steering angle signal.
 *
 * Hardware: Arduino Nano (ATmega328P, Old Bootloader / flash at 57600 baud)
 *   SPI bus (shared by both slaves)   SCK = D13, MOSI = D11, MISO = D12
 *   MCP2515  CS = D9    External 8MHz crystal -> setBitrate() needs MCP_8MHZ
 *   LS7366R  CS = D7    <- matches ZSS_V0.2 schematic
 *                          WARNING: the older board used D8. When swapping
 *                          boards, PIN_CS_ENCODER must be updated.
 *
 * CAN signal definition (toyota_zss.dbc):
 *   BO_ 35 SECONDARY_STEER_ANGLE : 8 bytes            -> CAN ID 0x23, DLC 8
 *   SG_ ZORRO_STEER : 7|24@0-  scale 0.004901594652   -> 24-bit big-endian signed
 *   That is roughly 204 counts per degree, range +/-500 degrees.
 *
 *   NOTE: Serial prints raw counts; Cabana displays scaled degrees. The two
 *         values differ by design — the ratio should be 204 counts : 1 degree.
 *   NOTE: The rate field in data[4..6] has no matching signal in the DBC yet.
 * ===========================================================================
 */

#include <SPI.h>
#include <Encoder_Buffer.h>   // LS7366R quadrature counter (SPI)
#include <can.h>              // can_frame struct definition
#include <mcp2515.h>          // MCP2515 CAN controller driver


/* ---------------------------------------------------------------------------
 * Debug switches
 *
 * Uncomment a #define to enable it; leave it commented out when not needed.
 * Disabled blocks are removed at compile time — no flash cost, no timing impact.
 *
 * WARNING: With DEBUG_SERIAL on, one line is printed every 10ms (synchronised
 *   with CAN transmission, so no flooding), but it still slows the loop down.
 *   The CAN_TX_PERIOD_LOOPS = 93 calibration does not hold while it is active.
 *   When measuring the CAN period, turn DEBUG_SERIAL off and use DEBUG_LED only.
 * ------------------------------------------------------------------------- */
//#define DEBUG_SERIAL      // Print angle, rate, and the 8 bytes actually sent
//#define DEBUG_LED         // Toggle an LED on every CAN transmission (scope probe)

#ifdef DEBUG_LED
  #define PIN_DEBUG_LED  10   // Debug LED pin.
                              // Note: D10 is the ATmega328P hardware SS pin and
                              //       must be an OUTPUT, otherwise SPI drops
                              //       back into slave mode.
  uint8_t ledState = 0;       // LED state, toggled on each CAN transmission
#endif


/* ---------------------------------------------------------------------------
 * Pin assignments
 * ------------------------------------------------------------------------- */
#define PIN_CS_ENCODER   7    // LS7366R chip select
#define PIN_LFLAG        6    // LS7366R Outputs. LFLAG
#define PIN_CS_MCP2515   9    // MCP2515 chip select


/* ---------------------------------------------------------------------------
 * CAN message parameters (per toyota_zss.dbc)
 * ------------------------------------------------------------------------- */
const uint16_t CAN_ID_STEER_ANGLE = 0x23;  // decimal 35, SECONDARY_STEER_ANGLE
const uint8_t  CAN_DLC            = 8;     // Payload length, fixed at 8 bytes
const uint8_t  CAN_CKSUM_INDEX    = 7;     // Checksum occupies the last byte
const uint8_t  CAN_CKSUM_LEN      = 7;     // Checksum covers data[0..6]

// Transmit throttle: send one CAN frame every N loop iterations.
// 93 was measured on a scope — it lands exactly on 10ms (100Hz) with the
// current loop body.
// WARNING: this value is tied to current loop execution speed. Any change to
//   the loop body or SPI clock will shift the interval, and it must then be
//   re-measured on a scope.
const uint8_t CAN_TX_PERIOD_LOOPS = 99;


/* ---------------------------------------------------------------------------
 * EMA filter parameters
 *
 * How it works: emaAcc holds the filter state scaled up by EMA_DEPTH. Once
 *   settled, emaAcc is approximately angleRaw * EMA_DEPTH, and the output is
 *   divided back down. The remainder stays inside emaAcc instead of being
 *   discarded, so small signals are not truncated to zero (integer-division
 *   deadband).
 * Trade-off: a larger depth means smoother output but more group delay.
 *   EMA_DEPTH = 16 at a 10ms period gives roughly 150ms of lag, which is on
 *   the high side for lateral control. If steering feels sluggish on the road,
 *   reduce this value first (try 8 or 4).
 * ------------------------------------------------------------------------- */
const int32_t EMA_DEPTH = 1;


/* ---------------------------------------------------------------------------
 * Global state
 * ------------------------------------------------------------------------- */
Encoder_Buffer encoder(PIN_CS_ENCODER);
MCP2515        mcp2515(PIN_CS_MCP2515);
struct can_frame steerMsg;                 // CAN frame sent on each transmission

int32_t angleRaw      = 0;   // Raw encoder count, updated every loop iteration
int32_t angleFiltered = 0;   // EMA-filtered angle, the value sent over CAN
int32_t angleAtLastTx = 0;   // angleFiltered at the previous transmission
int32_t angleRate     = 0;   // Absolute angle change between transmissions
                             //   (counts per 10ms, always >= 0)
int32_t emaAcc        = 0;   // EMA accumulator, holds (output * EMA_DEPTH)
uint8_t txCounter     = 0;   // Loop counter; transmits and resets at the period


/* ===========================================================================
 * SETUP
 * ========================================================================= */
void setup() {
  
  pinMode(PIN_LFLAG, INPUT_PULLUP);
  Serial.begin(115200);      // Order matters: begin() first, then wait.
  while (!Serial);           //   Waiting before begin() would hang.
  Serial.println("ZSS START");

  SPI.begin();

  // --- CAN controller ---
  mcp2515.reset();
  mcp2515.setBitrate(CAN_500KBPS, MCP_8MHZ);   // 500kbps with the onboard 8MHz crystal
  mcp2515.setNormalMode();

  // --- Angle sensor ---
  encoder.initEncoder();
  // init
  resetCounter();
  //resetMCP2515();

#ifdef DEBUG_LED
  pinMode(PIN_DEBUG_LED, OUTPUT);
  digitalWrite(PIN_DEBUG_LED, LOW);
#endif
}


/* ===========================================================================
 * MAIN LOOP
 * Updates the angle every iteration; transmits once CAN_TX_PERIOD_LOOPS
 * iterations (10ms) have elapsed.
 * ========================================================================= */
void loop() {
  readAngle();

  txCounter++;
  if (txCounter >= CAN_TX_PERIOD_LOOPS) {
    sendSteerAngle();
    txCounter = 0;
  }
}


/* ===========================================================================
 * Read the angle and filter it (runs every loop iteration)
 * ========================================================================= */
void readAngle() {
  angleRaw = encoder.readEncoder();    // 32-bit accumulated count from LS7366R
  // Serial.println(angleRaw); // for Debug 

  // EMA filter (fixed-point; the remainder is retained in emaAcc)
  emaAcc += angleRaw - (emaAcc / EMA_DEPTH);
  angleFiltered = emaAcc / EMA_DEPTH;
}


/* ===========================================================================
 * Assemble and transmit the CAN frame (ID 0x23, DLC 8)
 *
 *   data[0..2]  Angle, 24-bit big-endian signed (DBC: ZORRO_STEER 7|24@0-).
 *               High byte first, matching the DBC's Motorola byte order.
 *               WARNING: angleFiltered beyond +/-8,388,607 overflows and
 *               flips sign.
 *   data[3]     Reserved, always 0
 *   data[4..6]  Angular rate magnitude, 24-bit big-endian (always positive)
 *   data[7]     Toyota checksum
 * ========================================================================= */
void sendSteerAngle() {
  // Rate magnitude: absolute angle change over this 10ms window. No direction,
  // always >= 0.
  // WARNING: abs() must wrap the subtraction. Writing abs(a) - abs(b) instead
  // flips the sign while turning left and collapses to zero when passing
  // through 0 degrees — that form is wrong.
  angleRate     = abs(angleFiltered - angleAtLastTx);
  angleAtLastTx = angleFiltered;

  steerMsg.can_id  = CAN_ID_STEER_ANGLE;
  steerMsg.can_dlc = CAN_DLC;

  steerMsg.data[0] = (angleFiltered >> 16) & 0xFF;
  steerMsg.data[1] = (angleFiltered >>  8) & 0xFF;
  steerMsg.data[2] = (angleFiltered >>  0) & 0xFF;
  steerMsg.data[3] = 0x00;
  steerMsg.data[4] = (angleRate >> 16) & 0xFF;
  steerMsg.data[5] = (angleRate >>  8) & 0xFF;
  steerMsg.data[6] = (angleRate >>  0) & 0xFF;

  steerMsg.data[CAN_CKSUM_INDEX] =
      toyotaChecksum(steerMsg.data, CAN_CKSUM_LEN, CAN_ID_STEER_ANGLE);

  mcp2515.sendMessage(&steerMsg);

#ifdef DEBUG_SERIAL
  // Print exactly what went onto the bus, timed with the transmission, so the
  // output can be compared byte by byte against Cabana.
  // Format: angle=<filtered count>  rate=<abs change>  bytes=<data[0..7] in hex>
  Serial.print("angle=");
  Serial.print(angleFiltered);
  Serial.print("  rate=");
  Serial.print(angleRate);
  Serial.print("  bytes=");
  for (uint8_t i = 0; i < CAN_DLC; i++) {
    if (steerMsg.data[i] < 0x10) Serial.print('0');   // Pad to two hex digits
    Serial.print(steerMsg.data[i], HEX);
    Serial.print(' ');
  }
  Serial.println();
#endif

#ifdef DEBUG_LED
  // Toggles on every transmission, producing a square wave on the scope.
  // The HALF period equals the CAN interval (target 10ms); the full period is
  // 20ms. Do not misread this when measuring.
  ledState ^= 1;
  digitalWrite(PIN_DEBUG_LED, ledState);
#endif
}


/* ===========================================================================
 * Toyota CAN checksum
 * Algorithm: sum the CAN ID high byte, the low byte, (length + 1), and
 *   data[0..len-1]; the checksum is the low 8 bits of that sum.
 * ========================================================================= */
uint8_t toyotaChecksum(const uint8_t *data, uint8_t len, uint16_t canId) {
  uint8_t checksum = ((canId & 0xFF00) >> 8) + (canId & 0x00FF) + len + 1;
  for (uint8_t i = 0; i < len; i++) {
    checksum += data[i];
  }
  return checksum;
}

void resetCounter()
{
    digitalWrite(PIN_CS_ENCODER, LOW);
    SPI.transfer(0x20);   // CLR_CNTR
    digitalWrite(PIN_CS_ENCODER, HIGH);
}

void resetMCP2515()
{
    digitalWrite(PIN_CS_MCP2515, LOW);
    SPI.transfer(0xC0);
    digitalWrite(PIN_CS_MCP2515, HIGH);
}
