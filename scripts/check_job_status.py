"""
Script pour vérifier l'état d'un job dans DynamoDB
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from media_summarizer.utils import database_async


async def main():
    job_id = "6a304157-f1a2-4101-8bee-36907e8c3b2c"
    
    print(f"Vérification du job: {job_id}\n")
    print("=" * 80)
    
    job = await database_async.get_processing_job_by_id(job_id)
    
    if not job:
        print(f"❌ Job {job_id} introuvable dans la base de données")
        return
    
    print(f"✓ Job trouvé\n")
    print(f"Status              : {job.status}")
    print(f"User ID             : {job.user_id}")
    print(f"Episode GUID        : {job.episode_guid}")
    print(f"Podcast title       : {job.podcast_title}")
    print(f"Episode title       : {job.episode_title}")
    print(f"Audio S3 key        : {job.audio_s3_key or '(none)'}")
    print(f"Transcript S3 key   : {job.transcript_s3_key or '(none)'}")
    print(f"Summary S3 key      : {job.summary_s3_key or '(none)'}")
    print(f"Quiz S3 key         : {job.quiz_s3_key or '(none)'}")
    print(f"Created at          : {job.created_at}")
    print(f"Completed at        : {job.completed_at or '(none)'}")
    print()
    print("=" * 80)
    print("\nRaisons possibles si l'épisode n'apparaît pas dans l'UI:\n")
    
    issues = []
    if not job.summary_s3_key:
        issues.append("❌ Pas de summary_s3_key")
    else:
        issues.append(f"✓ Summary S3 key présent: {job.summary_s3_key}")
        
    if not job.quiz_s3_key:
        issues.append("❌ Pas de quiz_s3_key")
    else:
        issues.append(f"✓ Quiz S3 key présent: {job.quiz_s3_key}")
    
    for issue in issues:
        print(issue)


if __name__ == "__main__":
    asyncio.run(main())
