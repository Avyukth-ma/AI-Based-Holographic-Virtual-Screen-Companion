import asyncio
import base64
import json
import logging
import time
from typing import Dict, List, Optional, Set
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.perception import get_perception_engine
from app.cognition import get_cognition_engine

logger = logging.getLogger("companion.websocket")
logger.setLevel(logging.INFO)

router = APIRouter()

class ConnectionManager:
    """Manages active WebSocket client connections and multimodal buffers."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.connection_metadata: Dict[WebSocket, dict] = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        self.connection_metadata[websocket] = {
            "connected_at": time.time(),
            "last_ping": time.time(),
            "camera_enabled": False,
            "mic_enabled": False,
            "is_processing_frame": False,
            "audio_buffer": bytearray(),
            "active_cognition_task": None,
            "companion_state": "idle",
            "system_status": "AWAKE",
            "fist_start_time": None,
            "last_victory_time": 0.0,
            "background_tasks": set(),
        }
        logger.info(f"Client connected. Active connections: {len(self.active_connections)}")

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
        if websocket in self.connection_metadata:
            meta = self.connection_metadata[websocket]
            for task in list(meta.get("background_tasks", set())):
                task.cancel()
            del self.connection_metadata[websocket]
        logger.info(f"Client disconnected. Active connections: {len(self.active_connections)}")

    async def send_json(self, websocket: WebSocket, data: dict):
        """Send JSON payload to a specific client."""
        try:
            await websocket.send_json(data)
        except Exception as e:
            logger.error(f"Error sending JSON to client: {e}")

    async def broadcast_json(self, data: dict):
        """Broadcast JSON payload to all connected clients."""
        for connection in self.active_connections:
            try:
                await connection.send_json(data)
            except Exception as e:
                logger.error(f"Broadcast error: {e}")

manager = ConnectionManager()

async def background_llm_task(websocket, user_text, vc_str, intent: str = "", image_b64: str | None = None):
    """Background task to generate and stream LLM sentence chunks with pipelined TTS synthesis."""
    cognition = get_cognition_engine()
    cognition.abort_requested = False
    cognition.is_generating = True
    meta = manager.connection_metadata.get(websocket)
    if meta:
        meta["companion_state"] = "thinking"

    try:
        await manager.send_json(websocket, {"type": "ai_state", "payload": {"state": "thinking"}})

        # Queue for assembled sentences: (sentence_str, model_name, is_done)
        sentence_queue: asyncio.Queue = asyncio.Queue()

        async def llm_producer():
            try:
                async for sentence, model_name in cognition.astream_sentences(user_text, visual_context=vc_str, intent=intent, image_b64=image_b64):
                    if cognition.abort_requested:
                        logger.info("LLM producer aborted by user.")
                        break
                    if sentence:
                        await sentence_queue.put((sentence, model_name, False))
            except Exception as e:
                logger.error(f"Error in LLM producer stream: {e}", exc_info=True)
            finally:
                await sentence_queue.put((None, None, True))

        producer_task = asyncio.create_task(llm_producer())

        chunk_idx = 0
        full_text_so_far = ""
        first_chunk_sent = False

        while True:
            if cognition.abort_requested:
                logger.info("Sentence consumer aborted by user.")
                break

            sentence, model_name, is_done = await sentence_queue.get()
            if is_done:
                break

            if sentence:
                if full_text_so_far:
                    full_text_so_far += " " + sentence
                else:
                    full_text_so_far = sentence

                speech_bytes = await cognition.synthesize_speech(sentence)
                if cognition.abort_requested:
                    logger.info("Synthesis completed but abort was requested; dropping chunk.")
                    break

                speech_b64 = base64.b64encode(speech_bytes).decode("utf-8") if speech_bytes else None

                if not first_chunk_sent:
                    if meta:
                        meta["companion_state"] = "speaking"
                    await manager.send_json(websocket, {"type": "ai_state", "payload": {"state": "speaking"}})
                    first_chunk_sent = True

                await manager.send_json(websocket, {
                    "type": "ai_audio_response",
                    "payload": {
                        "chunk_index": chunk_idx,
                        "text": sentence,
                        "accumulated_text": full_text_so_far,
                        "audio": speech_b64,
                        "state": "speaking",
                        "model": "Neural Core",
                        "timestamp": time.time(),
                        "is_final": False,
                    },
                })
                chunk_idx += 1

        if cognition.abort_requested:
            producer_task.cancel()
        else:
            await producer_task
            await manager.send_json(websocket, {
                "type": "ai_audio_response",
                "payload": {
                    "chunk_index": chunk_idx,
                    "text": "",
                    "accumulated_text": full_text_so_far,
                    "audio": None,
                    "state": "idle",
                    "model": "Neural Core",
                    "timestamp": time.time(),
                    "is_final": True,
                },
            })

    except asyncio.TimeoutError:
        logger.error("Timeout during cognition/speech generation")
        await manager.send_json(websocket, {"type": "ai_state", "payload": {"state": "error"}})
        await manager.send_json(websocket, {
            "type": "ai_audio_response",
            "payload": {
                "chunk_index": 0,
                "text": "The neural core took too long to respond.",
                "accumulated_text": "The neural core took too long to respond.",
                "audio": None,
                "state": "error",
                "timestamp": time.time(),
                "is_final": True,
            },
        })
    except Exception as e:
        logger.error(f"Error in background LLM task: {e}", exc_info=True)
    finally:
        cognition.is_generating = False
        if meta:
            meta["companion_state"] = "idle"
            meta["active_cognition_task"] = None

@router.websocket("/ws/companion")
async def websocket_companion_endpoint(websocket: WebSocket):
    """Main WebSocket endpoint for the real-time AI companion."""
    await manager.connect(websocket)
    perception = get_perception_engine()
    cognition = get_cognition_engine()

    await manager.send_json(websocket, {
        "type": "server_ready",
        "payload": {
            "message": "Connected to AI Companion Backend",
            "timestamp": time.time(),
            "status": "idle",
        },
    })
    await manager.send_json(websocket, {
        "type": "ai_state",
        "payload": {"state": "idle"}
    })

    try:
        while True:
            message = await websocket.receive()
            if message.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect(message.get("code", 1000))

            if "text" in message:
                try:
                    data = json.loads(message["text"])
                    msg_type = data.get("type", "unknown")
                    payload = data.get("payload", {})
                    meta = manager.connection_metadata.get(websocket, {})

                    if msg_type == "ping":
                        await manager.send_json(websocket, {
                            "type": "pong",
                            "payload": {"client_timestamp": payload.get("timestamp"), "server_timestamp": time.time()}
                        })

                    elif msg_type == "video_frame":
                        frame_b64 = payload.get("data")
                        client_ts = payload.get("timestamp")

                        if not meta.get("is_processing_frame", False) and frame_b64:
                            meta["is_processing_frame"] = True
                            try:
                                result = await asyncio.to_thread(perception.process_frame, frame_b64)
                                result["client_timestamp"] = client_ts
                                meta["latest_perception"] = result
                                
                                gesture_event = result.get("gesture_event", "None")
                                hands_data = result.get("hands", [])
                                gesture_canonical = hands_data[0].get("gesture", "None") if hands_data else "None"
                                gesture = gesture_canonical if gesture_canonical != "None" else gesture_event
                                
                                # Intercept Gestures for System Commands
                                current_status = meta.get("system_status", "AWAKE")
                                
                                # 1. Open Palm -> Pause Audio (Debounced)
                                if gesture in ["open_palm", "pause"]:
                                    current_llm_task = meta.get("active_cognition_task")
                                    companion_state = meta.get("companion_state", "idle")
                                    is_active = (current_llm_task and not current_llm_task.done()) or companion_state in ["speaking", "thinking"] or getattr(cognition, "is_generating", False)
                                    if is_active:
                                        logger.info("AI output interrupted.")
                                        cognition.abort_generation()
                                        if current_llm_task and not current_llm_task.done():
                                            current_llm_task.cancel()
                                        meta["active_cognition_task"] = None
                                        meta["companion_state"] = "idle"
                                        await manager.send_json(websocket, {
                                            "type": "ai_interrupted",
                                            "payload": {"reason": "gesture_abort", "gesture": "Open Palm", "timestamp": time.time()}
                                        })
                                
                                # 2. Fist -> Sleep/Standby
                                elif gesture in ["fist", "stop"]:
                                    if meta.get("fist_start_time") is None:
                                        meta["fist_start_time"] = time.time()
                                    elif time.time() - meta["fist_start_time"] >= 2.0 and current_status == "AWAKE" and meta.get("companion_state") != "sleep":
                                        logger.info("Standby Mode Activated (Fist Hold 2s)")
                                        meta["system_status"] = "SLEEPING"
                                        current_llm_task = meta.get("active_cognition_task")
                                        companion_state = meta.get("companion_state", "idle")
                                        is_active = (current_llm_task and not current_llm_task.done()) or companion_state in ["speaking", "thinking"] or getattr(cognition, "is_generating", False)
                                        if is_active:
                                            cognition.abort_generation()
                                        meta["companion_state"] = "sleep"
                                        if current_llm_task and not current_llm_task.done():
                                            current_llm_task.cancel()
                                        meta["active_cognition_task"] = None
                                        
                                        await manager.send_json(websocket, {
                                            "type": "state_change",
                                            "payload": {"state": "sleep"}
                                        })
                                        await manager.send_json(websocket, {
                                            "type": "ai_state",
                                            "payload": {"state": "sleep"}
                                        })
                                else:
                                    # Strict reset if gesture is not fist/stop
                                    meta["fist_start_time"] = None

                                # 3. Thumbs Up -> Wake
                                if gesture in ["thumbs_up", "like"]:
                                    if time.time() - meta.get("last_thumbs_up_time", 0.0) >= 4.0:
                                        meta["last_thumbs_up_time"] = time.time()
                                        if current_status == "SLEEPING" or meta.get("companion_state") == "sleep":
                                            logger.info("Companion Awakened to Idle (Thumbs Up)")
                                            meta["system_status"] = "AWAKE"
                                            meta["companion_state"] = "idle"
                                            meta["fist_start_time"] = None
                                            
                                            await manager.send_json(websocket, {
                                                "type": "state_change",
                                                "payload": {"state": "idle"}
                                            })
                                            await manager.send_json(websocket, {
                                                "type": "ai_state",
                                                "payload": {"state": "idle"}
                                            })
                                        elif current_status == "AWAKE" and meta.get("companion_state") == "idle":
                                            logger.info("Affirmation Received (Thumbs Up)")
                                            await manager.send_json(websocket, {
                                                "type": "state_change",
                                                "payload": {"state": "affirmation"}
                                            })
                                            bg_tasks = meta["background_tasks"]
                                            task = asyncio.create_task(background_llm_task(
                                                websocket,
                                                "The user gave an affirmative thumbs-up. Give a short, cheerful 1-sentence acknowledgment (e.g. 'Awesome, let's keep going!' or 'Understood!').",
                                                "User gave a thumbs up.",
                                                intent="greeting"
                                            ))
                                            meta["active_cognition_task"] = task
                                            bg_tasks.add(task)
                                            task.add_done_callback(bg_tasks.discard)

                                # 4. Victory -> Proactive Greeting (Greeting)
                                elif gesture in ["victory", "greeting"] and current_status == "AWAKE":
                                    if time.time() - meta.get("last_victory_time", 0.0) >= 6.0:
                                        logger.info("Proactive Greeting Triggered (Victory Sign)")
                                        meta["last_victory_time"] = time.time()
                                        
                                        bg_tasks = meta["background_tasks"]
                                        task = asyncio.create_task(background_llm_task(
                                            websocket,
                                            "The user just flashed the victory/peace sign. Give a brief, warm 1-sentence greeting acknowledging their gesture.",
                                            "User is throwing a peace sign.",
                                            intent="greeting"
                                        ))
                                        meta["active_cognition_task"] = task
                                        bg_tasks.add(task)
                                        task.add_done_callback(bg_tasks.discard)

                                # 5. Pointing Up -> Proactive Spatial Query (Scan)
                                elif gesture in ["pointing_up", "pointing", "point"] and current_status == "AWAKE":
                                    if time.time() - meta.get("last_point_time", 0.0) >= 6.0:
                                        latest_b64 = meta.get("latest_frame_b64")
                                        if latest_b64:
                                            logger.info("Scene Analysis Triggered (Pointing Up)")
                                            meta["last_point_time"] = time.time()
                                            
                                            # Explicitly reset abort state for fresh requests
                                            cognition.abort_requested = False
                                            
                                            # Extract directional finger context
                                            spatial_hint = ""
                                            if hands_data and "landmarks" in hands_data[0]:
                                                lms = hands_data[0]["landmarks"]
                                                if len(lms) >= 9:
                                                    wrist = lms[0]
                                                    tip = lms[8]
                                                    spatial_hint = f"The hand has the WRIST at ({wrist[0]}, {wrist[1]}) and INDEX_FINGER_TIP at ({tip[0]}, {tip[1]}), pointing diagonally upward and to the left toward the upper-middle/center portion of the frame. "

                                            rigorous_prompt = f"""You are a real-time, low-latency perceptual AI Companion.

