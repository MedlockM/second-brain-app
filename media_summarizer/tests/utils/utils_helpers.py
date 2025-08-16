"""
Utility functions for tests.
"""
import json
import uuid
import datetime
import random
import string
import os
import tempfile
from typing import Any, Dict, List, Optional, Union, Tuple, Callable


def create_sqs_message(body: Union[Dict[str, Any], str], receipt_handle: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a mock SQS message for testing.
    
    Args:
        body: The message body as a dictionary or string
        receipt_handle: Optional receipt handle, generated if not provided
        
    Returns:
        A dictionary representing an SQS message
    """
    if receipt_handle is None:
        receipt_handle = f"receipt-{uuid.uuid4()}"
        
    return {
        "MessageId": f"msg-{uuid.uuid4()}",
        "ReceiptHandle": receipt_handle,
        "Body": json.dumps(body) if isinstance(body, dict) else body,
        "Attributes": {
            "SentTimestamp": str(int(datetime.datetime.now().timestamp() * 1000))
        }
    }


def create_api_auth_headers(user_id: str = None) -> Dict[str, str]:
    """
    Create authentication headers for API tests.
    
    Args:
        user_id: Optional user ID, generated if not provided
        
    Returns:
        A dictionary of headers including Authorization
    """
    if user_id is None:
        user_id = f"user-{uuid.uuid4()}"
        
    return {
        "Authorization": f"Bearer test-token-{user_id}",
        "Content-Type": "application/json"
    }


def mock_async_context_manager(return_value: Any = None):
    """
    Create a mock async context manager that returns a specified value.
    
    Args:
        return_value: The value to return from __aenter__
        
    Returns:
        A class that can be used as an async context manager in tests
    """
    class AsyncContextManagerMock:
        async def __aenter__(self):
            return return_value or self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return AsyncContextManagerMock()


def compare_dict_subset(subset: Dict[str, Any], full_dict: Dict[str, Any]) -> bool:
    """
    Check if all key-value pairs in subset exist in full_dict.
    
    Args:
        subset: The dictionary with keys to check
        full_dict: The dictionary to check against
        
    Returns:
        True if all key-value pairs in subset exist in full_dict
    """
    return all(key in full_dict and full_dict[key] == val for key, val in subset.items())


def generate_test_audio_metadata(duration_seconds: int = 1800) -> Dict[str, Any]:
    """
    Generate metadata for a test audio file.
    
    Args:
        duration_seconds: Duration of the audio in seconds
        
    Returns:
        A dictionary with audio metadata
    """
    file_size_bytes = duration_seconds * 16000 * 2  # Approximate size based on duration
    
    return {
        "duration": duration_seconds,
        "file_size": file_size_bytes,
        "sample_rate": 16000,
        "channels": 1,
        "format": "mp3",
        "bit_rate": 128000
    }


def format_iso_datetime(dt: Optional[datetime.datetime] = None) -> str:
    """
    Format a datetime as ISO 8601 string.
    
    Args:
        dt: Datetime to format, uses current time if None
        
    Returns:
        ISO 8601 formatted datetime string
    """
    if dt is None:
        dt = datetime.datetime.now(datetime.timezone.utc)
    return dt.isoformat()


def generate_random_string(length: int = 10) -> str:
    """
    Generate a random string of specified length.
    
    Args:
        length: Length of the string to generate
        
    Returns:
        A random string
    """
    return ''.join(random.choices(string.ascii_letters + string.digits, k=length))


def generate_random_email() -> str:
    """
    Generate a random email address for testing.
    
    Returns:
        A random email address
    """
    username = generate_random_string(8)
    domain = generate_random_string(6)
    return f"{username}@{domain}.com"


def create_temp_audio_file(duration_seconds: int = 10) -> Tuple[str, str]:
    """
    Create a temporary audio file for testing.
    
    Args:
        duration_seconds: Duration of the audio in seconds
        
    Returns:
        A tuple of (file_path, file_name)
    """
    # Create a temporary file
    fd, file_path = tempfile.mkstemp(suffix=".mp3")
    os.close(fd)
    
    # Write some random data to simulate an audio file
    # In a real test, you might want to use a real audio file or a library to generate one
    with open(file_path, "wb") as f:
        # Write some random bytes (1000 bytes per second of audio)
        f.write(os.urandom(duration_seconds * 1000))
    
    file_name = os.path.basename(file_path)
    return file_path, file_name


def create_temp_rss_feed(num_episodes: int = 3) -> str:
    """
    Create a temporary RSS feed XML file for testing.
    
    Args:
        num_episodes: Number of episodes to include in the feed
        
    Returns:
        The path to the temporary RSS feed file
    """
    # Create a temporary file
    fd, file_path = tempfile.mkstemp(suffix=".xml")
    os.close(fd)
    
    # Generate RSS feed content
    podcast_title = f"Test Podcast {generate_random_string(5)}"
    podcast_description = f"A test podcast for {podcast_title}"
    
    rss_content = f"""<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd">
  <channel>
    <title>{podcast_title}</title>
    <link>https://example.com/{generate_random_string(8)}</link>
    <description>{podcast_description}</description>
    <language>en-us</language>
    <itunes:author>Test Author</itunes:author>
    <itunes:image href="https://example.com/image-{generate_random_string(8)}.jpg"/>
"""
    
    # Add episodes
    for i in range(num_episodes):
        episode_title = f"Episode {i+1}: {generate_random_string(10)}"
        episode_description = f"Description for episode {i+1}"
        episode_guid = f"episode-{uuid.uuid4()}"
        episode_duration = random.randint(600, 3600)  # 10-60 minutes
        episode_size = episode_duration * 16000 * 2  # Approximate size
        
        rss_content += f"""    <item>
      <title>{episode_title}</title>
      <description>{episode_description}</description>
      <pubDate>{format_iso_datetime(datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=i))}</pubDate>
      <enclosure url="https://example.com/episode-{i+1}.mp3" length="{episode_size}" type="audio/mpeg"/>
      <guid isPermaLink="false">{episode_guid}</guid>
      <itunes:duration>{episode_duration // 60}:{episode_duration % 60:02d}</itunes:duration>
      <itunes:image href="https://example.com/episode-{i+1}-image.jpg"/>
    </item>
"""
    
    rss_content += """  </channel>
</rss>"""
    
    # Write the RSS feed to the file
    with open(file_path, "w") as f:
        f.write(rss_content)
    
    return file_path


def create_test_database_records(session, model_class, num_records: int = 5, **kwargs) -> List[Any]:
    """
    Create test records in the database.
    
    Args:
        session: SQLAlchemy session
        model_class: The model class to create instances of
        num_records: Number of records to create
        **kwargs: Additional fields to set on the records
        
    Returns:
        A list of created records
    """
    records = []
    
    for i in range(num_records):
        # Create a new instance with default values
        record = model_class(
            id=f"test-{uuid.uuid4()}",
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
            **kwargs
        )
        
        # Add to session
        session.add(record)
        records.append(record)
    
    # Commit the session
    session.commit()
    
    return records


def create_mock_response(status_code: int = 200, json_data: Optional[Dict[str, Any]] = None, text: str = ""):
    """
    Create a mock HTTP response object.
    
    Args:
        status_code: HTTP status code
        json_data: JSON data to return from .json() method
        text: Text to return from .text property
        
    Returns:
        A mock response object with common methods and properties
    """
    class MockResponse:
        def __init__(self, status_code, json_data, text):
            self.status_code = status_code
            self._json_data = json_data or {}
            self.text = text
            self.content = text.encode('utf-8') if text else b''
            
        async def json(self):
            return self._json_data
            
        async def __aenter__(self):
            return self
            
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
    
    return MockResponse(status_code, json_data, text)


def assert_dict_contains_subset(subset: Dict[str, Any], full_dict: Dict[str, Any], path: str = ""):
    """
    Assert that all key-value pairs in subset exist in full_dict.
    
    Args:
        subset: The dictionary with keys to check
        full_dict: The dictionary to check against
        path: Current path for nested dictionaries (used for error messages)
        
    Raises:
        AssertionError: If a key-value pair in subset doesn't exist in full_dict
    """
    for key, val in subset.items():
        current_path = f"{path}.{key}" if path else key
        
        assert key in full_dict, f"Key '{current_path}' not found in dictionary"
        
        if isinstance(val, dict) and isinstance(full_dict[key], dict):
            # Recursively check nested dictionaries
            assert_dict_contains_subset(val, full_dict[key], current_path)
        else:
            # Check values
            assert full_dict[key] == val, f"Value mismatch for key '{current_path}': expected {val}, got {full_dict[key]}"


def create_test_transcription(duration_seconds: int = 1800, words_per_second: float = 2.5) -> str:
    """
    Create a test transcription text.
    
    Args:
        duration_seconds: Duration of the audio in seconds
        words_per_second: Average words per second in the transcription
        
    Returns:
        A generated transcription text
    """
    # Common words to use in the transcription
    common_words = [
        "the", "be", "to", "of", "and", "a", "in", "that", "have", "I",
        "it", "for", "not", "on", "with", "he", "as", "you", "do", "at",
        "this", "but", "his", "by", "from", "they", "we", "say", "her", "she",
        "or", "an", "will", "my", "one", "all", "would", "there", "their", "what",
        "so", "up", "out", "if", "about", "who", "get", "which", "go", "me"
    ]
    
    # Sentence starters
    sentence_starters = [
        "I think", "We should", "The problem is", "It's important to", "Let me explain",
        "Consider this", "What if", "The key point is", "Remember that", "I believe",
        "The research shows", "According to", "In my experience", "The data suggests",
        "Many people say", "Experts agree that", "Studies indicate", "The evidence shows"
    ]
    
    # Sentence endings
    sentence_endings = [
        "right?", "you know?", "I think.", "that's for sure.", "without a doubt.",
        "in my opinion.", "based on the evidence.", "according to research.",
        "as we've discussed.", "as I mentioned earlier.", "which is interesting."
    ]
    
    # Calculate total words based on duration and words per second
    total_words = int(duration_seconds * words_per_second)
    
    # Generate sentences
    sentences = []
    words_generated = 0
    
    while words_generated < total_words:
        # Decide sentence length (5-15 words)
        sentence_length = random.randint(5, 15)
        
        # Ensure we don't exceed total words
        if words_generated + sentence_length > total_words:
            sentence_length = total_words - words_generated
        
        # Generate sentence
        if random.random() < 0.7:  # 70% chance to start with a sentence starter
            sentence = [random.choice(sentence_starters)]
            remaining_words = sentence_length - len(sentence[0].split())
        else:
            sentence = []
            remaining_words = sentence_length
        
        # Add random words
        sentence.extend(random.choices(common_words, k=remaining_words))
        
        # Add sentence ending
        if random.random() < 0.3:  # 30% chance to add an ending
            ending = random.choice(sentence_endings)
            sentence.append(ending)
        
        # Join words and capitalize first letter
        full_sentence = " ".join(sentence)
        full_sentence = full_sentence[0].upper() + full_sentence[1:]
        
        sentences.append(full_sentence)
        words_generated += len(full_sentence.split())
    
    # Join sentences
    transcription = " ".join(sentences)
    
    return transcription