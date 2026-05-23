---
name: stt-integration
description: Integrate Speech-to-Text (Whisper.cpp) for real-time voice input. Use when implementing STT, Whisper.cpp setup, streaming speech recognition, or voice input for AI agents. Triggers for "speech to text", "whisper", "voice input", "STT integration".
---

# Speech-to-Text Integration

Integrate Whisper.cpp for low-latency, streaming speech recognition in AI agents.

## Trigger

- "speech to text"
- "whisper.cpp"
- "voice recognition"
- "STT setup"
- "microphone input"
- "speech recognition"

## Engine Selection

### Whisper.cpp (Recommended)
- Runs locally, no API cost
- ~200ms latency for short utterances on CPU
- Models: tiny (75MB), base (150MB), small (500MB), medium (1.5GB), large (3GB)
- For real-time: use `tiny` or `base` model
- Language: supports 100+ languages (auto-detect)

### Alternatives
| Engine | Latency | Cost | Quality | Notes |
|--------|---------|------|---------|-------|
| Whisper.cpp tiny | ~200ms | Free | Good | Local, requires setup |
| Deepgram Nova-3 | ~100ms | $0.0059/min | Best | Cloud, real-time |
| Web Speech API | ~300ms | Free | Fair | Browser only |
| Azure Speech | ~200ms | $1/hr | Good | Cloud, many languages |

## Streaming STT Architecture

```
Microphone (continuous capture)
      │
      ▼
Audio Buffer (ring buffer, last 10s)
      │
      ▼
VAD (voice activity detection)
      │
      ├─→ Silence → accumulate in buffer
      │
      └─→ Speech detected → drain buffer into STT
                                    │
                                    ▼
                              Partial Result
                              (every 200ms while speaking)
                                    │
                                    ▼
                              Final Result
                              (after silence threshold)
```

## Implementation

### Whisper.cpp Server Mode

```bash
# Start whisper.cpp in server mode
./whisper-server \
  --model models/ggml-base.bin \
  --host 127.0.0.1 \
  --port 8080 \
  --language auto

# HTTP API
curl -X POST http://127.0.0.1:8080/inference \
  -F "file=@audio.wav" \
  -F "response_format=json"
```

### Node.js Client

```typescript
import { WhisperClient } from "./whisper-client";

interface STTConfig {
  model: "tiny" | "base" | "small";
  language: string | "auto";
  sampleRate: number;  // 16000
  vadThreshold: number; // 0.5
  silenceTimeout: number; // 300ms
}

class StreamingSTT {
  private audioBuffer: Float32Array[];
  private whisper: WhisperClient;
  private vad: VAD;

  async initialize(config: STTConfig): Promise<void> {
    // Start whisper.cpp server if not running
    // Connect WebSocket for streaming
    // Initialize VAD
  }

  pushAudio(samples: Float32Array): void {
    this.audioBuffer.push(samples);
    const isSpeech = this.vad.detect(samples);

    if (isSpeech && this.audioBuffer.length >= this.minChunkSize) {
      this.processChunk();
    }
  }

  private async processChunk(): Promise<void> {
    const chunk = this.audioBuffer.splice(0);
    const wav = this.encodeWAV(chunk);
    const result = await this.whisper.transcribe(wav);
    this.emit("transcript", result.text);
  }
}
```

### Audio Capture (Node.js)

```typescript
// Use node-record-lpcm16 or sox for mic capture
import { spawn } from "child_process";

function startMicCapture(sampleRate = 16000): ReadableStream {
  // Windows: use sox or arecord equivalent
  const sox = spawn("sox", [
    "-d",                    // default input device
    "-r", String(sampleRate),
    "-c", "1",              // mono
    "-b", "16",             // 16-bit
    "-e", "signed",         // signed PCM
    "-t", "raw",            // raw output
    "-",                    // stdout
  ]);
  return sox.stdout;
}
```

## Optimizations

### Latency Reduction
- Use `tiny` model for real-time (< 100ms per chunk)
- Process in 200ms chunks (3200 samples at 16kHz)
- Overlap chunks by 50ms to avoid word boundary issues
- Pre-warm the whisper model on startup

### Accuracy Improvement
- Apply noise suppression before STT
- Use a fixed audio gain (AGC — automatic gain control)
- Provide context hints (game vocabulary list)
- Post-process with Minecraft-specific word correction:
  ```
  "mind craft" → "Minecraft"
  "creeper" → "creeper" (correct)
  "diamond sword" → "diamond sword" (correct)
  ```

### Minecraft-Specific Vocabulary

Maintain a custom vocabulary list for the STT to bias toward:
```
creeper, enderman, netherite, pickaxe, crafting table,
elytra, redstone, diamond, emerald, obsidian, respawn,
enchantment, potion, shulker, wither, blaze, ghast
```

## Error Handling

- No speech detected for 10s → emit "silence_timeout" event
- STT confidence < 0.5 → ask for clarification ("What did you say?")
- Audio device not found → list available devices with diagnostic
- Chunk processing too slow → downgrade model from base→tiny
- Server crash → auto-restart whisper.cpp process

## Performance Targets

| Metric | Target |
|--------|--------|
| Chunk processing time | < 100ms |
| End-of-speech to final result | < 300ms |
| Memory usage (tiny model) | < 200MB |
| CPU usage (continuous) | < 30% on one core |
| Word Error Rate (gaming) | < 10% |
