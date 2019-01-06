#include <WiFi.h>
#include <WiFiUdp.h>

// WiFi network name and password:
const char * networkName = "jaysplace2";
const char * networkPswd = "deadbeef";

unsigned long scheduled_next_tick = 0;
unsigned long last_report_us = 0;
unsigned long last_tx_us = 0;

int ref_pin = 36;
int in1_pin = 39;
int in2_pin = 34;
int in3_pin = 35;
int in4_pin = 32;

//we want a period to be an even multiple of 60Hz
//1/60Hz = 16.7ms
//at 512 samples were 60Hz period:
//16.7ms / 512 = 65us
//1024 samples gives us 2 periods of 60Hz
unsigned long loop_us = 65;
#define HIST_CNT 512

int hist_idx = 0;

long in1_sq_hist[HIST_CNT];
long in2_sq_hist[HIST_CNT];
long in3_sq_hist[HIST_CNT];
long in4_sq_hist[HIST_CNT];

long in1_sq_sum = 0;
long in2_sq_sum = 0;
long in3_sq_sum = 0;
long in4_sq_sum = 0;


WiFiUDP Udp;

void connectToWiFi(const char * ssid, const char * pwd)
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
    for(int i = 0; i < HIST_CNT; i++) {
        in1_sq_hist[i] = 0;
        in2_sq_hist[i] = 0;
        in3_sq_hist[i] = 0;
        in4_sq_hist[i] = 0;
    }

    scheduled_next_tick = micros() + loop_us;
    pinMode(ref_pin, INPUT);
    pinMode(in1_pin, INPUT);
    pinMode(in2_pin, INPUT);
    pinMode(in3_pin, INPUT);
    pinMode(in4_pin, INPUT);

    Serial.begin(115200);
    connectToWiFi(networkName, networkPswd);
}

void loop()
{
    unsigned long now = micros();
    signed long time_til_tick = (signed long)(scheduled_next_tick - now);
    if(time_til_tick > 0) {
        return;
    }

    scheduled_next_tick += loop_us;

    int ref = analogRead(ref_pin);
    long in1 = (long)(analogRead(in1_pin) - ref);
    long in2 = (long)(analogRead(in2_pin) - ref);
    long in3 = (long)(analogRead(in3_pin) - ref);
    long in4 = (long)(analogRead(in4_pin) - ref);

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

    hist_idx = (hist_idx + 1) % HIST_CNT;

    float reading_to_amps = 1.0 / 15.0;
    float in1_rms = in1_sq_sum > 0 ? sqrt((float)(in1_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;
    float in2_rms = in2_sq_sum > 0 ? sqrt((float)(in2_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;
    float in3_rms = in3_sq_sum > 0 ? sqrt((float)(in3_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;
    float in4_rms = in4_sq_sum > 0 ? sqrt((float)(in4_sq_sum / HIST_CNT)) * reading_to_amps : 0.0;

    ///////////////////////////////////////////////////////////////////////////
    // REPORTING
    ///////////////////////////////////////////////////////////////////////////
    if(0) {  // raw heart signal diagnostics
        if((long)(now - last_report_us) > 0) {
            last_report_us = now;
            Serial.print(in1_rms);Serial.print(",");
            Serial.print(in2_rms);Serial.print(",");
            Serial.print(in3_rms);Serial.print(",");
            Serial.print(in4_rms);Serial.println();
        }
    }

    if(1) {  // raw heart signal diagnostics
        if((long)(now - last_tx_us) > 1000000) {
            last_tx_us = now;
            String msg = String(in1_rms) + "," + \
                         String(in2_rms) + "," + \
                         String(in3_rms) + "," + \
                         String(in4_rms);

            // Serial.print(amps);Serial.println();
            Udp.beginPacket("10.1.10.255", 10243);
            //unsigned char buf[] = "hi from jay...\r\n";
            //Udp.write(buf, sizeof(buf));
            Udp.write((const uint8_t*)msg.c_str(), msg.length());
            Udp.endPacket();
        }
    }
}
