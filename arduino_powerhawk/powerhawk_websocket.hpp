#pragma once

#include <sstream>
// #include <list>
#include <AsyncTCP.h>
#include <ESPAsyncWebSrv.h>

namespace powerhawk
{
    class powerhawk_websocket_type
    {
    public:
        AsyncWebServer& webserver_;
        AsyncWebSocket ws_handler_;
        // long history_start_millis_ = 0;
        // long last_millis_ = 0;
        
        // struct datum
        // {
        //     long t_;
        //     float resistance_;
        //     float target_resistance_;
        //     float work_kcal_;
        // };
        // std::list<datum> history_;

        powerhawk_websocket_type(AsyncWebServer& webserver)
            : webserver_(webserver)
            , ws_handler_("/powerhawk")
        {
        }
        
        size_t count() const        
        {
            return ws_handler_.count();
        }

        void setup()
        {
            ws_handler_.onEvent(
                [this](
                    AsyncWebSocket *websocket,
                    AsyncWebSocketClient *client,
                    AwsEventType type,
                    void *arg,
                    uint8_t *data,
                    size_t len) {
                    on_event(websocket, client, type, arg, data, len);                    
                });
            webserver_.addHandler(&ws_handler_);
        }

        void loop()
        {
            ws_handler_.cleanupClients();
        }
        
        void broadcast(const char *data, size_t sz)
        {
            ws_handler_.textAll(data, sz);
        }

        // void broadcast(float resistance, float target_resistance, float work_kcal)
        // {
        //     long now = millis();
        //     long since_last = now - last_millis_;
        //     if(since_last > 20000)
        //     {
        //         history_.clear();
        //         history_start_millis_ = now;
        //     }
        //     last_millis_ = now;
        //     long t = now - history_start_millis_;

        //     history_.push_back(datum{t, resistance, target_resistance, work_kcal});
        //     std::stringstream ss;
        //     ss << "{\"t\": " << t 
        //        << ",\"resistance\": " << resistance
        //        << ",\"target_resistance\": " << target_resistance
        //        << ",\"work_kcal\": " << work_kcal << "}";
        //     auto s = ss.str();
        //     ws_handler_.textAll(s.data(), s.size());
        // }
        
        // void send_history(AsyncWebSocketClient *client)
        // {
        //     for(auto&& d : history_)
        //     {
        //         std::stringstream ss;
        //         ss << "{\"t\": " << d.t_ 
        //         << ",\"resistance\": " << d.resistance_
        //         << ",\"target_resistance\": " << d.target_resistance_
        //         << ",\"work_kcal\": " << d.work_kcal_ << "}";
        //         auto s = ss.str();
        //         ws_handler_.text(client->id(), s.data(), s.size());
        //     }
        // }
    
    private:
        void on_event(AsyncWebSocket *websocket, AsyncWebSocketClient *client, AwsEventType type,
                                void *arg, uint8_t *data, size_t len)
        {
            switch (type)
            {
            case WS_EVT_CONNECT:
            {
                Serial.printf("WebSocket client #%u connected from %s\n", client->id(), client->remoteIP().toString().c_str());
                // std::string s = std::to_string(ledState);
                // send_history(client);
            }
            break;
            case WS_EVT_DISCONNECT:
                Serial.printf("WebSocket client #%u disconnected\n", client->id());
                break;
            case WS_EVT_DATA:
                // handleWebSocketMessage(arg, data, len);
                break;
            case WS_EVT_PONG:
            case WS_EVT_ERROR:
                break;
            }
        }


    };

}
