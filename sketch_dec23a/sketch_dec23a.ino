#include <WiFi.h>
#include <WiFiUdp.h>

// WiFi network name and password:
const char * networkName = "jaysplace2";
const char * networkPswd = "deadbeef";

unsigned long scheduled_next_tick = 0;
unsigned long last_report_us = 0;

int in1p_pin = 36;
int in1n_pin = 39;
// int in22a_pin = 34;
// int in22b_pin = 35;

unsigned long loop_us = 130;
float in1d_filt2 = 0.0;

//0.0 => 9
//2.8 => 15
//1.8 => 12
//11.1 => 43
//14.0 => 53
//12.9 => 47

#define IN1D2_HIST_CNT 512
float in1d2_hist[IN1D2_HIST_CNT];
int in1d2_hist_idx = 0;
float in1d2_sum = 0.0;

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

    //Udp.begin(12345);
}


void setup()
{
    for(int i = 0; i < IN1D2_HIST_CNT; i++) {
        in1d2_hist[i] = 0.0;
    }
    scheduled_next_tick = micros() + loop_us;
    pinMode(in1p_pin, INPUT);
    pinMode(in1n_pin, INPUT);
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

    float in1p = (float)analogRead(in1p_pin) / 4096.0 * 1000.0;
    float in1n = (float)analogRead(in1n_pin) / 4096.0 * 1000.0;

    float in1d = in1p - in1n;
    float in1d2 = in1d * in1d;

    in1d2_sum -= in1d2_hist[in1d2_hist_idx];
    in1d2_hist[in1d2_hist_idx] = in1d2;
    in1d2_sum += in1d2;
    in1d2_hist_idx = (in1d2_hist_idx + 1) % IN1D2_HIST_CNT;
    //in1d2_sum *= 0.9999;  //hack to make numerically stable.  don't accum float rounding error.
    float in1d_rms = sqrt(in1d2_sum / IN1D2_HIST_CNT);
    if(in1d2_sum < 0.0) {
        in1d_rms = 0.0;
    }

    float amps = (in1d_rms - 8.0) * 0.32;
    if(amps < 0.0) {
        amps = 0.0;
    }

    //in1d_filt2 = in1d_filt2 * 0.995 + in1d * in1d * 0.005;
    //float in1d_filt = sqrt(in1d_filt2);


    ///////////////////////////////////////////////////////////////////////////
    // REPORTING
    ///////////////////////////////////////////////////////////////////////////
    if(1) {  // raw heart signal diagnostics
        if((long)(now - last_report_us) > 1000000) {
            last_report_us = now;
            // Serial.print(100.0*in1p);Serial.print(",");
            // Serial.print(100.0*in1n);Serial.print(",");
            // Serial.print(in1d_rms);Serial.print(",");
            // Serial.print(in1d);Serial.println();
            Serial.print(amps);Serial.println();
            Udp.beginPacket("10.1.10.255", 12345);
            unsigned char buf[] = "hi from jay...\r\n";
            Udp.write(buf, sizeof(buf));
            Udp.endPacket();
        }
    }
}

//#include <WiFi.h>
//
//// WiFi network name and password:
//const char * networkName = "jaysplace2";
//const char * networkPswd = "deadbeef";
//
//// Internet domain to request from:
//const char * hostDomain = "google.com";
//const int hostPort = 80;

//const int BUTTON_PIN = 0;
//const int LED_PIN = 5;

//void setup()
//{
//  // Initilize hardware:
//  Serial.begin(115200);
//  //pinMode(BUTTON_PIN, INPUT);
//  //pinMode(LED_PIN, OUTPUT);
//
//  // Connect to the WiFi network (see function below loop)
//  //connectToWiFi(networkName, networkPswd);
//
//  //digitalWrite(LED_PIN, LOW); // LED off
//  //Serial.print("Press button 0 to connect to ");
//  //Serial.println(hostDomain);
//}
//
//void loop()
//{
//  /*
//  if (digitalRead(BUTTON_PIN) == LOW)
//  { // Check if button has been pressed
//    while (digitalRead(BUTTON_PIN) == LOW)
//      ; // Wait for button to be released
//
//    digitalWrite(LED_PIN, HIGH); // Turn on LED
//    requestURL(hostDomain, hostPort); // Connect to server
//    digitalWrite(LED_PIN, LOW); // Turn off LED
//  }
//  */
//  
//}

//void connectToWiFi(const char * ssid, const char * pwd)
//{
//  int ledState = 0;
//
//  printLine();
//  Serial.println("Connecting to WiFi network: " + String(ssid));
//
//  WiFi.begin(ssid, pwd);
//
//  while (WiFi.status() != WL_CONNECTED) 
//  {
//    // Blink LED while we're connecting:
//    digitalWrite(LED_PIN, ledState);
//    ledState = (ledState + 1) % 2; // Flip ledState
//    delay(500);
//    Serial.print(".");
//  }
//
//  Serial.println();
//  Serial.println("WiFi connected!");
//  Serial.print("IP address: ");
//  Serial.println(WiFi.localIP());
//}
//
//void requestURL(const char * host, uint8_t port)
//{
//  printLine();
//  Serial.println("Connecting to domain: " + String(host));
//
//  // Use WiFiClient class to create TCP connections
//  WiFiClient client;
//  if (!client.connect(host, port))
//  {
//    Serial.println("connection failed");
//    return;
//  }
//  Serial.println("Connected!");
//  printLine();
//
//  // This will send the request to the server
//  client.print((String)"GET / HTTP/1.1\r\n" +
//               "Host: " + String(host) + "\r\n" +
//               "Connection: close\r\n\r\n");
//  unsigned long timeout = micros();
//  while (client.available() == 0) 
//  {
//    if (micros() - timeout > 5000) 
//    {
//      Serial.println(">>> Client Timeout !");
//      client.stop();
//      return;
//    }
//  }
//
//  // Read all the lines of the reply from server and print them to Serial
//  while (client.available()) 
//  {
//    String line = client.readStringUntil('\r');
//    Serial.print(line);
//  }
//
//  Serial.println();
//  Serial.println("closing connection");
//  client.stop();
//}
//
//void printLine()
//{
//  Serial.println();
//  for (int i=0; i<30; i++)
//    Serial.print("-");
//  Serial.println();
//}
