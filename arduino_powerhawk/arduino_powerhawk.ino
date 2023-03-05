#include <WiFi.h>
#include <WiFiUdp.h>
#include <AsyncTCP.h>
#include <ESPAsyncWebSrv.h>
#include <sstream>

// #include "esp_adc_cal.h"
// #include <driver/adc_common.h>
// #include <esp_wifi.h>

#include "powerhawk_websocket.hpp"

// WiFi network name and password:
const char *networkName = "To The Oasis";
const char *networkPswd = "deadbeef";

AsyncWebServer webserver(80);
powerhawk::powerhawk_websocket_type powerhawk_websocket(webserver);

using timestamp_t = unsigned long;

timestamp_t last_tx_us = 0;

int ref_pin = 36;
int in1_pin = 39;
int in2_pin = 34;
int in3_pin = 35;
int in4_pin = 32;

#define HIST_CNT 512

#define AMPS_LONG_HIST_CNT 512

float amps1_long_hist[AMPS_LONG_HIST_CNT];
float amps2_long_hist[AMPS_LONG_HIST_CNT];
float amps3_long_hist[AMPS_LONG_HIST_CNT];
float amps4_long_hist[AMPS_LONG_HIST_CNT];
int amps_long_hist_idx = 0;

int hist_idx = 0;

long in1_sq_hist[HIST_CNT];
long in2_sq_hist[HIST_CNT];
long in3_sq_hist[HIST_CNT];
long in4_sq_hist[HIST_CNT];

long in1_sq_sum = 0;
long in2_sq_sum = 0;
long in3_sq_sum = 0;
long in4_sq_sum = 0;

int16_t in1_hist[HIST_CNT];
int16_t in2_hist[HIST_CNT];
int16_t in3_hist[HIST_CNT];
int16_t in4_hist[HIST_CNT];

WiFiUDP Udp;

void connectToWiFi(const char *ssid, const char *pwd)
{
    Serial.println("Connecting to WiFi network: " + String(ssid));

    WiFi.begin(ssid, pwd);

    while (WiFi.status() != WL_CONNECTED)
    {
        delay(500);
        Serial.print(".");
    }

    Serial.println();
    Serial.println("WiFi connected!");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
}

void setup()
{
    for (int i = 0; i < HIST_CNT; i++)
    {
        in1_sq_hist[i] = 0;
        in2_sq_hist[i] = 0;
        in3_sq_hist[i] = 0;
        in4_sq_hist[i] = 0;

        in1_hist[i] = 0;
        in2_hist[i] = 0;
        in3_hist[i] = 0;
        in4_hist[i] = 0;
    }

    pinMode(ref_pin, INPUT);
    pinMode(in1_pin, INPUT);
    pinMode(in2_pin, INPUT);
    pinMode(in3_pin, INPUT);
    pinMode(in4_pin, INPUT);

    Serial.begin(115200);
    connectToWiFi(networkName, networkPswd);

    powerhawk_websocket.setup();

    webserver.on("/", HTTP_GET, [](AsyncWebServerRequest *request)
                 { request->send_P(200, "text/html", "HI!!", nullptr); });

    // Start webserver
    webserver.begin();
}

