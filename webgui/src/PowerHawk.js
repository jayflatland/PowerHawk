import React, { useState, useEffect } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import C3Chart from 'react-c3js';
import 'c3/c3.css';

export default function PowerHawk(props) {
    const [socketUrl] = useState('ws://10.1.10.212/powerhawk');
    const [state, setState] = useState({
        "in1": [],
        "in2": [],
        "kW": 0.0,
        "amps": 0.0,
        "kW_hist": [],
        "amps_hist": [],
    });

    const { lastMessage, readyState } = useWebSocket(socketUrl);

    
    function amps_rms(v) {
        return (v.reduce((p, c) => p + c*c, 0.0) / v.length) ** 0.5;
    }

    useEffect(() => {
        if (lastMessage !== null) {
            var d = JSON.parse(lastMessage.data);
            if (Object.keys(d).length === 0) {
                return;
            }
            // console.log(d);

            var amps = amps_rms(state.in1) + amps_rms(state.in2);
            var kW = amps * 240.0 * 1e-3;


            setState((prevState) => {
                // console.log(prevState);
                try {
                    return {
                        "in1": d.in1,
                        "in2": d.in2,
                        "kW": kW,
                        "amps": amps,
                        "kW_hist": [...prevState.kW_hist, kW],
                        "amps_hist": [...prevState.amps_hist, amps],
                    };
                }
                catch {
                    return prevState;
                }
            });
        }

        // const canvas = canvasRef.current
        // const context = canvas.getContext('2d')
        //Our first draw
        // context.fillStyle = '#0000ff';
        // context.fillRect(0, 0, context.canvas.width, context.canvas.height);

    }, [lastMessage]);

    const connectionStatus = {
        [ReadyState.CONNECTING]: 'Connecting',
        [ReadyState.OPEN]: 'Open',
        [ReadyState.CLOSING]: 'Closing',
        [ReadyState.CLOSED]: 'Closed',
        [ReadyState.UNINSTANTIATED]: 'Uninstantiated',
    }[readyState];
    
    return (
        <div>
            <span>The WebSocket is currently {connectionStatus}</span>
            <h1>Total Power is {state.kW.toFixed(2)}kW, {state.amps.toFixed(1)}A</h1>
            <C3Chart
                data={{
                    // x: 'x',
                    columns: [
                        // ['x', ...state.times],
                        ['in1', ...state.in1],
                        ['in2', ...state.in2]
                        // ['in3', ...state.in3],
                        // ['in4', ...state.in4]
                    ]
                }}
                point={{ show: false }}
                axis={{
                    x:{show: false},
                    y: {tick: { format: d => d.toFixed(0) } },
                    //, y:{min: -10000, max: 10000}
                }}
                transition={{duration: 0}}
            />
            <C3Chart
                data={{
                    columns: [
                        ['amps', ...state.amps_hist]
                    ]
                }}
                point={{ show: false }}
                axis={{
                    x: {show: false},
                    y: {tick: { format: d => d.toFixed(2) } },
                }}
                transition={{duration: 0}}
            />
        </div>
    );
};
