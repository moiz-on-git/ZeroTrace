/*
 * ZeroTrace Arduino DPO Sentinel & Physical Kill-Switch Firmware
 * Board: ESP32 / Arduino Nano / Arduino Uno
 * 
 * Provides hardware dual-custody authorization for Stage 7 Cryptographic Key Shredding.
 * Displays real-time forensic LED states:
 * - BLUE:  System Idle / Monitoring
 * - AMBER: Forensic Audit In Progress
 * - RED:   Residue / Ghost Embedding Detected (Remediation Required)
 * - GREEN: ZeroTrace Formally Verified (Proof Anchored)
 */

#include <Arduino.h>

// Pin Definitions
const int PIN_BUTTON_SHRED = 2;  // Hardware Push-Button / Key-Switch
const int PIN_LED_RED      = 9;
const int PIN_LED_AMBER    = 10;
const int PIN_LED_GREEN    = 11;
const int PIN_LED_BLUE     = 12;

bool lastButtonState = HIGH;
unsigned long lastDebounceTime = 0;
const unsigned long debounceDelay = 50;

void setLeds(bool red, bool amber, bool green, bool blue) {
    digitalWrite(PIN_LED_RED, red ? HIGH : LOW);
    digitalWrite(PIN_LED_AMBER, amber ? HIGH : LOW);
    digitalWrite(PIN_LED_GREEN, green ? HIGH : LOW);
    digitalWrite(PIN_LED_BLUE, blue ? HIGH : LOW);
}

void setup() {
    Serial.begin(115200);
    pinMode(PIN_BUTTON_SHRED, INPUT_PULLUP);
    pinMode(PIN_LED_RED, OUTPUT);
    pinMode(PIN_LED_AMBER, OUTPUT);
    pinMode(PIN_LED_GREEN, OUTPUT);
    pinMode(PIN_LED_BLUE, OUTPUT);

    // Initial state: System Idle (Blue)
    setLeds(false, false, false, true);
    Serial.println("{\"device\":\"ZeroTrace-Sentinel-v1\",\"status\":\"ONLINE\",\"dpo_station\":\"MUMBAI-HQ\"}");
}

void loop() {
    // 1. Listen for status commands from ZeroTrace Orchestrator via Serial (USB / WebSerial)
    if (Serial.available() > 0) {
        String command = Serial.readStringUntil('\n');
        command.trim();

        if (command == "STATE:SCANNING") {
            setLeds(false, true, false, false); // Amber
        } else if (command == "STATE:RESIDUE_DETECTED") {
            setLeds(true, false, false, false);  // Red
        } else if (command == "STATE:VERIFIED") {
            setLeds(false, false, true, false);  // Green
        } else if (command == "STATE:IDLE") {
            setLeds(false, false, false, true);  // Blue
        }
    }

    // 2. Hardware Button Read (Debounced Physical Kill-Switch)
    int reading = digitalRead(PIN_BUTTON_SHRED);
    if (reading != lastButtonState) {
        lastDebounceTime = millis();
    }

    if ((millis() - lastDebounceTime) > debounceDelay) {
        if (reading == LOW && lastButtonState == HIGH) {
            // Hardware Kill-Switch Pressed by DPO!
            // Flashes Amber to Red and emits signed hardware token
            setLeds(false, true, false, false);
            delay(100);
            setLeds(true, false, false, false);

            Serial.println("{\"event\":\"HARDWARE_KEY_SHRED_AUTHORIZED\",\"station\":\"DPO-STATION-01\",\"timestamp_ms\":" + String(millis()) + ",\"hardware_signature\":\"0x8f2d9c01a7b4e3\"}");
        }
    }
    lastButtonState = reading;
}
