"""
Test models for Media Summarizer tests.

This module provides test data models for use in tests,
helping to standardize test data and reduce code duplication.
"""
import uuid
import random
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, Optional, List, Union


class TestUser:
    """Test user data model."""

    @staticmethod
    def create(
        user_id: Optional[str] = None,
        email: Optional[str] = None,
        credits: int = 100,
        is_active: bool = True,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a test user.

        Args:
            user_id: User ID (optional, defaults to a random UUID)
            email: User email (optional, defaults to a generated email)
            credits: User credits (default: 100)
            is_active: Whether the user is active (default: True)
            created_at: User creation timestamp (optional, defaults to now)

        Returns:
            Dict representing a user
        """
        if user_id is None:
            user_id = str(uuid.uuid4())

        if email is None:
            email = f"user-{user_id[:8]}@example.com"

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        return {
            "id": user_id,
            "email": email,
            "credits": credits,
            "is_active": is_active,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat()
        }


class TestPodcast:
    """Test podcast data model."""

    @staticmethod
    def create(
        podcast_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        feed_url: Optional[str] = None,
        website: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a test podcast.

        Args:
            podcast_id: Podcast ID (optional, defaults to a random UUID)
            title: Podcast title (optional, defaults to a generated title)
            description: Podcast description (optional)
            feed_url: Podcast feed URL (optional, defaults to a generated URL)
            website: Podcast website URL (optional)
            created_at: Podcast creation timestamp (optional, defaults to now)

        Returns:
            Dict representing a podcast
        """
        if podcast_id is None:
            podcast_id = str(uuid.uuid4())

        if title is None:
            title = f"Test Podcast {podcast_id[:8]}"

        if feed_url is None:
            feed_url = f"https://example.com/feeds/{podcast_id}.xml"

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        return {
            "id": podcast_id,
            "title": title,
            "description": description,
            "feed_url": feed_url,
            "website": website,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat()
        }


class TestEpisode:
    """Test episode data model."""

    @staticmethod
    def create(
        episode_id: Optional[str] = None,
        podcast_id: Optional[str] = None,
        title: Optional[str] = None,
        description: Optional[str] = None,
        audio_url: Optional[str] = None,
        published_at: Optional[datetime] = None,
        duration: Optional[int] = None,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a test episode.

        Args:
            episode_id: Episode ID (optional, defaults to a random UUID)
            podcast_id: Podcast ID (optional, defaults to a random UUID)
            title: Episode title (optional, defaults to a generated title)
            description: Episode description (optional)
            audio_url: Episode audio URL (optional, defaults to a generated URL)
            published_at: Episode publication timestamp (optional, defaults to now)
            duration: Episode duration in seconds (optional)
            created_at: Episode creation timestamp (optional, defaults to now)

        Returns:
            Dict representing an episode
        """
        if episode_id is None:
            episode_id = str(uuid.uuid4())

        if podcast_id is None:
            podcast_id = str(uuid.uuid4())

        if title is None:
            title = f"Test Episode {episode_id[:8]}"

        if audio_url is None:
            audio_url = f"https://example.com/episodes/{episode_id}.mp3"

        if published_at is None:
            published_at = datetime.now(timezone.utc) - timedelta(days=1)

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        return {
            "id": episode_id,
            "podcast_id": podcast_id,
            "title": title,
            "description": description,
            "audio_url": audio_url,
            "published_at": published_at.isoformat(),
            "duration": duration,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat()
        }


class TestJob:
    """Test job data model."""

    @staticmethod
    def create(
        job_id: Optional[str] = None,
        user_id: Optional[str] = None,
        podcast_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        status: str = "pending",
        created_at: Optional[datetime] = None,
        updated_at: Optional[datetime] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Create a test job.

        Args:
            job_id: Job ID (optional, defaults to a random UUID)
            user_id: User ID (optional, defaults to a random UUID)
            podcast_id: Podcast ID (optional)
            episode_id: Episode ID (optional)
            status: Job status (default: "pending")
            created_at: Job creation timestamp (optional, defaults to now)
            updated_at: Job update timestamp (optional, defaults to now)
            metadata: Job metadata (optional)

        Returns:
            Dict representing a job
        """
        if job_id is None:
            job_id = str(uuid.uuid4())

        if user_id is None:
            user_id = str(uuid.uuid4())

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        if updated_at is None:
            updated_at = created_at

        if metadata is None:
            metadata = {}

        return {
            "id": job_id,
            "user_id": user_id,
            "podcast_id": podcast_id,
            "episode_id": episode_id,
            "status": status,
            "created_at": created_at.isoformat(),
            "updated_at": updated_at.isoformat(),
            "metadata": metadata
        }


class TestSummary:
    """Test summary data model."""

    @staticmethod
    def create(
        summary_id: Optional[str] = None,
        job_id: Optional[str] = None,
        episode_id: Optional[str] = None,
        main_topics: Optional[List[str]] = None,
        key_points: Optional[List[str]] = None,
        notable_quotes: Optional[List[str]] = None,
        conclusion: Optional[str] = None,
        created_at: Optional[datetime] = None,
        as_dict: bool = False
    ) -> Union[Dict[str, Any], Dict[str, Any]]:
        """
        Create a test summary.

        Args:
            summary_id: Summary ID (optional, defaults to a random UUID)
            job_id: Job ID (optional, defaults to a random UUID)
            episode_id: Episode ID (optional)
            main_topics: Main topics (optional)
            key_points: Key points (optional)
            notable_quotes: Notable quotes (optional)
            conclusion: Conclusion (optional)
            created_at: Summary creation timestamp (optional, defaults to now)
            as_dict: If True, return just the summary content without the wrapper (default: False)

        Returns:
            Dict representing a summary
        """
        if summary_id is None:
            summary_id = str(uuid.uuid4())

        if job_id is None:
            job_id = str(uuid.uuid4())

        if main_topics is None:
            main_topics = ["Topic 1", "Topic 2", "Topic 3"]

        if key_points is None:
            key_points = [
                "This is the first key point.",
                "This is the second key point.",
                "This is the third key point."
            ]

        if notable_quotes is None:
            notable_quotes = [
                "This is a notable quote from the podcast.",
                "This is another notable quote."
            ]

        if conclusion is None:
            conclusion = "This is the conclusion of the summary."

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        summary_content = {
            "main_topics": main_topics,
            "key_points": key_points,
            "notable_quotes": notable_quotes,
            "conclusion": conclusion
        }

        if as_dict:
            return summary_content

        return {
            "id": summary_id,
            "job_id": job_id,
            "episode_id": episode_id,
            "summary": summary_content,
            "created_at": created_at.isoformat(),
            "updated_at": created_at.isoformat()
        }


class TestCreditTransaction:
    """Test credit transaction data model."""

    @staticmethod
    def create(
        transaction_id: Optional[str] = None,
        user_id: Optional[str] = None,
        amount: int = 0,
        transaction_type: str = "purchase",
        description: Optional[str] = None,
        job_id: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Create a test credit transaction.

        Args:
            transaction_id: Transaction ID (optional, defaults to a random UUID)
            user_id: User ID (optional, defaults to a random UUID)
            amount: Transaction amount (default: 0)
            transaction_type: Transaction type (default: "purchase")
            description: Transaction description (optional)
            job_id: Job ID (optional)
            created_at: Transaction timestamp (optional, defaults to now)

        Returns:
            Dict representing a credit transaction
        """
        if transaction_id is None:
            transaction_id = str(uuid.uuid4())

        if user_id is None:
            user_id = str(uuid.uuid4())

        if description is None:
            if transaction_type == "purchase":
                description = "Credit purchase"
            elif transaction_type == "deduction":
                description = "Podcast processing"
            elif transaction_type == "refund":
                description = "Failed job refund"
            else:
                description = "Credit transaction"

        if created_at is None:
            created_at = datetime.now(timezone.utc)

        return {
            "id": transaction_id,
            "user_id": user_id,
            "amount": amount,
            "type": transaction_type,
            "description": description,
            "job_id": job_id,
            "created_at": created_at.isoformat()
        }


class TestFeedData:
    """Test RSS feed data."""

    @staticmethod
    def create_feed_entry(
        title: str,
        link: str,
        description: str = "",
        published: str = "",
        enclosures: Optional[List[Dict[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Create a test feed entry.

        Args:
            title: Entry title
            link: Entry link
            description: Entry description (optional)
            published: Entry publication date (optional)
            enclosures: Entry enclosures (optional)

        Returns:
            Dict representing a feed entry
        """
        if enclosures is None:
            enclosures = [
                {"type": "audio/mpeg", "href": f"{link}.mp3"}
            ]

        return {
            "title": title,
            "link": link,
            "description": description,
            "published": published,
            "enclosures": enclosures
        }

    @staticmethod
    def create_feed(
        title: str,
        link: str,
        description: str = "",
        entries: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """
        Create a test feed.

        Args:
            title: Feed title
            link: Feed link
            description: Feed description (optional)
            entries: Feed entries (optional)

        Returns:
            Dict representing a feed
        """
        if entries is None:
            entries = [
                TestFeedData.create_feed_entry(
                    title=f"{title} - Episode 1",
                    link=f"{link}/episode1",
                    description="This is the first episode.",
                    published="Mon, 01 Jan 2023 12:00:00 +0000"
                ),
                TestFeedData.create_feed_entry(
                    title=f"{title} - Episode 2",
                    link=f"{link}/episode2",
                    description="This is the second episode.",
                    published="Mon, 08 Jan 2023 12:00:00 +0000"
                )
            ]

        return {
            "feed": {
                "title": title,
                "link": link,
                "description": description,
                "image": {"href": f"{link}/image.jpg"}
            },
            "entries": entries
        }


class TestRSSFeed:
    """Test RSS feed data model."""

    @staticmethod
    def create(
        title: str = "Test Podcast Feed",
        link: str = "https://example.com/podcast",
        description: str = "A test podcast feed for testing purposes",
        language: str = "en-us",
        entries_count: int = 3,
        with_enclosures: bool = True
    ) -> Dict[str, Any]:
        """
        Create a test RSS feed.

        Args:
            title: Feed title (default: "Test Podcast Feed")
            link: Feed link (default: "https://example.com/podcast")
            description: Feed description (default: "A test podcast feed for testing purposes")
            language: Feed language (default: "en-us")
            entries_count: Number of entries to generate (default: 3)
            with_enclosures: Whether to include audio enclosures (default: True)

        Returns:
            Dict representing an RSS feed
        """
        feed_id = str(uuid.uuid4())

        entries = []
        for i in range(entries_count):
            episode_id = str(uuid.uuid4())
            entry = {
                "title": f"{title} - Episode {i+1}",
                "link": f"{link}/episode{i+1}",
                "description": f"This is episode {i+1} of the test podcast.",
                "published": (datetime.now(timezone.utc) - timedelta(days=i*7)).strftime("%a, %d %b %Y %H:%M:%S +0000"),
                "guid": episode_id
            }

            if with_enclosures:
                entry["enclosures"] = [
                    {
                        "url": f"{link}/episodes/{episode_id}.mp3",
                        "length": str(random.randint(10000000, 50000000)),
                        "type": "audio/mpeg"
                    }
                ]

            entries.append(entry)

        return {
            "version": "2.0",
            "channel": {
                "title": title,
                "link": link,
                "description": description,
                "language": language,
                "image": {
                    "url": f"{link}/image.jpg",
                    "title": title,
                    "link": link
                },
                "items": entries
            }
        }


class TestTranscription:
    """Test transcription data model."""

    @staticmethod
    def create(
        short: bool = True,
        paragraphs: int = 3,
        topic: str = "artificial intelligence",
        with_timestamps: bool = False,
        with_speaker_labels: bool = False
    ) -> str:
        """
        Create a test transcription.

        Args:
            short: Whether to create a short transcription (default: True)
            paragraphs: Number of paragraphs to generate (default: 3)
            topic: Main topic of the transcription (default: "artificial intelligence")
            with_timestamps: Whether to include timestamps (default: False)
            with_speaker_labels: Whether to include speaker labels (default: False)

        Returns:
            String representing a transcription
        """
        topics = {
            "artificial intelligence": [
                "machine learning algorithms",
                "neural networks",
                "deep learning",
                "natural language processing",
                "computer vision",
                "ethical implications of AI",
                "AI in healthcare",
                "autonomous vehicles",
                "reinforcement learning",
                "AI regulation"
            ],
            "climate change": [
                "global warming",
                "renewable energy",
                "carbon emissions",
                "sustainable development",
                "climate policy",
                "extreme weather events",
                "sea level rise",
                "biodiversity loss",
                "climate adaptation",
                "carbon capture"
            ],
            "technology": [
                "blockchain",
                "cloud computing",
                "Internet of Things",
                "cybersecurity",
                "5G networks",
                "quantum computing",
                "augmented reality",
                "virtual reality",
                "edge computing",
                "digital transformation"
            ]
        }

        # Default to AI topics if the specified topic isn't in our dictionary
        selected_topics = topics.get(topic.lower(), topics["artificial intelligence"])

        # Select a subset of topics based on the number of paragraphs
        selected_topics = random.sample(selected_topics, min(paragraphs, len(selected_topics)))

        paragraphs_text = []
        current_time = 0
        speakers = ["Speaker A", "Speaker B", "Speaker C"]

        for i, subtopic in enumerate(selected_topics):
            # Generate paragraph length based on short parameter
            sentences_count = random.randint(2, 5) if short else random.randint(8, 15)

            sentences = []
            current_speaker = random.choice(speakers) if with_speaker_labels else None

            for j in range(sentences_count):
                if with_timestamps:
                    minutes = current_time // 60
                    seconds = current_time % 60
                    timestamp = f"[{minutes:02d}:{seconds:02d}] "
                    current_time += random.randint(10, 30)
                else:
                    timestamp = ""

                speaker_label = f"{current_speaker}: " if current_speaker else ""

                if j == 0:
                    # First sentence introduces the topic
                    sentence = f"{timestamp}{speaker_label}Let's talk about {subtopic} as an important aspect of {topic}."
                elif j == sentences_count - 1:
                    # Last sentence concludes the topic
                    sentence = f"{timestamp}{speaker_label}That's why {subtopic} is crucial for understanding {topic}."
                else:
                    # Middle sentences provide details
                    templates = [
                        f"{timestamp}{speaker_label}Research has shown significant advancements in {subtopic} recently.",
                        f"{timestamp}{speaker_label}Many experts believe that {subtopic} will transform how we approach {topic}.",
                        f"{timestamp}{speaker_label}The challenges in {subtopic} include technical limitations and ethical considerations.",
                        f"{timestamp}{speaker_label}Companies are investing heavily in {subtopic} technologies.",
                        f"{timestamp}{speaker_label}The future of {subtopic} looks promising despite current limitations."
                    ]
                    sentence = random.choice(templates)

                sentences.append(sentence)

                # Occasionally change speaker if speaker labels are enabled
                if with_speaker_labels and random.random() > 0.7:
                    current_speaker = random.choice([s for s in speakers if s != current_speaker])

            paragraphs_text.append(" ".join(sentences))

        return "\n\n".join(paragraphs_text)
