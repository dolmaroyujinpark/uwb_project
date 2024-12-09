/*
   This example code is in the Public Domain (or CC0 licensed, at your option.)

   Unless required by applicable law or agreed to in writing, this
   software is distributed on an "AS IS" BASIS, WITHOUT WARRANTIES OR
   CONDITIONS OF ANY KIND, either express or implied.
*/

/* 
 * StandardRTLSAnchorMain_TWR.ino
 * 
 * This is an example master anchor in a RTLS using two way ranging ISO/IEC 24730-62_2013 messages
 */

#include <DW1000Ng.hpp>
#include <DW1000NgUtils.hpp>
#include <DW1000NgRanging.hpp>
#include <DW1000NgRTLS.hpp>

String cmd = "distance";
String input = "";

typedef struct Position {
    double x;
    double y;
} Position;

// connection pins
#if defined(ESP8266)
//const uint8_t PIN_SS = 15;
#else
const uint8_t PIN_RST = 15;
const uint8_t PIN_SS = 4; // spi select pin
#endif

// Extended Unique Identifier register. 64-bit device identifier. Register file: 0x01
const char EUI[] = "AA:BB:CC:DD:EE:FF:00:01";

Position position_self = {0,0};
Position position_B = {4.23,0};
Position position_C = {2.8,5};

double range_self;
double range_B;
double range_C;

boolean received_B = false;

byte target_eui[8];
byte tag_shortAddress[] = {0x05, 0x00};

byte anchor_b[] = {0x02, 0x00};
uint16_t next_anchor = 2;
byte anchor_c[] = {0x03, 0x00};

device_configuration_t DEFAULT_CONFIG = {
    false,
    true,
    true,
    true,
    false,
    SFDMode::STANDARD_SFD,
    Channel::CHANNEL_5,
    DataRate::RATE_850KBPS,
    PulseFrequency::FREQ_16MHZ,
    PreambleLength::LEN_256,
    PreambleCode::CODE_3
};

frame_filtering_configuration_t ANCHOR_FRAME_FILTER_CONFIG = {
    false,
    false,
    true,
    false,
    false,
    false,
    false,
    true /* This allows blink frames */
};

void setup() {
    // DEBUG monitoring
    Serial.begin(115200);
    Serial.println(F("### DW1000Ng-arduino-ranging-anchorMain ###"));
    // initialize the driver
    #if defined(ESP8266)
    DW1000Ng::initializeNoInterrupt(PIN_SS);
    #else
    DW1000Ng::initializeNoInterrupt(PIN_SS, PIN_RST);
    #endif
    Serial.println(F("DW1000Ng initialized ..."));
    // general configuration
    DW1000Ng::applyConfiguration(DEFAULT_CONFIG);
    DW1000Ng::enableFrameFiltering(ANCHOR_FRAME_FILTER_CONFIG);
    
    DW1000Ng::setEUI(EUI);

    DW1000Ng::setPreambleDetectionTimeout(64);
    DW1000Ng::setSfdDetectionTimeout(273);
    DW1000Ng::setReceiveFrameWaitTimeoutPeriod(5000);

    DW1000Ng::setNetworkId(RTLS_APP_ID);
    DW1000Ng::setDeviceAddress(1);
   
    DW1000Ng::setAntennaDelay(16436);
    
    Serial.println(F("Committed configuration ..."));
    // DEBUG chip info and registers pretty printed
    char msg[128];
    DW1000Ng::getPrintableDeviceIdentifier(msg);
    Serial.print("Device ID: "); Serial.println(msg);
    DW1000Ng::getPrintableExtendedUniqueIdentifier(msg);
    Serial.print("Unique ID: "); Serial.println(msg);
    DW1000Ng::getPrintableNetworkIdAndShortAddress(msg);
    Serial.print("Network ID & Device Address: "); Serial.println(msg);
    DW1000Ng::getPrintableDeviceMode(msg);
    Serial.print("Device mode: "); Serial.println(msg);    
}

