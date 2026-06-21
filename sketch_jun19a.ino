#include <BLEDevice.h>
#include <BLEServer.h>
#include <BLEUtils.h>
#include <BLE2902.h>
#include <WiFi.h>

// --- PINES SEGUROS (Mueve tus cables aquí para evitar los parpadeos locos) ---
const int mosfetRojo = 1;  
const int mosfetVerde = 5; 
const int mosfetAzul = 6;  

#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

String modoActual = "OFF";
int cR = 0, cG = 0, cB = 0; 
unsigned long ultimoActualizacion = 0;
int pasoAnimacion = 0;
bool incrementando = true;

// -----------------------------------------------------------------
// MODO 100% LIBRE (Python es el jefe ahora)
// -----------------------------------------------------------------
void aplicarPotencia(int valR, int valG, int valB) {
  int outputR = valR; 
  int outputG = valG; // Ya no hay 0.25 aquí, pasa directo el 100%
  int outputB = valB; 
  
  // EL SALVAVIDAS: Evita que el lado derecho se apague en las animaciones
  if (outputR > 0 && outputR < 90) {
    outputR = 90;
  }

  // CANDADO DE APAGADO
  if (modoActual == "OFF") {
    outputR = 0; outputG = 0; outputB = 0;
  }

  analogWrite(mosfetRojo, outputR);
  analogWrite(mosfetVerde, outputG);
  analogWrite(mosfetAzul, outputB);
}

class MyCallbacks: public BLECharacteristicCallbacks {
    void onWrite(BLECharacteristic *pCharacteristic) {
      String rxValue = pCharacteristic->getValue();
      if (rxValue.length() > 0) {
        int primerComa = rxValue.indexOf(',');
        if (primerComa > 0) {
            modoActual = rxValue.substring(0, primerComa);
            int segundaComa = rxValue.indexOf(',', primerComa + 1);
            cR = rxValue.substring(primerComa + 1, segundaComa).toInt();
            cG = rxValue.substring(segundaComa + 1, rxValue.lastIndexOf(',')).toInt();
            cB = rxValue.substring(rxValue.lastIndexOf(',') + 1).toInt();
        } else {
            modoActual = "OFF"; 
            cR = 0; cG = 0; cB = 0; 
        }
        pasoAnimacion = 0; 
      }
    }
};

void setup() {
  digitalWrite(mosfetRojo, LOW);
  digitalWrite(mosfetVerde, LOW);
  digitalWrite(mosfetAzul, LOW);
  
  pinMode(mosfetRojo, OUTPUT);
  pinMode(mosfetVerde, OUTPUT);
  pinMode(mosfetAzul, OUTPUT);

  modoActual = "OFF";
  aplicarPotencia(0, 0, 0);

  WiFi.mode(WIFI_OFF); 

  BLEDevice::init("G15_RGB_Mod");
  BLEServer *pServer = BLEDevice::createServer();
  BLEService *pService = pServer->createService(SERVICE_UUID);
  BLECharacteristic *pCharacteristic = pService->createCharacteristic(
                                         CHARACTERISTIC_UUID,
                                         BLECharacteristic::PROPERTY_READ |
                                         BLECharacteristic::PROPERTY_WRITE
                                       );
  pCharacteristic->setCallbacks(new MyCallbacks());
  pService->start();
  
  BLEAdvertising *pAdvertising = BLEDevice::getAdvertising();
  pAdvertising->addServiceUUID(SERVICE_UUID);
  pAdvertising->setScanResponse(true);
  BLEDevice::startAdvertising();
}

void loop() {
  unsigned long tiempoActual = millis();

  if (modoActual == "FIJO" || modoActual == "LOW") {
    aplicarPotencia(cR, cG, cB);
  } 
  else if (modoActual == "RESPIRA") {
    if (tiempoActual - ultimoActualizacion > 5) { 
      if (incrementando) pasoAnimacion++; else pasoAnimacion--;
      if (pasoAnimacion >= 255) incrementando = false;
      if (pasoAnimacion <= 0) incrementando = true;
      
      aplicarPotencia((cR * pasoAnimacion) / 255, (cG * pasoAnimacion) / 255, (cB * pasoAnimacion) / 255);
      ultimoActualizacion = tiempoActual;
    }
  } 
  else if (modoActual == "FLASH") {
    if (tiempoActual - ultimoActualizacion > 500) { 
      pasoAnimacion = !pasoAnimacion;
      if (pasoAnimacion) {
        aplicarPotencia(cR, cG, cB);
      } else {
        aplicarPotencia(0, 0, 0);
      }
      ultimoActualizacion = tiempoActual;
    }
  }
  else if (modoActual == "ARCOIRIS") {
    if (tiempoActual - ultimoActualizacion > 20) {
      pasoAnimacion++;
      if (pasoAnimacion > 255) pasoAnimacion = 0;
      
      int pos = 255 - pasoAnimacion;
      int valR = 0, valG = 0, valB = 0;
      
      if(pos < 85) { valR = 255 - pos * 3; valG = 0; valB = pos * 3; } 
      else if(pos < 170) { pos -= 85; valR = 0; valG = pos * 3; valB = 255 - pos * 3; } 
      else { pos -= 170; valR = pos * 3; valG = 255 - pos * 3; valB = 0; }

      aplicarPotencia((valR * cR) / 255, (valG * cG) / 255, (valB * cB) / 255);
      ultimoActualizacion = tiempoActual;
    }
  }
  else { 
    aplicarPotencia(0, 0, 0);
  }

  delay(1);  
}