// Агент «Мова» для ESP32: UART (115200) + Wi-Fi точка доступу + TCP-сервер
// на порту 5555. Протокол — PROTOCOL.md: запит 4 байти [команда][пін][hi][lo],
// відповідь 3 байти [статус][hi][lo]. Лише стандартні бібліотеки ESP32 (WiFi).
//
// Телефон підключається до мережі AP_SSID (пароль AP_PASSWORD), плата має
// адресу 192.168.4.1. Одночасно працює і USB-кабель (UART).

#include <WiFi.h>

const char* AP_SSID = "Мова-плата";
const char* AP_PASSWORD = "12345678";     // мінімум 8 символів
const uint16_t TCP_PORT = 5555;

const uint8_t CMD_PIN = 1, CMD_WRITE = 2, CMD_READ = 3, CMD_ANALOG = 4,
              CMD_PWM = 5, CMD_DELAY = 6, CMD_PING = 7, CMD_BLINK = 8;
const uint8_t ST_OK = 0, ST_UNKNOWN = 1, ST_BAD_PIN = 2, ST_BAD_VALUE = 3;
const uint16_t PROTOCOL_VERSION = 1;
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

WiFiServer server(TCP_PORT);
WiFiClient client;

// ШІМ на ESP32 — через канали ledc; кожному піну свій канал (до 16)
int pwmChannel[40];

void reply(Stream& out, uint8_t status, uint16_t value) {
  out.write(status);
  out.write((uint8_t)(value >> 8));
  out.write((uint8_t)(value & 0xFF));
  out.flush();
}

bool pinOk(uint8_t pin) { return pin < 40; }

void handle(Stream& out, uint8_t cmd, uint8_t pin, uint16_t value) {
  switch (cmd) {
    case CMD_PIN:
      if (!pinOk(pin)) return reply(out, ST_BAD_PIN, 0);
      if (value == 0) pinMode(pin, OUTPUT);
      else if (value == 1) pinMode(pin, INPUT);
      else if (value == 2) pinMode(pin, INPUT_PULLUP);
      else return reply(out, ST_BAD_VALUE, 0);
      return reply(out, ST_OK, 0);
    case CMD_WRITE:
      if (!pinOk(pin)) return reply(out, ST_BAD_PIN, 0);
      if (value > 1) return reply(out, ST_BAD_VALUE, 0);
      digitalWrite(pin, value ? HIGH : LOW);
      return reply(out, ST_OK, 0);
    case CMD_READ:
      if (!pinOk(pin)) return reply(out, ST_BAD_PIN, 0);
      return reply(out, ST_OK, digitalRead(pin) == HIGH ? 1 : 0);
    case CMD_ANALOG:
      if (!pinOk(pin)) return reply(out, ST_BAD_PIN, 0);
      return reply(out, ST_OK, analogRead(pin));        // 0..4095
    case CMD_PWM: {
      if (!pinOk(pin)) return reply(out, ST_BAD_PIN, 0);
      if (value > 255) return reply(out, ST_BAD_VALUE, 0);
      if (pwmChannel[pin] < 0) {
        static int next = 0;
        if (next >= 16) return reply(out, ST_BAD_PIN, 0);
        pwmChannel[pin] = next++;
        ledcSetup(pwmChannel[pin], 5000, 8);
        ledcAttachPin(pin, pwmChannel[pin]);
      }
      ledcWrite(pwmChannel[pin], value);
      return reply(out, ST_OK, 0);
    }
    case CMD_DELAY:
      delay(value);                                       // відповідь — після паузи
      return reply(out, ST_OK, 0);
    case CMD_PING:
      return reply(out, ST_OK, PROTOCOL_VERSION);
    case CMD_BLINK:
      pinMode(LED_BUILTIN, OUTPUT);
      for (uint16_t i = 0; i < value; i++) {
        digitalWrite(LED_BUILTIN, HIGH); delay(200);
        digitalWrite(LED_BUILTIN, LOW);  delay(200);
      }
      return reply(out, ST_OK, 0);
    default:
      return reply(out, ST_UNKNOWN, 0);
  }
}

void serve(Stream& io) {
  if (io.available() >= 4) {
    uint8_t cmd = io.read();
    uint8_t pin = io.read();
    uint16_t value = ((uint16_t)io.read() << 8) | io.read();
    handle(io, cmd, pin, value);
  }
}

void setup() {
  for (int i = 0; i < 40; i++) pwmChannel[i] = -1;
  Serial.begin(115200);
  pinMode(LED_BUILTIN, OUTPUT);
  WiFi.mode(WIFI_AP);
  WiFi.softAP(AP_SSID, AP_PASSWORD);
  server.begin();
}

void loop() {
  serve(Serial);
  if (!client || !client.connected()) {
    client = server.available();
  }
  if (client && client.connected()) {
    serve(client);
  }
}
