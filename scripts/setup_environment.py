#!/usr/bin/env python3
"""
Script de gestion d'environnement pour Media Summarizer.
Ce script aide à configurer et gérer les différents environnements (dev, prod).
"""

import argparse
import os
import shutil
import sys
from pathlib import Path
from typing import Dict, Optional


class EnvironmentManager:
    """Gestionnaire des configurations d'environnement."""

    def __init__(self, project_root: Optional[Path] = None):
        """
        Initialise le gestionnaire d'environnement.

        Args:
            project_root: Chemin racine du projet. Si None, détecté automatiquement.
        """
        self.project_root = project_root or self._find_project_root()
        self.env_configs = {
            "development": {
                "env_file": ".env.dev",
                "compose_file": "docker-compose.dev.yml",
                "whisper_model": "tiny",
                "sqs_config": "Tests rapides (1 msg, 120s timeout, heartbeat 60s)",
                "description": "Environnement de développement (modèle Whisper tiny, LocalStack)"
            },

            "production": {
                "env_file": ".env.prod",
                "compose_file": "docker-compose.prod.yml",
                "whisper_model": "large",
                "sqs_config": "Production stable (1 msg, 600s timeout, heartbeat 240s)",
                "description": "Environnement de production (modèle Whisper large, AWS prod)"
            }
        }

    def _find_project_root(self) -> Path:
        """Trouve automatiquement la racine du projet."""
        current = Path(__file__).parent.absolute()
        while current != current.parent:
            if (current / "pyproject.toml").exists():
                return current
            current = current.parent
        raise RuntimeError("Impossible de trouver la racine du projet")

    def list_environments(self) -> None:
        """Affiche la liste des environnements disponibles."""
        print("🌟 Environnements disponibles:")
        print("=" * 50)

        for env_name, config in self.env_configs.items():
            print(f"\n📋 {env_name.upper()}")
            print(f"   Description: {config['description']}")
            print(f"   Modèle Whisper: {config['whisper_model']}")
            print(f"   Config SQS: {config['sqs_config']}")
            print(f"   Fichier env: {config['env_file']}")
            print(f"   Docker Compose: {config['compose_file']}")

            # Vérifier si les fichiers existent
            env_file_exists = (self.project_root / config['env_file']).exists()
            compose_file_exists = (self.project_root / config['compose_file']).exists()

            print(f"   État: ", end="")
            if env_file_exists and compose_file_exists:
                print("✅ Prêt")
            elif env_file_exists:
                print("⚠️  Fichier env OK, Docker Compose manquant")
            elif compose_file_exists:
                print("⚠️  Docker Compose OK, fichier env manquant")
            else:
                print("❌ Non configuré")

    def setup_environment(self, environment: str, force: bool = False) -> None:
        """
        Configure un environnement spécifique.

        Args:
            environment: Nom de l'environnement (development, production)
            force: Forcer l'écrasement des fichiers existants
        """
        if environment not in self.env_configs:
            raise ValueError(f"Environnement '{environment}' non supporté. "
                           f"Environnements disponibles: {list(self.env_configs.keys())}")

        config = self.env_configs[environment]
        print(f"🚀 Configuration de l'environnement: {environment}")
        print(f"📝 {config['description']}")

        # Copier le fichier d'environnement
        self._setup_env_file(environment, config, force)

        # Créer le fichier Docker Compose si nécessaire
        self._setup_compose_file(environment, config, force)

        # Afficher les instructions de démarrage
        self._show_startup_instructions(environment, config)

    def _setup_env_file(self, environment: str, config: Dict, force: bool) -> None:
        """Configure le fichier d'environnement."""
        env_file_path = self.project_root / config['env_file']
        main_env_path = self.project_root / ".env"

        if env_file_path.exists():
            print(f"✅ Fichier {config['env_file']} existe déjà")
        else:
            print(f"❌ Fichier {config['env_file']} manquant")
            print("   Créez ce fichier en vous basant sur .env.example")

        # Créer ou mettre à jour le fichier .env principal
        if main_env_path.exists() and not force:
            response = input(f"Le fichier .env existe. Le remplacer par {config['env_file']}? (y/N): ")
            if response.lower() != 'y':
                print("❌ Configuration annulée")
                return

        if env_file_path.exists():
            shutil.copy2(env_file_path, main_env_path)
            print(f"✅ Fichier .env mis à jour avec la configuration {environment}")
        else:
            print(f"⚠️  Impossible de copier {config['env_file']} vers .env (fichier source manquant)")

    def _setup_compose_file(self, environment: str, config: Dict, force: bool) -> None:
        """Configure le fichier Docker Compose."""
        compose_file_path = self.project_root / config['compose_file']

        if compose_file_path.exists():
            print(f"✅ Fichier {config['compose_file']} existe")
        else:
            print(f"❌ Fichier {config['compose_file']} manquant")

    def _show_startup_instructions(self, environment: str, config: Dict) -> None:
        """Affiche les instructions de démarrage."""
        print(f"\n🎯 Instructions de démarrage pour {environment}:")
        print("=" * 50)

        if environment == "development":
            print("1. Démarrer LocalStack et l'infrastructure:")
            print("   docker-compose -f docker-compose.dev.yml --profile infrastructure up -d")
            print("\n2. Démarrer l'API:")
            print("   docker-compose -f docker-compose.dev.yml --profile api up -d")
            print("\n3. Démarrer les workers:")
            print("   docker-compose -f docker-compose.dev.yml --profile workers up -d")
            print("\n4. Ou démarrer tout en une fois:")
            print("   docker-compose -f docker-compose.dev.yml --profile full up -d")

        elif environment == "production":
            print("1. Vérifier les variables d'environnement:")
            print("   - OPENAI_API_KEY")
            print("   - STRIPE_API_KEY")
            print("   - AWS credentials (IAM role recommandé)")
            print("\n2. Démarrer les services:")
            print("   docker-compose -f docker-compose.prod.yml up -d")

        print(f"\n📊 Configuration:")
        print(f"   Modèle Whisper: {config['whisper_model']}")
        print(f"   SQS: {config['sqs_config']}")
        print("💡 Astuce: Utilisez 'docker-compose logs -f' pour suivre les logs")

    def check_requirements(self, environment: str) -> bool:
        """
        Vérifie que tous les prérequis sont remplis pour un environnement.

        Args:
            environment: Nom de l'environnement à vérifier

        Returns:
            True si tous les prérequis sont OK, False sinon
        """
        if environment not in self.env_configs:
            print(f"❌ Environnement '{environment}' non supporté")
            return False

        print(f"🔍 Vérification des prérequis pour {environment}:")

        all_ok = True
        config = self.env_configs[environment]

        # Vérifier les fichiers de configuration
        files_to_check = [
            (config['env_file'], "Fichier de configuration environnement"),
            (config['compose_file'], "Fichier Docker Compose"),
        ]

        for file_name, description in files_to_check:
            file_path = self.project_root / file_name
            if file_path.exists():
                print(f"✅ {description}: {file_name}")
            else:
                print(f"❌ {description}: {file_name} (MANQUANT)")
                all_ok = False

        # Vérifications spécifiques par environnement
        if environment == "development":
            # Vérifier Docker
            docker_available = shutil.which("docker") is not None
            if docker_available:
                print("✅ Docker installé")
            else:
                print("❌ Docker non trouvé")
                all_ok = False

        elif environment == "production":
            # Vérifier les variables critiques
            critical_vars = ["OPENAI_API_KEY", "STRIPE_API_KEY"]
            for var in critical_vars:
                if os.environ.get(var):
                    print(f"✅ Variable {var} définie")
                else:
                    print(f"⚠️  Variable {var} non définie")

        print(f"\n🎯 État global: {'✅ PRÊT' if all_ok else '❌ PROBLÈMES DÉTECTÉS'}")
        return all_ok

    def switch_environment(self, environment: str) -> None:
        """
        Bascule rapidement vers un environnement.

        Args:
            environment: Nom de l'environnement cible
        """
        if environment not in self.env_configs:
            raise ValueError(f"Environnement '{environment}' non supporté")

        config = self.env_configs[environment]
        print(f"🔄 Basculement vers l'environnement: {environment}")
        print(f"📋 Configuration: {config['whisper_model']} model, {config['sqs_config']}")
        print(f"💓 Heartbeat SQS: Renouvellement automatique de la visibilité")

        # Arrêter les services Docker actuels
        print("🛑 Arrêt des services Docker en cours...")
        os.system("docker-compose down 2>/dev/null")

        # Configurer le nouvel environnement
        self.setup_environment(environment, force=True)

        print(f"✅ Basculement vers {environment} terminé!")

        # Afficher les différences de performance attendues
        if environment == "development":
            print("⚡ Mode rapide activé: messages traités immédiatement avec heartbeat 60s")
        else:
            print("🏗️  Mode production: jobs longs protégés avec heartbeat 240s")

    def show_sqs_comparison(self) -> None:
        """Affiche une comparaison des configurations SQS."""
        print("📊 Comparaison des configurations SQS:")
        print("=" * 60)

        headers = ["Paramètre", "Développement", "Production"]
        rows = [
            ["Max Messages", "1 (séquentiel)", "1 (séquentiel)"],
            ["Wait Time", "1s (réactivité)", "20s (économique)"],
            ["Visibility Timeout", "120s (tests courts)", "600s (jobs longs)"],
            ["Heartbeat Interval", "60s (1 min)", "240s (4 min)"],
            ["Traitement", "Séquentiel + heartbeat", "Séquentiel + heartbeat"],
            ["Optimisé pour", "Tests rapides", "Jobs longs (30-60 min)"],
            ["Protection", "Double traitement", "Lease renewal auto"]
        ]

        # Affichage tableau
        col_widths = [max(len(str(row[i])) for row in [headers] + rows) + 2 for i in range(3)]

        # En-tête
        print("| " + " | ".join(headers[i].ljust(col_widths[i]) for i in range(3)) + " |")
        print("|" + "|".join("-" * (col_widths[i] + 2) for i in range(3)) + "|")

        # Lignes
        for row in rows:
            print("| " + " | ".join(str(row[i]).ljust(col_widths[i]) for i in range(3)) + " |")


