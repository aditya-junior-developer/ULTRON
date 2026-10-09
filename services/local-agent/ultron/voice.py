import asyncio
import queue
import threading
import time
from pathlib import Path

from .store import Store


class Voice:
    """Optional on-device voice pipeline. Model downloads are user-controlled."""
    def __init__(self, store: Store):
        self.store = store
        self.state = "idle"
        self.error = None
        self.transcript = ""
        self.conversation_id = None
        self.thread = None
        self.stop_flag = threading.Event()
        self.speech_stop = threading.Event()
        self.events: queue.Queue = queue.Queue(maxsize=8)
        self.whisper = None
        self.piper = None
        self.speaking = False

    def status(self):
        return {"state": self.state, "error": self.error, "transcript": self.transcript,
                "conversation_id": self.conversation_id,
                "running": bool(self.thread and self.thread.is_alive()),
                "echo_mode": "half-duplex: microphone frames ignored during speaker playback; Stop interrupts immediately"}

    def start(self):
        if not self.store.settings()["microphone"]:
            raise ValueError("Microphone permission is disabled")
        if self.thread and self.thread.is_alive():
            return
        try:
            import sounddevice  # noqa: F401
            import faster_whisper  # noqa: F401
        except (ImportError, OSError) as exc:
            raise ValueError("Voice dependencies or the OS audio runtime are missing. Install the voice extra and verify audio devices.") from exc
        self.stop_flag.clear()
        self.error = None
        self.thread = threading.Thread(target=self._listen, daemon=True, name="ultron-voice")
        self.thread.start()

    def stop(self):
        self.stop_flag.set()
        self.interrupt()
        self.state = "idle"

    def interrupt(self):
        self.speech_stop.set()
        try:
            import sounddevice
            sounddevice.stop()
        except (ImportError, OSError):
            pass

    def _listen(self):
        try:
            import numpy as np
            import sounddevice as sd
            from faster_whisper import WhisperModel
            s = self.store.settings()
            model_path = Path(s["whisper_model"])
            if not model_path.is_dir():
                raise ValueError("Set Whisper model to an already downloaded local model directory; ULTRON will not silently download models")
            self.whisper = WhisperModel(str(model_path), device="cpu", compute_type="int8", cpu_threads=4)
            wake = None
            if s["wake_model"]:
                from openwakeword.model import Model
                if not Path(s["wake_model"]).is_file():
                    raise ValueError("Wake-word ONNX model file is missing")
                wake = Model(wakeword_models=[s["wake_model"]], inference_framework="onnx")
            frames = queue.Queue(maxsize=64)
            def callback(data, frame_count, timing, status):
                if not self.speaking:
                    try:
                        frames.put_nowait(data.copy())
                    except queue.Full:
                        pass
            self.state = "wake" if wake else "listening"
            recording, silence, active_until = [], 0, 0
            with sd.InputStream(samplerate=16000, channels=1, blocksize=1280, dtype="int16", callback=callback):
                while not self.stop_flag.is_set() and self.store.settings()["microphone"]:
                    try:
                        frame = frames.get(timeout=0.2).flatten()
                    except queue.Empty:
                        continue
                    if wake and time.time() > active_until and not recording:
                        prediction = wake.predict(frame)
                        if max(prediction.values(), default=0) < 0.6:
                            self.state = "wake"
                            continue
                        active_until = time.time() + 10
                        self.state = "listening"
                    energy = float(np.sqrt(np.mean((frame.astype(np.float32) / 32768) ** 2)))
                    if energy > 0.012:
                        recording.append(frame)
                        silence = 0
                    elif recording:
                        recording.append(frame)
                        silence += 1
                    if recording and (silence >= 10 or len(recording) >= 250):
                        self.state = "transcribing"
                        samples = np.concatenate(recording).astype(np.float32) / 32768
                        language = self.store.settings()["language"]
                        segments, info = self.whisper.transcribe(samples, language=None if language in {"auto", "hinglish"} else language,
                            beam_size=2, vad_filter=True)
                        text = " ".join(segment.text.strip() for segment in segments).strip()
                        self.transcript = text
                        if text:
                            if text.lower().strip(".! ") in {"stop", "silent", "stop speaking", "chup", "चुप"}:
                                self.interrupt()
                            else:
                                try:
                                    self.events.put_nowait({"text": text, "language": info.language})
                                except queue.Full:
                                    self.store.event("voice_busy", "Speech request queue full; utterance dropped")
                        recording, silence = [], 0
                        self.state = "wake" if wake else "listening"
        except Exception as exc:
            self.error = str(exc)[:500] if isinstance(exc, (ValueError, ImportError)) else f"{type(exc).__name__}: voice initialization failed"
            self.state = "error"
        finally:
            self.whisper = None

    async def speak(self, text: str):
        if not self.store.settings()["voice_enabled"]:
            return {"spoken": False, "reason": "Speech output is disabled"}
        return await asyncio.to_thread(self._speak, text)

    def _speak(self, text):
        import numpy as np
        import sounddevice as sd
        from piper.voice import PiperVoice
        from piper.config import SynthesisConfig
        s = self.store.settings()
        path = Path(s["voice_model"])
        if not path.is_file() or not Path(str(path) + ".json").is_file():
            raise ValueError("Set a downloaded Piper ONNX voice with its matching .onnx.json configuration")
        self.speech_stop.clear()
        self.speaking = True
        self.state = "speaking"
        try:
            voice = PiperVoice.load(str(path), use_cuda=False)
            synth = SynthesisConfig(length_scale=1 / s["speech_rate"])
            for chunk in voice.synthesize(text[:4000], syn_config=synth):
                if self.speech_stop.is_set():
                    return {"spoken": False, "interrupted": True}
                samples = np.frombuffer(chunk.audio_int16_bytes, dtype=np.int16).astype(np.float32) / 32768 * s["volume"]
                sd.play(samples, chunk.sample_rate)
                sd.wait()
            return {"spoken": True}
        finally:
            self.speaking = False
            self.state = "listening" if self.thread and self.thread.is_alive() else "idle"
