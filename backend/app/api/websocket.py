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

                speech_bytes = None
                try:
                    speech_bytes = await asyncio.wait_for(cognition.synthesize_speech(sentence), timeout=6.0)
                except asyncio.TimeoutError:
                    logger.warning("TTS speech synthesis timed out (>6s); continuing without audio chunk.")
                except Exception as tts_err:
                    logger.warning(f"TTS synthesis error: {tts_err}")

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

async def speak_quick_phrase(websocket: WebSocket, text: str, state: str = "speaking"):
    """Synthesize and transmit a single fast reactive speech phrase without LLM latency."""
    cognition = get_cognition_engine()
    if cognition.abort_requested:
        return
    try:
        speech_bytes = await asyncio.wait_for(cognition.synthesize_speech(text), timeout=3.5)
        speech_b64 = base64.b64encode(speech_bytes).decode("utf-8") if speech_bytes else None
        
        await manager.send_json(websocket, {"type": "ai_state", "payload": {"state": state}})
        await manager.send_json(websocket, {
            "type": "ai_audio_response",
            "payload": {
                "chunk_index": 0,
                "text": text,
                "accumulated_text": text,
                "audio": speech_b64,
                "state": state,
                "model": "Reactive Gesture Engine",
                "timestamp": time.time(),
                "is_final": True,
            },
        })
    except Exception as e:
        logger.warning(f"Failed to play quick reactive phrase: {e}")

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

                        # Cache latest frame for vision queries and pointing inspection
                        if frame_b64:
                            meta["latest_frame_b64"] = frame_b64

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

                                # Maintain temporal streak to filter transient single-frame flickers
                                last_g = meta.get("last_seen_gesture")
                                if gesture == last_g and gesture not in ["None", "unknown"]:
                                    meta["gesture_streak"] = meta.get("gesture_streak", 0) + 1
                                else:
                                    meta["last_seen_gesture"] = gesture
                                    meta["gesture_streak"] = 1
                                streak = meta.get("gesture_streak", 1)
                                
                                # Current system awake/sleep state
                                current_status = meta.get("system_status", "AWAKE")
                                companion_state = meta.get("companion_state", "idle")
                                is_busy = companion_state in ["speaking", "thinking"] or getattr(cognition, "is_generating", False)
                                
                                # 1. Open Palm -> Unconditional Immediate Pause / Interrupt
                                if gesture in ["open_palm", "pause"]:
                                    logger.info("Open Palm detected: Aborting AI output and returning to idle.")
                                    cognition.abort_generation()
                                    current_llm_task = meta.get("active_cognition_task")
                                    if current_llm_task and not current_llm_task.done():
                                        current_llm_task.cancel()
                                    meta["active_cognition_task"] = None
                                    meta["companion_state"] = "idle"
                                    await manager.send_json(websocket, {
                                        "type": "ai_interrupted",
                                        "payload": {"reason": "gesture_abort", "gesture": "Open Palm", "timestamp": time.time()}
                                    })
                                
                                # 2. Fist -> Sleep/Standby (Held for >= 1.0 second)
                                elif gesture in ["fist", "stop"]:
                                    if meta.get("fist_start_time") is None:
                                        meta["fist_start_time"] = time.time()
                                    elif time.time() - meta["fist_start_time"] >= 1.0 and current_status == "AWAKE" and meta.get("companion_state") != "sleep":
                                        logger.info("Standby Mode Activated (Fist Hold 1.0s)")
                                        meta["system_status"] = "SLEEPING"
                                        cognition.abort_generation()
                                        current_llm_task = meta.get("active_cognition_task")
                                        if current_llm_task and not current_llm_task.done():
                                            current_llm_task.cancel()
                                        meta["active_cognition_task"] = None
                                        meta["companion_state"] = "sleep"
                                        await manager.send_json(websocket, {"type": "state_change", "payload": {"state": "sleep"}})
                                        await manager.send_json(websocket, {"type": "ai_state", "payload": {"state": "sleep"}})
                                        asyncio.create_task(speak_quick_phrase(websocket, "Entering standby mode, sir.", state="sleep"))
                                else:
                                    meta["fist_start_time"] = None

                                # 3. Thumbs Up -> Wake if sleeping, or vocal confirmation if awake
                                if gesture in ["thumbs_up", "like"] and streak >= 2:
                                    if current_status == "SLEEPING" or meta.get("companion_state") == "sleep":
                                        logger.info("Companion Awakened to Idle (Thumbs Up)")
                                        meta["system_status"] = "AWAKE"
                                        meta["companion_state"] = "idle"
                                        meta["fist_start_time"] = None
                                        await manager.send_json(websocket, {"type": "state_change", "payload": {"state": "idle"}})
                                        await manager.send_json(websocket, {"type": "ai_state", "payload": {"state": "idle"}})
                                        asyncio.create_task(speak_quick_phrase(websocket, "Jarvis online, ready sir.", state="speaking"))
                                    elif current_status == "AWAKE" and not is_busy:
                                        if time.time() - meta.get("last_thumbs_up_time", 0.0) >= 4.0:
                                            meta["last_thumbs_up_time"] = time.time()
                                            await manager.send_json(websocket, {"type": "state_change", "payload": {"state": "affirmation"}})
                                            asyncio.create_task(speak_quick_phrase(websocket, "Affirmative, sir! Ready for your command.", state="affirmation"))

                                # 4. Victory / Peace -> Spoken Greeting and Holographic Arc Cyan
                                elif gesture in ["victory", "greeting"] and current_status == "AWAKE" and streak >= 2 and not is_busy:
                                    if time.time() - meta.get("last_victory_time", 0.0) >= 5.0:
                                        meta["last_victory_time"] = time.time()
                                        await manager.send_json(websocket, {"type": "state_change", "payload": {"state": "greeting"}})
                                        asyncio.create_task(speak_quick_phrase(websocket, "Greetings, sir! Arc reactor and neural cores are nominal.", state="speaking"))

                                # 5. Pointing Up -> Real-Time Camera Scan of Pointed Object
                                elif gesture in ["pointing_up", "pointing", "point"] and current_status == "AWAKE" and streak >= 2:
                                    if time.time() - meta.get("last_point_time", 0.0) >= 6.0:
                                        latest_b64 = meta.get("latest_frame_b64")
                                        if latest_b64:
                                            meta["last_point_time"] = time.time()
                                            logger.info("Scene Analysis Triggered (Pointing Up Gesture)")
                                            cognition.abort_generation()
                                            prev_task = meta.get("active_cognition_task")
                                            if prev_task and not prev_task.done():
                                                prev_task.cancel()
                                            cognition.abort_requested = False

                                            real_vision_prompt = (
                                                "You are an AI companion looking directly through the camera. "
                                                "The user is actively pointing at an object or area in their environment. "
                                                "Carefully inspect the image: identify what the user is pointing towards or displaying, "
                                                "and state what you see in 1-2 concise, natural sentences."
                                            )

                                            bg_tasks = meta["background_tasks"]
                                            task = asyncio.create_task(background_llm_task(
                                                websocket,
                                                real_vision_prompt,
                                                "User is pointing at an object in the camera frame.",
                                                intent="vision",
                                                image_b64=latest_b64
                                            ))
                                            meta["active_cognition_task"] = task
                                            bg_tasks.add(task)
                                            task.add_done_callback(bg_tasks.discard)

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
                        
                        # Cancel any previous still-running or hanging cognition task
                        prev_task = meta.get("active_cognition_task")
                        if prev_task and not prev_task.done():
                            logger.info("Cancelling prior unfinished cognition task for incoming query.")
                            cognition.abort_generation()
                            prev_task.cancel()
                        cognition.abort_requested = False

                        # Route classification and dynamic visual attachment
                        query_route = cognition.classify_query(user_text, vc_str)
                        attached_frame = meta.get("latest_frame_b64") if query_route == "vision" else None

                        bg_tasks = meta["background_tasks"]
                        task = asyncio.create_task(background_llm_task(
                            websocket,
                            user_text,
                            vc_str,
                            intent=query_route,
                            image_b64=attached_frame
                        ))
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
