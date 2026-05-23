---
name: tts-integration
description: Integrate Text-to-Speech (Edge-TTS) for real-time voice output with streaming synthesis. Use when implementing TTS, voice output, Edge-TTS setup, or AI agent speech. Triggers for "text to speech", "TTS", "voice output", "Edge-TTS", "AI speech synthesis".
---

# Text-to-Speech Integration

Integrate Edge-TTS for low-latency, streaming text-to-speech output in AI agents.

## Trigger

- "text to speech"
- "TTS setup"
- "voice output"
- "Edge-TTS"
- "speech synthesis"
- "AI voice"

## Engine Selection

### Edge-TTS (Recommended)
- Free, no API key needed
- Neural voices (200+ across 50+ languages)
- Streaming output (sentence-level chunks)
- ~200ms to first audio
- Runs via WebSocket to Microsoft Edge TTS service

### Alternatives
| Engine | Latency | Cost | Quality | Notes |
|--------|---------|------|---------|-------|
| Edge-TTS | ~200ms | Free | Excellent | Microsoft neural voices |
| Piper TTS | ~100ms | Free | Good | Local, lightweight |
| Kokoro | ~150ms | Free | Good | ONNX, local |
| ElevenLabs | ~300ms | $0.30/1K chars | Best | Cloud, emotional control |
| Deepgram Aura-2 | ~100ms | $0.015/1K chars | Excellent | Cloud, ultra-low latency |

## Streaming TTS Architecture

```
LLM Token Stream
      │
      ▼
Sentence Splitter (buffer until ., !, ?, or ;)
      │
      ▼
SSML Processor (optional: add prosody, pauses, emphasis)
      │
      ▼
TTS Engine (Edge-TTS WebSocket)
      │
      ▼
Audio Chunk Buffer (queue of audio segments)
      │
      ▼
Audio Output (stream to speaker)
```

## Sentence-Level Streaming

The key to low latency: start TTS on the first complete sentence, not the full response.

```typescript
class StreamingTTS {
  private textBuffer: string = "";
  private audioQueue: AudioBuffer[] = [];
  private isPlaying: boolean = false;
  private voice: string = "en-US-EricNeural"; // Default voice

  // Called for each LLM token
  pushToken(token: string): void {
    this.textBuffer += token;

    // Check for sentence boundary
    const match = this.textBuffer.match(/^(.+[.!?;]\s*)(.*)$/s);
    if (match) {
      const sentence = match[1];
      this.textBuffer = match[2];
      this.synthesizeSentence(sentence);
    }
  }

  // Called when LLM finishes
  flush(): void {
    if (this.textBuffer.trim()) {
      this.synthesizeSentence(this.textBuffer);
    }
  }

  private async synthesizeSentence(text: string): Promise<void> {
    const audio = await this.edgeTTS.synthesize(text, {
      voice: this.voice,
      pitch: "+0Hz",
      rate: "+10%",  // Slightly faster for gaming
    });
    this.audioQueue.push(audio);
    this.playNext();
  }

  private playNext(): void {
    if (this.isPlaying || this.audioQueue.length === 0) return;
    this.isPlaying = true;
    const audio = this.audioQueue.shift()!;
    this.playAudio(audio).finally(() => {
      this.isPlaying = false;
      this.playNext();
    });
  }
}
```

## Edge-TTS Integration

```typescript
import { EdgeTTS } from "edge-tts";

interface TTSConfig {
  voice: string;         // Voice name (e.g., "en-US-EricNeural")
  pitch: string;         // e.g., "+0Hz", "-5Hz", "+10Hz"
  rate: string;          // e.g., "+0%", "+15%", "-10%"
  volume: string;        // e.g., "+0%"
}

// Voice personality mapping
const VOICE_PERSONALITIES: Record<string, TTSConfig> = {
  friendly: { voice: "en-US-GuyNeural", pitch: "+2Hz", rate: "+5%" },
  serious:  { voice: "en-US-EricNeural", pitch: "-3Hz", rate: "+0%" },
  excited:  { voice: "en-US-DavisNeural", pitch: "+8Hz", rate: "+15%" },
  calm:     { voice: "en-US-SteffanNeural", pitch: "-5Hz", rate: "-5%" },
  playful:  { voice: "en-US-JasonNeural", pitch: "+5Hz", rate: "+10%" },
};

function selectVoice(personality: string): TTSConfig {
  return VOICE_PERSONALITIES[personality] || VOICE_PERSONALITIES.friendly;
}
```

## SSML for Expressive Speech

```xml
<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis">
  <voice name="en-US-GuyNeural">
    <prosody rate="+10%" pitch="+5%">
      Watch out! There's a <emphasis level="strong">creeper</emphasis> behind you!
    </prosody>
    <break time="200ms"/>
    <prosody rate="+20%" pitch="+10%">
      Run!
    </prosody>
  </voice>
</speak>
```

## Audio Output (Node.js)

```typescript
import { Speaker } from "speaker"; // or "audio" package

function playAudio(audioData: Buffer): Promise<void> {
  return new Promise((resolve, reject) => {
    const speaker = new Speaker({
      channels: 1,
      bitDepth: 16,
      sampleRate: 24000,  // Edge-TTS default
    });

    speaker.write(audioData);
    speaker.end();
    speaker.on("finish", resolve);
    speaker.on("error", reject);
  });
}
```

## Voice Personality System

The TTS should reflect the AI's emotional state:

```typescript
interface VoiceModulation {
  pitch: string;    // e.g., "+5Hz" (happy), "-5Hz" (sad)
  rate: string;     // e.g., "+15%" (excited), "-10%" (tired)
  voice: string;    // Different neural voice per mood
}

const MOOD_VOICE_MAP: Record<string, VoiceModulation> = {
  happy:    { pitch: "+5Hz", rate: "+10%", voice: "en-US-GuyNeural" },
  sad:      { pitch: "-5Hz", rate: "-10%", voice: "en-US-SteffanNeural" },
  excited:  { pitch: "+10Hz", rate: "+20%", voice: "en-US-DavisNeural" },
  scared:   { pitch: "+8Hz", rate: "+25%", voice: "en-US-EricNeural" },
  calm:     { pitch: "+0Hz", rate: "+0%", voice: "en-US-SteffanNeural" },
  urgent:   { pitch: "+3Hz", rate: "+30%", voice: "en-US-DavisNeural" },
};
```

## Optimization

- Start TTS at first sentence boundary (don't wait for full response)
- Cache synthesized audio for common phrases ("Hello!", "Watch out!", "I'm on it!")
- Pre-synthesize the AI's name and common greetings on startup
- Use shorter sentences — they synthesize faster and sound more natural
- Limit TTS output length (max ~200 chars per chunk) to avoid long synthesis

## Error Handling

- TTS WebSocket timeout: fall back to Piper TTS (local)
- Audio device busy: queue audio and retry after 500ms
- Network failure: fall back to local Kokoro/Piper TTS
- Empty text: skip synthesis silently
- Rate limit: implement token bucket (max 50 TTS requests per minute)

## Performance Targets

| Metric | Target |
|--------|--------|
| TTFA (Time to First Audio) | < 200ms |
| Sentence synthesis time | < 300ms |
| Audio playback latency | < 50ms |
| Memory usage | < 100MB |
| Cache hit rate (phrases) | > 30% |
