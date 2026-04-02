"""
Script de diagnostic pour investiguer pourquoi un épisode source ne match pas dans le flux RSS.
"""
import asyncio
import os
import sys
from pathlib import Path

# Ajouter le répertoire parent au PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

from media_summarizer.utils import podcast_index


def _normalize(s: str) -> str:
    """Normalisation agressive actuelle (supprime accents)"""
    import re
    import unicodedata

    s = (s or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[\W_]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def _normalize_light(s: str) -> str:
    """Normalisation légère (garde accents, supprime juste ponctuation)"""
    import re
    s = (s or "").lower()
    # Remplace juste la ponctuation commune par des espaces (garde accents)
    s = re.sub(r"[()\[\]{},.;:!?'\"-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def main():
    # Épisode recherché
    target_title = "BEST OF - Le meilleur des auditeurs depuis le début de la saison"
    feed_id = 570656  # Les Grosses Têtes
    
    print(f"Recherche de l'épisode : '{target_title}'")
    print(f"Titre normalisé : '{_normalize(target_title)}'")
    print(f"\nRécupération des épisodes du feed {feed_id}...\n")
    
    # Récupérer les épisodes
    eps = await podcast_index.get_episodes_by_feed_id(feed_id=feed_id, max_results=250)
    episodes = eps.get("items", [])
    
    print(f"Nombre d'épisodes récupérés : {len(episodes)}\n")
    
    print("=" * 80)
    print("COMPARAISON: AVEC vs SANS NORMALISATION")
    print("=" * 80)
    
    # ===== AVEC NORMALISATION (approche actuelle) =====
    print("\n1. AVEC NORMALISATION (approche actuelle):\n")
    t_norm = _normalize(target_title)
    t_tokens = set(t_norm.split())
    
    candidates_normalized = []
    
    for e in episodes:
        e_title = e.get("title", "")
        e_norm = _normalize(e_title)
        
        # Vérifier si c'est un BEST OF ou contient "meilleur"
        if "best" in e_norm or "meilleur" in e_norm:
            e_tokens = set(e_norm.split())
            if e_tokens and t_tokens:
                inter = len(t_tokens & e_tokens)
                union = len(t_tokens | e_tokens)
                score = inter / union if union else 0.0
            else:
                score = 0.0
            
            candidates_normalized.append({
                "title": e_title,
                "normalized": e_norm,
                "score": score,
                "date": e.get("datePublished", ""),
            })
    
    candidates_normalized.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"Épisodes contenant 'best' ou 'meilleur' : {len(candidates_normalized)}")
    print(f"Meilleur score : {candidates_normalized[0]['score']:.3f}")
    print(f"Seuil requis : 0.600")
    print(f"Match trouvé : {'OUI' if candidates_normalized[0]['score'] >= 0.6 else 'NON'}\n")
    
    print("Top 5 candidats :")
    for i, c in enumerate(candidates_normalized[:5], 1):
        print(f"{i}. Score: {c['score']:.3f}")
        print(f"   Titre: {c['title'][:80]}")
        print()
    
    # ===== SANS NORMALISATION (test) =====
    print("\n" + "=" * 80)
    print("2. SANS NORMALISATION (test avec .lower() seulement):\n")
    
    t_lower = target_title.lower()
    t_tokens_raw = set(t_lower.split())
    
    candidates_raw = []
    
    for e in episodes:
        e_title = e.get("title", "")
        e_lower = e_title.lower()
        
        # Vérifier si c'est un BEST OF ou contient "meilleur"
        if "best" in e_lower or "meilleur" in e_lower:
            e_tokens_raw = set(e_lower.split())
            if e_tokens_raw and t_tokens_raw:
                inter = len(t_tokens_raw & e_tokens_raw)
                union = len(t_tokens_raw | e_tokens_raw)
                score = inter / union if union else 0.0
            else:
                score = 0.0
            
            candidates_raw.append({
                "title": e_title,
                "lower": e_lower,
                "score": score,
                "date": e.get("datePublished", ""),
            })
    
    candidates_raw.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"Épisodes contenant 'best' ou 'meilleur' : {len(candidates_raw)}")
    print(f"Meilleur score : {candidates_raw[0]['score']:.3f}")
    print(f"Seuil requis : 0.600")
    print(f"Match trouvé : {'OUI' if candidates_raw[0]['score'] >= 0.6 else 'NON'}\n")
    
    print("Top 5 candidats :")
    for i, c in enumerate(candidates_raw[:5], 1):
        print(f"{i}. Score: {c['score']:.3f}")
        print(f"   Titre: {c['title'][:80]}")
        print()
    
    # ===== AVEC NORMALISATION LÉGÈRE (test) =====
    print("\n" + "=" * 80)
    print("3. AVEC NORMALISATION LÉGÈRE (garde accents, supprime ponctuation):\n")
    
    t_light = _normalize_light(target_title)
    t_tokens_light = set(t_light.split())
    
    candidates_light = []
    
    for e in episodes:
        e_title = e.get("title", "")
        e_light = _normalize_light(e_title)
        
        # Vérifier si c'est un BEST OF ou contient "meilleur"
        if "best" in e_light or "meilleur" in e_light:
            e_tokens_light = set(e_light.split())
            if e_tokens_light and t_tokens_light:
                inter = len(t_tokens_light & e_tokens_light)
                union = len(t_tokens_light | e_tokens_light)
                score = inter / union if union else 0.0
            else:
                score = 0.0
            
            candidates_light.append({
                "title": e_title,
                "light": e_light,
                "score": score,
                "date": e.get("datePublished", ""),
            })
    
    candidates_light.sort(key=lambda x: x["score"], reverse=True)
    
    print(f"Épisodes contenant 'best' ou 'meilleur' : {len(candidates_light)}")
    print(f"Meilleur score : {candidates_light[0]['score']:.3f}")
    print(f"Seuil requis : 0.600")
    print(f"Match trouvé : {'OUI' if candidates_light[0]['score'] >= 0.6 else 'NON'}\n")
    
    print("Top 5 candidats :")
    for i, c in enumerate(candidates_light[:5], 1):
        print(f"{i}. Score: {c['score']:.3f}")
        print(f"   Titre: {c['title'][:80]}")
        print()

    # ===== COMPARAISON =====
    print("\n" + "=" * 80)
    print("CONCLUSION:\n")
    print(f"Score avec normalisation agressive : {candidates_normalized[0]['score']:.3f}")
    print(f"Score sans normalisation (raw)     : {candidates_raw[0]['score']:.3f}")
    print(f"Score avec normalisation légère    : {candidates_light[0]['score']:.3f}")
    print(f"\nMeilleure approche : ", end="")
    best_score = max(candidates_normalized[0]['score'], candidates_raw[0]['score'], candidates_light[0]['score'])
    if best_score == candidates_light[0]['score']:
        print("NORMALISATION LÉGÈRE")
    elif best_score == candidates_raw[0]['score']:
        print("SANS NORMALISATION")
    else:
        print("NORMALISATION AGRESSIVE")
    print("=" * 80)
    
    # Vérifier aussi les épisodes les plus récents
    print("\n\n10 épisodes les plus récents du feed :\n")
    recent = sorted(episodes, key=lambda x: x.get("datePublished", 0), reverse=True)[:10]
    for i, e in enumerate(recent, 1):
        print(f"{i}. {e.get('datePublished', 'No date')} - {e.get('title', 'No title')}")


if __name__ == "__main__":
    asyncio.run(main())