def main():
    """Fonction principale du script."""
    parser = argparse.ArgumentParser(
        description="Gestionnaire d'environnements pour Media Summarizer",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples d'utilisation:
  python scripts/setup_environment.py list
  python scripts/setup_environment.py setup development
  python scripts/setup_environment.py setup production --force
  python scripts/setup_environment.py check production
  python scripts/setup_environment.py switch development
  python scripts/setup_environment.py compare
        """
    )

    parser.add_argument(
        "command",
        choices=["list", "setup", "check", "switch", "compare"],
        help="Commande à exécuter"
    )

    parser.add_argument(
        "environment",
        nargs="?",
        choices=["development", "production"],
        help="Environnement cible (requis pour setup, check, switch)"
    )

    parser.add_argument(
        "--force",
        action="store_true",
        help="Forcer l'écrasement des fichiers existants"
    )

    args = parser.parse_args()

    try:
        manager = EnvironmentManager()

        if args.command == "list":
            manager.list_environments()

        elif args.command == "setup":
            if not args.environment:
                print("❌ Erreur: environnement requis pour la commande 'setup'")
                parser.print_help()
                sys.exit(1)
            manager.setup_environment(args.environment, args.force)

        elif args.command == "check":
            if not args.environment:
                print("❌ Erreur: environnement requis pour la commande 'check'")
                parser.print_help()
                sys.exit(1)
            success = manager.check_requirements(args.environment)
            sys.exit(0 if success else 1)

        elif args.command == "switch":
            if not args.environment:
                print("❌ Erreur: environnement requis pour la commande 'switch'")
                parser.print_help()
                sys.exit(1)
            manager.switch_environment(args.environment)

        elif args.command == "compare":
            manager.show_sqs_comparison()

    except Exception as e:
        print(f"❌ Erreur: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