The user is performing an active pointing gesture (☝️) in their workspace. Look closely at the video frame:
{spatial_hint}
- Trace a straight diagonal line extending directly up and to the left from the tip of the pointed index finger (visible on the mid-right side).
- Identify the target object exactly in this line of sight. (Note: There is a prominent collared/striped shirt hanging on a hanger or hook in the upper-middle background, just above the blacked-out area. It is NOT a lamp, ceiling fixture, or pendant light).
- Acknowledge their gesture, recognize the targeted object (e.g., the hanging striped shirt/jacket), and in 1-2 concise, natural sentences, check in with what they are pointing at (e.g. "I see you're pointing at the striped shirt hanging behind you, what's up?")."""

                                            bg_tasks = meta["background_tasks"]
                                            task = asyncio.create_task(background_llm_task(
                                                websocket,
                                                rigorous_prompt,
                                                "User is pointing up.",
                                                intent="vision",
                                                image_b64=latest_b64
                                            ))
                                            meta["active_cognition_task"] = task
                                            bg_tasks.add(task)
                                            task.add_done_callback(bg_tasks.discard)
                                        else:
                                            logger.warning("No camera frame available for Pointing Up gesture.")

                                await manager.send_json(websocket, {
                                    "type": "perception_result",
                                    "payload": result,
                                })
                                
                                if "gaze_x" in result and "gaze_y" in result:
                                    await manager.send_json(websocket, {
                                        "type": "gaze",
                                        "x": result["gaze_x"],
                                        "y": result["gaze_y"]
                                    })
                            finally:
                                meta["is_processing_frame"] = False

                    elif msg_type == "interrupt_request":
                        current_llm_task = meta.get("active_cognition_task")
                        companion_state = meta.get("companion_state", "idle")
                        is_active = (current_llm_task and not current_llm_task.done()) or companion_state in ["speaking", "thinking"] or getattr(cognition, "is_generating", False)
                        if is_active:
                            logger.info("User interrupt requested while active. Aborting generation.")
                            cognition.abort_generation()
                            meta["companion_state"] = "idle"
                            if current_llm_task and not current_llm_task.done():
                                current_llm_task.cancel()
                            meta["active_cognition_task"] = None
                            await manager.send_json(websocket, {
                                "type": "ai_interrupted",
                                "payload": {"reason": "user_interrupt", "timestamp": time.time()}
                            })

                    elif msg_type == "client_status":
                        if websocket in manager.connection_metadata:
                            manager.connection_metadata[websocket]["camera_enabled"] = payload.get("camera", False)
                            manager.connection_metadata[websocket]["mic_enabled"] = payload.get("mic", False)
                        await manager.send_json(websocket, {
                            "type": "status_ack",
                            "payload": {"status": "synced", "received": payload}
                        })

                    elif msg_type == "text_message":
                        if meta.get("system_status") == "SLEEPING":
                            logger.info("System is SLEEPING. Ignoring text message.")
                            await manager.send_json(websocket, {
                                "type": "status_ack",
                                "payload": {"status": "ignored_sleeping"}
                            })
                            continue
                            
                        user_text = payload.get("text", "") if isinstance(payload, dict) else str(payload)
                        logger.info(f"Received user text query: {user_text}")
                        
                        latest_perception = meta.get("latest_perception", {})
                        persons_data = latest_perception.get("persons", [])
                        faces_data = latest_perception.get("faces", [])
                        person_count = len(persons_data) if persons_data else len(faces_data)
                        hands_data = latest_perception.get("hands", [])
                        gesture_val = hands_data[0].get("gesture", "None") if hands_data else "None"
                        gaze_x = latest_perception.get("gaze_x")
                        gaze_y = latest_perception.get("gaze_y")
                        has_gaze = gaze_x is not None and (gaze_x != 0.0 or gaze_y != 0.0 or person_count > 0)
                        user_present = latest_perception.get("user_present", False) or person_count > 0 or has_gaze

                        if person_count > 0 or has_gaze or user_present or gesture_val != "None":
                            effective_count = max(person_count, 1)
                            gaze_detail = f" (gaze coordinates: x={gaze_x:.2f}, y={gaze_y:.2f})" if (gaze_x is not None and (gaze_x != 0.0 or gaze_y != 0.0)) else ""
                            vc_str = f"User is present in front of the camera ({effective_count} person(s) detected{gaze_detail}; Active Gesture: {gesture_val})."
                        else:
                            vc_str = "I don't see you in front of the camera."
                        
                        bg_tasks = meta["background_tasks"]
                        task = asyncio.create_task(background_llm_task(websocket, user_text, vc_str))
                        meta["active_cognition_task"] = task
                        bg_tasks.add(task)
                        task.add_done_callback(bg_tasks.discard)

                except json.JSONDecodeError:
                    logger.error("Failed to decode JSON text message.")

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"Unexpected WebSocket error: {e}", exc_info=True)
        manager.disconnect(websocket)