/* using https://math.stackexchange.com/questions/884807/find-x-location-using-3-known-x-y-location-using-trilateration */
void calculatePosition(double &x, double &y) {
    // 원 1: (x - position_self.x)^2 + (y - position_self.y)^2 = range_self^2
    // 원 2: (x - position_B.x)^2 + (y - position_B.y)^2 = range_B^2
    // 두 원의 교점을 구하는 공식 사용

    double A = -2 * position_self.x + 2 * position_B.x;
    double B = -2 * position_self.y + 2 * position_B.y;
    double C = pow(range_self, 2) - pow(range_B, 2) - pow(position_self.x, 2) + pow(position_B.x, 2) - pow(position_self.y, 2) + pow(position_B.y, 2);

    double D = -2 * position_B.x + 2 * position_C.x;
    double E = -2 * position_B.y + 2 * position_C.y;
    double F = pow(range_B, 2) - pow(range_C, 2) - pow(position_B.x, 2) + pow(position_C.x, 2) - pow(position_B.y, 2) + pow(position_C.y, 2);

    // 첫 번째 교점 (x1, y1)
    double x1 = (C * E - F * B) / (E * A - B * D);
    double y1 = (C * D - A * F) / (B * D - A * E);

    // 두 번째 교점 (x2, y2)
    double x2 = (C * E + F * B) / (E * A + B * D);
    double y2 = (C * D + A * F) / (B * D + A * E);

    // 두 교점과 앵커 C의 거리 차이 계산
    double dist1 = sqrt(pow(x1 - position_C.x, 2) + pow(y1 - position_C.y, 2));
    double dist2 = sqrt(pow(x2 - position_C.x, 2) + pow(y2 - position_C.y, 2));

    // 세 번째 앵커와 가까운 교점 선택
    if (dist1 < dist2) {
        x = x1;
        y = y1;
    } else {
        x = x2;
        y = y2;
    }
}

int main() {
    // 두 원의 중심 좌표와 반지름
    double x1 = 0, y1 = 0, r1 = 5;  // 첫 번째 원
    double x2 = 8, y2 = 0, r2 = 5;  // 두 번째 원

    // 앵커 좌표들
    Point anchor1 = {0, 0};
    Point anchor2 = {10, 0};
    Point anchor3 = {5, 5};

    /*// 두 원의 교점들에서 세 번째 앵커와 가까운 점의 무게중심을 구합니다.
    Point centroid = calculateCentroidOfClosestIntersections(x1, y1, r1, x2, y2, r2);

    // 결과 출력
    std::cout << "선택된 교점의 좌표 (무게중심): (" << centroid.x << ", " << centroid.y << ")\n";*/

    return 0;
}

// 시리얼 창에서 앵커의 좌표를 읽어오는 함수
void readAnchorPositions() {

        String message = Serial.readStringUntil('\n');
        Serial.println(message);
        // Expecting the format: "anchor self:x,y;B:x,y;C:x,y"
        if (message.startsWith("anchor")) {
            int selfPosIndex = message.indexOf("self:");
            int bPosIndex = message.indexOf("B:");
            int cPosIndex = message.indexOf("C:");

            if (selfPosIndex != -1 && bPosIndex != -1 && cPosIndex != -1) {
                // Extract coordinates
                String selfCoords = message.substring(selfPosIndex + 5, bPosIndex);
                String bCoords = message.substring(bPosIndex + 2, cPosIndex);
                String cCoords = message.substring(cPosIndex + 2);

                // Parse coordinates and set positions
                position_self.x = selfCoords.substring(0, selfCoords.indexOf(',')).toDouble();
                position_self.y = selfCoords.substring(selfCoords.indexOf(',') + 1).toDouble();

                position_B.x = bCoords.substring(0, bCoords.indexOf(',')).toDouble();
                position_B.y = bCoords.substring(bCoords.indexOf(',') + 1).toDouble();

                position_C.x = cCoords.substring(0, cCoords.indexOf(',')).toDouble();
                position_C.y = cCoords.substring(cCoords.indexOf(',') + 1).toDouble();

                Serial.println("Updated anchor positions:");
                Serial.print("Self: x="); Serial.print(position_self.x); Serial.print(", y="); Serial.println(position_self.y);
                Serial.print("B: x="); Serial.print(position_B.x); Serial.print(", y="); Serial.println(position_B.y);
                Serial.print("C: x="); Serial.print(position_C.x); Serial.print(", y="); Serial.println(position_C.y);
            }
        }
   
}

