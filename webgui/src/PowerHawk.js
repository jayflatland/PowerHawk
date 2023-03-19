import React, { useState, useEffect } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import C3Chart from 'react-c3js';
import 'c3/c3.css';

// function parse_csv(text) {
//     var lines = text.split(/\r?\n/);
//     var hdr = lines[0];
//     lines = lines.slice(1);
//     var columns = hdr.split(',');

//     var records = lines.map(line => {
//         return line.split(',')
//             .map((v, i) => {return {key: i, val: v};})
//             .reduce((accum, c) => {
//             accum[columns[c.key]] = c.val;
//             return accum;
//         }, {});
//     });
//     return records;
// }

export default function PowerHawk(props) {
    // const [socketUrl] = useState('ws://10.1.10.212/powerhawk');//prod
    const [socketUrl] = useState('ws://powerhawk.jayflatland.com/sensor');//prod
    // const [socketUrl] = useState('ws://10.1.10.223/powerhawk');//test
    const [state, setState] = useState({
        "amps1": 0.0,
        "amps2": 0.0,
        "amps1_scope": [],
        "amps2_scope": [],
        "kW": 0.0,
        "amps": 0.0,
        "amps_hist": [],
    });

    const { lastMessage, readyState } = useWebSocket(socketUrl);

    useEffect(() => {
        if (lastMessage !== null) {
            var d = JSON.parse(lastMessage.data);
            if (Object.keys(d).length === 0) {
                return;
            }
            // console.log(d);

            var amps = d.amps1 + d.amps2;
            var kW = amps * 240.0 * 1e-3;

            setState({
                    "amps1": d.amps1,
                    "amps2": d.amps2,
                    "amps1_scope": d.amps1_scope,
                    "amps2_scope": d.amps2_scope,
                    "kW": kW,
                    "amps": amps,
                    "amps_hist": d.amps_hist,
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
                    columns: [
                        ['amps1', ...state.amps1_scope],
                        ['amps2', ...state.amps2_scope]
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
