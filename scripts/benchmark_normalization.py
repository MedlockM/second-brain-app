"""
Benchmark pour tester différentes stratégies de normalisation.
On teste avec des paires (titre Spotify, titre RSS) qui DEVRAIENT matcher.
"""
import re
import unicodedata
from typing import Callable, List, Tuple


def normalize_aggressive(s: str) -> str:
    """Approche actuelle : supprime accents ET ponctuation"""
    s = (s or "").lower()
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = unicodedata.normalize("NFC", s)
    s = re.sub(r"[\W_]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_light(s: str) -> str:
    """Normalisation légère : supprime ponctuation mais garde accents"""
    s = (s or "").lower()
    s = re.sub(r"[()[\]{},.;:!?'\"-]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def normalize_minimal(s: str) -> str:
    """Minimal : juste lower() et espaces multiples"""
    s = (s or "").lower()
    s = re.sub(r"\s+", " ", s).strip()
    return s


def jaccard_similarity(s1: str, s2: str, normalize_fn: Callable[[str], str]) -> float:
    """Calcule similarité Jaccard avec fonction de normalisation donnée"""
    t1 = set(normalize_fn(s1).split())
    t2 = set(normalize_fn(s2).split())
    if not t1 or not t2:
        return 0.0
    inter = len(t1 & t2)
    union = len(t1 | t2)
    return inter / union if union else 0.0


# Cas de test : paires (spotify_title, rss_title) qui DEVRAIENT matcher
# Plus des cas difficiles où les titres diffèrent légèrement
test_cases = [
    # Cas 1: Titres identiques
    (
        "Les secrets du succès",
        "Les secrets du succès",
        "identique"
    ),
    # Cas 2: Différence d'accents
    (
        "Café philo: Episode 1",
        "Cafe philo: Episode 1",
        "accents"
    ),
    # Cas 3: Différence de ponctuation
    (
        "L'histoire de Marie (partie 1/2)",
        "L'histoire de Marie partie 1/2",
        "ponctuation_simple"
    ),
    # Cas 4: Ponctuation avec numéros (problème actuel!)
    (
        "BEST OF - Le meilleur de la semaine (2/2)",
        "BEST OF - Le meilleur de la semaine (2/2)",
        "ponctuation_numeros"
    ),
    # Cas 5: Casse différente
    (
        "INTERVIEW DE JEAN DURAND",
        "Interview de Jean Durand",
        "casse"
    ),
    # Cas 6: Espaces multiples
    (
        "Le   podcast    tech",
        "Le podcast tech",
        "espaces"
    ),
    # Cas 7: Apostrophes différentes
    (
        "L'épisode du jour",
        "L'épisode du jour",
        "apostrophes"
    ),
    # Cas 8: Guillemets différents
    (
        'Episode "spécial"',
        "Episode «spécial»",
        "guillemets"
    ),
    # Cas 9: Tirets différents
    (
        "Paris – Lyon – Marseille",
        "Paris - Lyon - Marseille",
        "tirets"
    ),
    # Cas 10: Cas mixte difficile
    (
        "Tech'n'Talk - Épisode #42: L'IA (1/2)",
        "Tech'n'Talk Épisode 42 L'IA partie 1/2",
        "mixte_difficile"
    ),
]


def run_benchmark():
    strategies = [
        ("Aggressive (actuelle)", normalize_aggressive),
        ("Light", normalize_light),
        ("Minimal", normalize_minimal),
    ]
    
    print("=" * 100)
    print("BENCHMARK DES STRATÉGIES DE NORMALISATION")
    print("=" * 100)
    print("\nObjectif: tester quelle stratégie donne les MEILLEURS scores pour des paires qui DEVRAIENT matcher\n")
    
    results = {name: [] for name, _ in strategies}
    
    for i, (s1, s2, category) in enumerate(test_cases, 1):
        print(f"\n{'─' * 100}")
        print(f"Cas {i}: {category}")
        print(f"Spotify : {s1}")
        print(f"RSS     : {s2}")
        print()
        
        for name, fn in strategies:
            score = jaccard_similarity(s1, s2, fn)
            results[name].append(score)
            status = "✓" if score >= 0.6 else "✗"
            print(f"  {status} {name:20s}: {score:.3f}  (normalized: '{fn(s1)[:60]}...')")
    
    print("\n" + "=" * 100)
    print("RÉSULTATS GLOBAUX")
    print("=" * 100)
    print()
    
    for name, _ in strategies:
        scores = results[name]
        avg = sum(scores) / len(scores)
        above_threshold = sum(1 for s in scores if s >= 0.6)
        perfect = sum(1 for s in scores if s >= 0.95)
        
        print(f"{name:20s}:")
        print(f"  Score moyen       : {avg:.3f}")
        print(f"  Au-dessus de 0.6  : {above_threshold}/{len(scores)} ({100*above_threshold/len(scores):.1f}%)")
        print(f"  Quasi-parfait (>0.95) : {perfect}/{len(scores)} ({100*perfect/len(scores):.1f}%)")
        print()
    
    print("=" * 100)
    print("RECOMMANDATION")
    print("=" * 100)
    
    best_name = max(strategies, key=lambda x: sum(results[x[0]]) / len(results[x[0]]))[0]
    print(f"\nMeilleure stratégie: {best_name}")
    print("\nAnalyse:")
    print("- Si 'Aggressive' gagne: la suppression d'accents/ponctuation aide")
    print("- Si 'Light' gagne: garder les accents mais supprimer ponctuation est optimal")
    print("- Si 'Minimal' gagne: moins on normalise, mieux c'est")


if __name__ == "__main__":
    run_benchmark()
