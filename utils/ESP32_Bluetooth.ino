#include "BluetoothSerial.h"
BluetoothSerial SerialBT;

void setup()
{
    Serial.begin(115200);        // UART to STM32
    SerialBT.begin("AstroLens"); // Name shown to PC
}

void loop()
{
    // PC → ESP32 → STM32
    if (SerialBT.available())
    {
        Serial.write(SerialBT.read());
    }

    // STM32 → ESP32 → PC
    if (Serial.available())
    {
        SerialBT.write(Serial.read());
    }
}
