# Audio Filler Assets

This directory contains pre-recorded audio filler sounds for natural speech synthesis.

## Required Filler Audio

Filler sounds are injected before responses to mask TTS latency and make the agent sound more human.

### Fillers List

- `clear_throat.wav` - Subtle throat clearing (0.5-1 second)
- `hmm.wav` - Thinking sound "Hmm..." (0.5-1 second)
- `let_me_see.wav` - "Låt mig se här..." (1-2 seconds)
- `thinking.wav` - Thinking pause (0.5-1 second)
- `uh_huh.wav` - Acknowledgment sound (0.5 second)
- `well.wav` - "Well..." (0.5-1 second)

## Recording Guidelines

1. **Audio Quality**
   - Sample rate: 44.1 kHz or 48 kHz
   - Bit depth: 16-bit or 24-bit
   - Mono or stereo (stereo preferred for Teams)
   - Format: WAV (uncompressed)

2. **Recording Environment**
   - Quiet room with minimal background noise
   - Consistent distance from microphone
   - Same microphone used for voice cloning (if applicable)

3. **Natural Delivery**
   - Record multiple variations of each filler
   - Keep them subtle and natural
   - Avoid exaggerated sounds
   - Match your normal speaking style

4. **File Specifications**
   - Duration: 0.5-2 seconds per filler
   - Volume: Normalized to -3 dB
   - Fade in/out: Very short (10-20ms) if needed

## Using Fillers

Fillers are automatically injected by the audio synthesizer based on:
- Filler probability setting (default: 30%)
- Random selection from available fillers
- Context (e.g., thinking sounds for complex questions)

## Testing

Test fillers by:
1. Playing them individually to check quality
2. Testing injection in synthesizer
3. Adjusting probability settings
4. Ensuring they don't sound repetitive

## Placeholder Assets

For testing purposes, you can use:
- Silence (no filler)
- Simple beep (not recommended for production)
- Public domain filler sounds (ensure rights)

Replace with your actual recordings for production use.
