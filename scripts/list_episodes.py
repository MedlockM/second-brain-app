"""
Liste tous les épisodes d'un flux RSS et cherche une correspondance
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from media_summarizer.utils import podcast_index


async def main():
    feed_id = 570656  # Les Grosses Têtes
    target = "BEST OF - Le meilleur des auditeurs depuis le début de la saison"
    
    print(f"Récupération des 250 derniers épisodes du feed {feed_id}...")
    print(f"Recherche de: '{target}'")
    print("=" * 100)
    
    eps = await podcast_index.get_episodes_by_feed_id(feed_id=feed_id, max_results=250)
    episodes = eps.get("items", [])
    
    print(f"\nNombre d'épisodes récupérés: {len(episodes)}\n")
    
    # Chercher des correspondances potentielles
    print("Recherche de 'auditeurs' dans les titres:")
    print("-" * 100)
    
    found_auditeurs = False
    for e in episodes:
        title = e.get("title", "")
        if "auditeur" in title.lower():
            found_auditeurs = True
            date = e.get("datePublished", 0)
            print(f"✓ {date} - {title}")
    
    if not found_auditeurs:
        print("❌ Aucun épisode contenant 'auditeur' trouvé dans les 250 derniers épisodes")
    
    print("\n" + "=" * 100)
    print("\nRecherche de 'début' ou 'saison' dans les titres:")
    print("-" * 100)
    
    found_debut_saison = False
    for e in episodes:
        title = e.get("title", "")
        if "début" in title.lower() or "debut" in title.lower() or "saison" in title.lower():
            found_debut_saison = True
            date = e.get("datePublished", 0)
            print(f"✓ {date} - {title}")
    
    if not found_debut_saison:
        print("❌ Aucun épisode contenant 'début' ou 'saison' trouvé")
    
    print("\n" + "=" * 100)
    print("\nTous les BEST OF dans les 250 derniers épisodes:")
    print("-" * 100)
    
    best_ofs = [e for e in episodes if "best of" in e.get("title", "").lower()]
    print(f"\nTotal: {len(best_ofs)} épisodes BEST OF\n")
    
    for i, e in enumerate(best_ofs[:30], 1):  # Afficher les 30 premiers
        title = e.get("title", "")
        date = e.get("datePublished", 0)
        print(f"{i:3d}. {date} - {title}")
    
    if len(best_ofs) > 30:
        print(f"\n... et {len(best_ofs) - 30} autres BEST OF")


if __name__ == "__main__":
    asyncio.run(main())
