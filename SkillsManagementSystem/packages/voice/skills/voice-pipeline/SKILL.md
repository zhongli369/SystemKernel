---
name: voice-pipeline
description: Design and implement low-latency streaming voice pipelines for AI agents. Use when discussing voice architecture, STT-to-LLM-to-TTS pipeline, streaming audio, real-time voice interaction, or voice latency optimization. The target is sub-2-second voice response.
---

# Voice Pipeline Architecture

Design streaming voice pipelines for real-time AI agents. The goal is sub-2-second voice response latency through parallel async processing.

## Trigger

- "voice pipeline"
- "voice architecture"
- "STT TTS pipeline"
- "streaming voice"
- "real-time voice"
- "voice latency"
- "audio pipeline"

## Pipeline Architecture

```
Microphone Input
      │
      ▼
┌─────────────┐
│  STT Engine  │  (Whisper.cpp — streaming)
│  chunked     │  → partial transcripts as they arrive
└──────┬──────┘
       │ partial + final transcript
       ▼
┌─────────────┐
│  NLU Router  │  (classify intent: chat/command/question/emergency)
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  LLM Engine  │  (DeepSeek V4 — streaming)
│  context     │  → stream tokens as they generate
└──────┬──────┘
       │ tokens
       ▼
┌─────────────┐
│  TTS Engine  │  (Edge-TTS — streaming synthesis)
│  sentence    │  → sentence-level chunking for low latency
└──────┬──────┘
       │ audio chunks
       ▼
  Speaker Output
```

## Latency Budget (Target: < 2000ms total)

```
STT:       200ms  (streaming partial)
NLU:        50ms  (lightweight classifier)
LLM TTFT:  500ms  (time-to-first-token)
LLM gen:   800ms  (streaming generation)
TTS TTFA:  200ms  (time-to-first-audio)
TTS synth: 200ms  (remaining synthesis)
─────────────────
TOTAL:   ~1950ms
```

## Streaming vs Batch

### Streaming (required for < 2s)
- STT produces partial transcripts every 200ms
- LLM streams tokens as generated
- TTS starts synthesis on first sentence punctuation
- User hears first words while LLM is still generating

### Batch (unacceptable)
- STT waits for silence → full transcript
- LLM waits for full prompt → full response
- TTS waits for full response → full audio
- Total: 5-15 seconds

## Implementation Pattern

```typescript
interface VoicePipeline {
  // Start pipeline (called once)
  start(config: VoiceConfig): Promise<void>;

  // Push audio chunk from mic
  pushAudio(chunk: Float32Array): void;

  // Pipeline events
  on(event: "partial_transcript", cb: (text: string) => void): void;
  on(event: "final_transcript", cb: (text: string) => void): void;
  on(event: "llm_token", cb: (token: string) => void): void;
  on(event: "tts_audio", cb: (audio: Float32Array) => void): void;
  on(event: "speaking_start", cb: () => void): void;
  on(event: "speaking_end", cb: () => void): void;
  on(event: "interrupt", cb: () => void): void;

  // Stop pipeline
  stop(): void;
}
```

## Interrupt System

Users should be able to interrupt the AI mid-speech:
- Keyboard: Press any key to interrupt
- Voice: Detect user speech during AI response (duck AI audio)
- The interrupt must cleanly stop TTS, not crash the pipeline

```typescript
class InterruptHandler {
  private isSpeaking: boolean = false;
  private interruptCallback: (() => void) | null = null;

  onInterrupt(cb: () => void): void {
    // Stop current TTS, clear TTS queue
    // Send cancellation signal to LLM
    // Flush audio buffer
  }
}
```

## Voice Activity Detection (VAD)

- Use energy-based VAD for simple cases
- Use Silero VAD for accuracy (ONNX model, runs in browser/Node)
- Parameters: 300ms silence to end utterance, 100ms speech to start
- Noise floor calibration on pipeline start

## Audio Format Pipeline

```
Mic input:     PCM 16kHz mono 16-bit
STT input:     PCM 16kHz mono 16-bit (or float32)
STT output:    text (UTF-8)
LLM input:     text (UTF-8)
LLM output:    text (UTF-8)
TTS input:     SSML or plain text
TTS output:    PCM 24kHz mono 16-bit (Edge-TTS default)
Speaker:       PCM 24kHz mono 16-bit
```

## Error Recovery

- STT failure: retry with last 2s of audio buffer
- LLM timeout: send "I'm thinking..." TTS placeholder after 3s
- TTS failure: fall back to displaying text
- Audio device change: reinitialize audio context

## Benchmarks

Target metrics for the pipeline:
- STT accuracy: > 95% WER (word error rate)
- LLM TTFT: < 500ms
- TTS TTFA: < 200ms
- Pipeline memory: < 512MB total
- CPU usage: < 50% on 4-core machine
