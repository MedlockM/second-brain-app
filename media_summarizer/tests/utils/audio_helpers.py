"""
Utility functions for creating test audio files.
"""
import os
import tempfile
import subprocess
import shutil
from pathlib import Path


def create_test_audio_file(duration_seconds=5, sample_rate=16000, frequency=440):
    """
    Create a valid test audio file using FFmpeg, with fallback to WAV generation.

    Args:
        duration_seconds: Duration of the audio file in seconds
        sample_rate: Sample rate in Hz
        frequency: Frequency of the sine wave in Hz

    Returns:
        str: Path to the created audio file
    """
    # First try to create a simple WAV file (most reliable)
    try:
        return create_simple_wav_file(duration_seconds, sample_rate)
    except Exception:
        pass

    # If that fails, try FFmpeg
    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_file.close()

    try:
        # Use FFmpeg to generate a sine wave audio file (WAV format is more reliable)
        cmd = [
            "ffmpeg",
            "-f", "lavfi",
            "-i", f"sine=frequency={frequency}:duration={duration_seconds}:sample_rate={sample_rate}",
            "-c:a", "pcm_s16le",  # Use PCM encoding for WAV
            "-y",  # Overwrite output file
            temp_file.name
        ]

        # Run FFmpeg command
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )

        # Verify the file was created and has content
        if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
            return temp_file.name
        else:
            raise RuntimeError("FFmpeg failed to create audio file")

    except (subprocess.CalledProcessError, FileNotFoundError):
        # If FFmpeg fails or is not available, create a simple WAV file
        os.unlink(temp_file.name)  # Clean up the failed attempt
        return create_dummy_mp3_file()  # This now creates a WAV file


def create_dummy_mp3_file():
    """
    Create a simple WAV file that can be processed by Whisper.
    This is a fallback when FFmpeg is not available.
    """
    import struct
    import wave

    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_file.close()

    # Create a simple WAV file with silence
    sample_rate = 16000
    duration = 2  # seconds
    num_samples = sample_rate * duration

    with wave.open(temp_file.name, 'w') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate silence (zeros)
        silence = struct.pack('<' + 'h' * num_samples, *([0] * num_samples))
        wav_file.writeframes(silence)

    return temp_file.name


def create_simple_wav_file(duration_seconds=2, sample_rate=16000):
    """
    Create a simple WAV file with a sine wave that Whisper can process.

    Args:
        duration_seconds: Duration of the audio file in seconds
        sample_rate: Sample rate in Hz

    Returns:
        str: Path to the created WAV file
    """
    import struct
    import wave
    import math

    temp_file = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    temp_file.close()

    # Create a WAV file with a simple sine wave
    frequency = 440  # A4 note
    num_samples = sample_rate * duration_seconds

    with wave.open(temp_file.name, 'w') as wav_file:
        wav_file.setnchannels(1)  # mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)

        # Generate sine wave
        samples = []
        for i in range(num_samples):
            # Generate sine wave sample
            sample = int(16384 * math.sin(2 * math.pi * frequency * i / sample_rate))
            samples.append(sample)

        # Pack samples as 16-bit signed integers
        audio_data = struct.pack('<' + 'h' * len(samples), *samples)
        wav_file.writeframes(audio_data)

    return temp_file.name


def get_real_test_audio_file():
    """
    Get the path to a real audio file with speech for integration testing.

    This function looks for a real audio file in the test fixtures directory.
    If found, it copies it to a temporary location for use in tests.

    Returns:
        str: Path to the real test audio file, or None if not found
    """
    # Look for real audio files in the fixtures directory
    fixtures_audio_dir = Path(__file__).parent.parent / "fixtures" / "audio"

    # Common audio file extensions to look for
    audio_extensions = ['.wav', '.mp3', '.m4a', '.flac', '.ogg']

    for audio_file in fixtures_audio_dir.glob('*'):
        if audio_file.suffix.lower() in audio_extensions:
            # Copy the real audio file to a temporary location
            temp_file = tempfile.NamedTemporaryFile(suffix=audio_file.suffix, delete=False)
            temp_file.close()

            try:
                shutil.copy2(str(audio_file), temp_file.name)
                return temp_file.name
            except Exception as e:
                # If copy fails, clean up and continue
                try:
                    os.unlink(temp_file.name)
                except:
                    pass

    return None


def create_test_audio_file_with_fallback(duration_seconds=5, sample_rate=16000, frequency=440):
    """
    Create a test audio file, preferring real speech audio if available.

    This function first tries to use a real audio file with speech from the fixtures.
    If no real audio file is found, it falls back to generating a synthetic audio file.

    Args:
        duration_seconds: Duration of the audio file in seconds (used for synthetic audio)
        sample_rate: Sample rate in Hz (used for synthetic audio)
        frequency: Frequency of the sine wave in Hz (used for synthetic audio)

    Returns:
        str: Path to the created audio file
    """
    # First, try to get a real audio file
    real_audio_path = get_real_test_audio_file()
    if real_audio_path:
        return real_audio_path

    # Fall back to creating synthetic audio
    return create_test_audio_file(duration_seconds, sample_rate, frequency)


def cleanup_test_audio_file(file_path):
    """
    Clean up a test audio file.

    Args:
        file_path: Path to the audio file to delete
    """
    try:
        if os.path.exists(file_path):
            os.unlink(file_path)
    except OSError:
        pass  # Ignore cleanup errors
