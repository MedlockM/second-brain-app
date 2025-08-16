# Test Audio Fixtures

This directory contains real audio files used for integration testing of the Whisper transcription functionality.

## Purpose

Integration tests require real audio files with speech content to properly validate the transcription pipeline. Synthetic audio (sine waves) doesn't produce meaningful transcriptions, so real voice recordings are needed for comprehensive testing.

## Adding Audio Files

### Recommended File Specifications

- **Format**: WAV, MP3, M4A, FLAC, or OGG
- **Duration**: 5-30 seconds (for faster test execution)
- **Content**: Clear speech in English
- **Quality**: Good quality recording without background noise
- **Size**: Keep files small (<1MB) for repository efficiency

### Naming Convention

Use descriptive names that indicate the content:
- `test_speech_sample.wav` - Generic speech sample
- `integration_test_voice.mp3` - Voice for integration testing
- `whisper_test_audio.wav` - Audio specifically for Whisper testing

### How to Add Audio Files

1. Place your audio file(s) in this directory
2. The test system will automatically detect and use them
3. Files are prioritized over synthetic audio generation
4. Multiple files are supported - the first found will be used

### Test Integration

The test system works as follows:

1. **Real Audio Priority**: Tests first look for real audio files in this directory
2. **Automatic Detection**: Any audio file with supported extensions will be found
3. **Fallback**: If no real audio is found, synthetic audio is generated
4. **Temporary Copies**: Real files are copied to temporary locations for test isolation

### File Usage in Tests

Real audio files are used in:
- Integration tests requiring actual transcription
- Worker component tests with real Whisper service
- End-to-end workflow validation tests

### Security & Privacy

- Only include audio you have rights to use
- Avoid personal or sensitive content
- Use short, generic speech samples
- Consider using public domain recordings

### Example Content Ideas

Good audio content for testing:
- "This is a test recording for the media summarizer application"
- "Testing the automatic transcription functionality with real speech"
- "Integration test audio sample for Whisper speech recognition"

### File Management

- Keep files small and focused on testing needs
- Update this README when adding new audio types
- Clean up unused or outdated audio files periodically

## Technical Details

### Supported Formats

The system looks for files with these extensions:
- `.wav` - Preferred for compatibility
- `.mp3` - Common format
- `.m4a` - Apple audio format
- `.flac` - Lossless compression
- `.ogg` - Open source format

### Integration Process

1. `get_real_test_audio_file()` scans this directory
2. First matching audio file is selected
3. File is copied to temporary location
4. Temporary path is returned to test
5. Cleanup happens after test completion

## Troubleshooting

### No Audio Files Found

If tests fall back to synthetic audio:
1. Check that audio files are in this directory
2. Verify file extensions are supported
3. Ensure files are not corrupted
4. Check file permissions

### Test Failures with Real Audio

If tests fail with real audio:
1. Verify audio quality and clarity
2. Check duration (very long files may timeout)
3. Ensure content is in English for expected results
4. Test file playback outside the application

### Adding Your First Audio File

1. Record or obtain a short speech sample
2. Convert to WAV format if possible
3. Place in this directory
4. Run integration tests to verify detection
5. Check test output for transcription quality

---

**Note**: This directory is essential for comprehensive integration testing. Without real audio files, tests will use synthetic alternatives that may not fully validate the transcription pipeline.