void loop() {
    
    // Read anchor positions from serial
    if (Serial.available()){
      readAnchorPositions();
    }


    if(DW1000NgRTLS::receiveFrame()){
      Serial.print("aaaaaaa");
      
        size_t recv_len = DW1000Ng::getReceivedDataLength();
        byte recv_data[recv_len];
        DW1000Ng::getReceivedData(recv_data, recv_len);

        Serial.print(recv_data[7]); Serial.print(" "); Serial.print(recv_data[8]); Serial.print(" "); Serial.println(recv_data[9]);
        if(recv_data[0] == BLINK) {
            DW1000NgRTLS::transmitRangingInitiation(&recv_data[2], tag_shortAddress);
            DW1000NgRTLS::waitForTransmission();

            RangeAcceptResult result = DW1000NgRTLS::anchorRangeAccept(NextActivity::RANGING_CONFIRM, next_anchor);
            if(!result.success) return;
            range_self = result.range;

            String rangeString = "Range: "; rangeString += range_self; rangeString += " m";
            rangeString += "\t RX power: "; rangeString += DW1000Ng::getReceivePower(); rangeString += " dBm";
            //Serial.print(rangeString);

        } else if(recv_data[9] == 0x60) {
            double range = static_cast<double>(DW1000NgUtils::bytesAsValue(&recv_data[10],2) / 1000.0);
            String rangeReportString = "Range from: "; rangeReportString += recv_data[7];
            rangeReportString += " = "; rangeReportString += range;
            //Serial.println(rangeReportString);
            if(received_B == false && recv_data[7] == anchor_b[0] && recv_data[8] == anchor_b[1]) {
                range_B = range;
                received_B = true;
            } else if(recv_data[7] == anchor_c[0] && recv_data[8] == anchor_c[1]){
                range_C = range;
                double x,y;
                calculatePosition(x,y);
                // 두 원의 교점들에서 세 번째 앵커와 가까운 점의 무게중심을 구합니다.
                //Point centroid = calculateCentroidOfClosestIntersections(, y1, r1, x2, y2, r2, position_self, position_B, position_C);

                String positioning = "A=" ; positioning += range_self;
                positioning += "/B=" ; positioning += range_B;
                positioning += "/C=" ; positioning += range_C;
                positioning += "/x="; positioning += x;
                positioning += "/y="; positioning += y;
                Serial.println(positioning);

                if(Serial.available()) {
                  input = Serial.readStringUntil('\n');
                }
                if(Serial.available()==0 && input == cmd) {
    
                  /*Serial.println(positioning);
                  Serial.print("Self: x="); Serial.print(position_self.x); Serial.print(", y="); Serial.println(position_self.y);
                  Serial.print("B: x="); Serial.print(position_B.x); Serial.print(", y="); Serial.println(position_B.y);
                  Serial.print("C: x="); Serial.print(position_C.x); Serial.print(", y="); Serial.println(position_C.y);
                  */
                  input = "";
                }
                /*Serial.println(positioning);
                Serial.print("Self: x="); Serial.print(position_self.x); Serial.print(", y="); Serial.println(position_self.y);
                Serial.print("B: x="); Serial.print(position_B.x); Serial.print(", y="); Serial.println(position_B.y);
                Serial.print("C: x="); Serial.print(position_C.x); Serial.print(", y="); Serial.println(position_C.y);
                received_B = false;*/
            } else {
                received_B = false;
            }
        }
    }
    

    
}