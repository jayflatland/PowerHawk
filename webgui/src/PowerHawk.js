import React, { useState, useRef, useEffect } from 'react';
import useWebSocket, { ReadyState } from 'react-use-websocket';
import C3Chart from 'react-c3js';
import 'c3/c3.css';

export default function PowerHawk(props) {
    const [socketUrl] = useState('ws://10.1.10.212/powerhawk');
    const [state, setState] = useState({
        "in1": [],
        "in2": [],
        "in3": [],
        "in4": [],
    });

    const { lastMessage, readyState } = useWebSocket(socketUrl);

    const canvasRef = useRef(null)
    // const canvas = canvasRef.current
    // const context = canvas.getContext('2d')

    useEffect(() => {
        if (lastMessage !== null) {
            var d = JSON.parse(lastMessage.data);
            if (Object.keys(d).length === 0) {
                return;
            }
            // console.log(d);

            setState((prevState) => {
                // console.log(prevState);
                try {
                    return {
                        "in1": d.in1,
                        "in2": d.in2,
                        "in3": d.in3,
                        "in4": d.in4
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

    // console.log(state);
    return (
        <div>
            <span>The WebSocket is currently {connectionStatus}</span>
            <C3Chart
                data={{
                    // x: 'x',
                    columns: [
                        // ['x', ...state.times],
                        ['in1', ...state.in1],
                        ['in2', ...state.in2],
                        ['in3', ...state.in3],
                        ['in4', ...state.in4]
                    ]
                }}
                point={{ show: false }}
                axis={{
                    x:{show: false}
                    //, y:{min: -10000, max: 10000}
                }}
                transition={{duration: 0}}
            />
            {/* <canvas ref={canvasRef} {...props} /> */}
        </div>
    );
};
