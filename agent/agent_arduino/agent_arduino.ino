// Агент «Мова» для Arduino (Uno/Nano/Mega…): лише UART, 115200 8N1.
// Протокол — PROTOCOL.md: запит 4 байти [команда][пін][hi][lo],
// відповідь 3 байти [статус][hi][lo]. Без зовнішніх бібліотек.

const uint8_t CMD_PIN = 1, CMD_WRITE = 2, CMD_READ = 3, CMD_ANALOG = 4,
              CMD_PWM = 5, CMD_DELAY = 6, CMD_PING = 7, CMD_BLINK = 8;
const uint8_t ST_OK = 0, ST_UNKNOWN = 1, ST_BAD_PIN = 2, ST_BAD_VALUE = 3;
const uint16_t PROTOCOL_VERSION = 1;

void reply(uint8_t status, uint16_t value) {
  Serial.write(status);
  Serial.write((uint8_t)(value >> 8));
  Serial.write((uint8_t)(value & 0xFF));
}

bool pinOk(uint8_t pin) { return pin < NUM_DIGITAL_PINS; }

void handle(uint8_t cmd, uint8_t pin, uint16_t value) {
  switch (cmd) {
    case CMD_PIN:
      if (!pinOk(pin)) return reply(ST_BAD_PIN, 0);
      if (value == 0) pinMode(pin, OUTPUT);
      else if (value == 1) pinMode(pin, INPUT);
      else if (value == 2) pinMode(pin, INPUT_PULLUP);
      else return reply(ST_BAD_VALUE, 0);
      return reply(ST_OK, 0);
    case CMD_WRITE:
      if (!pinOk(pin)) return reply(ST_BAD_PIN, 0);
      if (value > 1) return reply(ST_BAD_VALUE, 0);
      digitalWrite(pin, value ? HIGH : LOW);
      return reply(ST_OK, 0);
    case CMD_READ:
      if (!pinOk(pin)) return reply(ST_BAD_PIN, 0);
      return reply(ST_OK, digitalRead(pin) == HIGH ? 1 : 0);
    case CMD_ANALOG:
      if (pin >= NUM_ANALOG_INPUTS) return reply(ST_BAD_PIN, 0);
      return reply(ST_OK, analogRead(A0 + pin));
    case CMD_PWM:
      if (!pinOk(pin)) return reply(ST_BAD_PIN, 0);
      if (value > 255) return reply(ST_BAD_VALUE, 0);
      analogWrite(pin, value);
      return reply(ST_OK, 0);
    case CMD_DELAY:
      delay(value);                 // відповідь — після паузи
      return reply(ST_OK, 0);
    case CMD_PING:
      return reply(ST_OK, PROTOCOL_VERSION);
    case CMD_BLINK:
      pinMode(LED_BUILTIN, OUTPUT);
      for (uint16_t i = 0; i < value; i++) {
        digitalWrite(LED_BUILTIN, HIGH); delay(200);
        digitalWrite(LED_BUILTIN, LOW);  delay(200);
      }
      return reply(ST_OK, 0);
    default:
      return reply(ST_UNKNOWN, 0);
  }
}

void setup() {
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
}

void loop() {
  if (Serial.available() >= 4) {
    uint8_t cmd = Serial.read();
    uint8_t pin = Serial.read();
    uint16_t value = ((uint16_t)Serial.read() << 8) | Serial.read();
    handle(cmd, pin, value);
  }
}