void loop()
{
    powerhawk_websocket.loop();

    timestamp_t now = micros();

    int ref = analogRead(ref_pin);
    int16_t in1 = (analogRead(in1_pin) - ref);
    int16_t in2 = (analogRead(in2_pin) - ref);
    int16_t in3 = (analogRead(in3_pin) - ref);
    int16_t in4 = (analogRead(in4_pin) - ref);

    long in1_sq = in1 * in1;
    long in2_sq = in2 * in2;
    long in3_sq = in3 * in3;
    long in4_sq = in4 * in4;

    in1_sq_sum += in1_sq - in1_sq_hist[hist_idx];
    in2_sq_sum += in2_sq - in2_sq_hist[hist_idx];
    in3_sq_sum += in3_sq - in3_sq_hist[hist_idx];
    in4_sq_sum += in4_sq - in4_sq_hist[hist_idx];

    in1_sq_hist[hist_idx] = in1_sq;
    in2_sq_hist[hist_idx] = in2_sq;
    in3_sq_hist[hist_idx] = in3_sq;
    in4_sq_hist[hist_idx] = in4_sq;

    in1_hist[hist_idx] = in1;
    in2_hist[hist_idx] = in2;
    in3_hist[hist_idx] = in3;
    in4_hist[hist_idx] = in4;

    hist_idx = (hist_idx + 1) % HIST_CNT;

    if ((long)(now - last_tx_us) > 1000000)
    {
        float reading_to_amps = 1.0 / 15.0;
        float amps1 = in1_sq_sum > 0 ? sqrt((float)(in1_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;
        float amps2 = in2_sq_sum > 0 ? sqrt((float)(in2_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;
        float amps3 = in3_sq_sum > 0 ? sqrt((float)(in3_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;
        float amps4 = in4_sq_sum > 0 ? sqrt((float)(in4_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;

        amps1_long_hist[amps_long_hist_idx] = amps1;
        amps2_long_hist[amps_long_hist_idx] = amps2;
        amps3_long_hist[amps_long_hist_idx] = amps3;
        amps4_long_hist[amps_long_hist_idx] = amps4;
        amps_long_hist_idx = (amps_long_hist_idx + 1) % AMPS_LONG_HIST_CNT;

        last_tx_us = now;

        String msg = String(amps1) + "," +
                        String(amps2) + "," +
                        String(amps3) + "," +
                        String(amps4);
                        
        Udp.beginPacket("10.1.10.11", 10243);
        Udp.write((const uint8_t *)msg.c_str(), msg.length());
        Udp.endPacket();

        if(powerhawk_websocket.count() > 0)
        {
            std::stringstream ss;
            ss << "{";
            ss << "\"t\": " << now;
            ss << ",\"amps1\": " << amps1;
            ss << ",\"amps2\": " << amps2;
            ss << ",\"amps3\": " << amps3;
            ss << ",\"amps4\": " << amps4;
            ss << ",\"amps1_scope\": ["; for (int i = 0; i < HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << in1_hist[(i + hist_idx) % HIST_CNT] * reading_to_amps; } ss << "]";
            ss << ",\"amps2_scope\": ["; for (int i = 0; i < HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << in2_hist[(i + hist_idx) % HIST_CNT] * reading_to_amps; } ss << "]";
            // ss << ",\"amps3_scope\": ["; for (int i = 0; i < HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << in3_hist[(i + hist_idx) % HIST_CNT] * reading_to_amps; } ss << "]";
            // ss << ",\"amps4_scope\": ["; for (int i = 0; i < HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << in4_hist[(i + hist_idx) % HIST_CNT] * reading_to_amps; } ss << "]";
            ss << ",\"amps_hist\": [";
            for (int i = 0; i < AMPS_LONG_HIST_CNT; i++)
            {
                if (i > 0) {ss << ',';} 
                ss << amps1_long_hist[(amps_long_hist_idx + i) % AMPS_LONG_HIST_CNT] + amps2_long_hist[(amps_long_hist_idx + i) % AMPS_LONG_HIST_CNT];
            }
            ss << "]";
            // ss << ",\"amps1_hist\": ["; for (int i = 0; i < AMPS_LONG_HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << amps1_long_hist[(amps_long_hist_idx + i) % AMPS_LONG_HIST_CNT]; } ss << "]";
            // ss << ",\"amps2_hist\": ["; for (int i = 0; i < AMPS_LONG_HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << amps2_long_hist[(amps_long_hist_idx + i) % AMPS_LONG_HIST_CNT]; } ss << "]";
            // ss << ",\"amps3_hist\": ["; for (int i = 0; i < AMPS_LONG_HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << amps3_long_hist[(amps_long_hist_idx + i) % AMPS_LONG_HIST_CNT]; } ss << "]";
            // ss << ",\"amps4_hist\": ["; for (int i = 0; i < AMPS_LONG_HIST_CNT; i++) { if (i > 0) {ss << ',';} ss << amps4_long_hist[(amps_long_hist_idx + i) % AMPS_LONG_HIST_CNT]; } ss << "]";
            ss << "}";
            auto s = ss.str();
            powerhawk_websocket.broadcast(s.data(), s.size());
        }
    }
}

