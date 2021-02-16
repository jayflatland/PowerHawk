#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include <math.h>

const char* ssid = "jaysplace2";
const char* password = "deadbeef";

WiFiUDP Udp;


typedef float sample_t;
volatile unsigned long next;
volatile sample_t sample_val;

volatile sample_t running_mean;
volatile sample_t sample_rms;
volatile sample_t d_val;
volatile int d_state;

static const int sample_freq_hz = 1000;
static const int cpu_hz = 80000000;
static const int sample_period_clks = cpu_hz / sample_freq_hz;
static const float k_washout_mean = sample_freq_hz * 5.0;
static const float k_washout_rms = 64.0;
static const float k_washout_d = 64.0;

static unsigned long isr_cnt;
static unsigned long last_isr_cnt;

void inline servoISR(void){
  next += sample_period_clks;
  timer0_write(next);

  {
    sample_t reading;
    reading = (sample_t)analogRead(A0);

    if(running_mean == 0.0) {
      running_mean = reading;
    }
    running_mean = ((running_mean * k_washout_mean) - running_mean + reading) / k_washout_mean;

    sample_val = reading - running_mean;
  }

  {
    sample_t d;
    sample_t r;
    sample_t ms;

    d = sample_val * sample_val;
    r = sample_rms * sample_rms;
    
    ms = ((r * k_washout_rms) - r + d) / k_washout_rms;
    sample_rms = sqrt(ms);
  }

  {
    sample_t reading;
    reading = (sample_t)digitalRead(D1);
    d_val = ((d_val * k_washout_d) - d_val + reading) / k_washout_d;
    d_state = d_val > 0.01 ? 1 : 0;
  }

  isr_cnt++;
}

unsigned int localUdpPort = 4210;  // local port to listen on

int last_hb_cnt;
void setup() {
  sample_val = 0;
  running_mean = 0;
  sample_rms = 0;

  d_val = 0;
  d_state = 0;

  isr_cnt = 0;
  last_isr_cnt = 0;

  pinMode(D1, INPUT);

  noInterrupts();
  timer0_isr_init();
  timer0_attachInterrupt(servoISR);
  next=ESP.getCycleCount()+1000;
  timer0_write(next);
  interrupts();

  Serial.begin(115200);

  // Serial.printf("Connecting to %s ", ssid);
  // WiFi.begin(ssid, password);
  // while (WiFi.status() != WL_CONNECTED)
  // {
  //   delay(500);
  //   Serial.print(".");
  // }
  // Serial.println(" connected");

  // Udp.begin(localUdpPort);
  // Serial.printf("Now listening at IP %s, UDP port %d\n", WiFi.localIP().toString().c_str(), localUdpPort);
}

void loop() {
  if( last_isr_cnt != isr_cnt ) {
    last_isr_cnt = isr_cnt;
    Serial.print(sample_val);
    Serial.print('\t');
    Serial.print(sample_rms);
    Serial.print('\t');
    Serial.print(d_state);
    Serial.print('\n');
  }

  // Udp.beginPacket("10.1.10.10", Udp.remotePort());
  // Udp.write("hi");
  // Udp.endPacket();
}

