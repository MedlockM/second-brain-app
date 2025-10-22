"""
Core services for the media summarizer application.

This module contains business logic services for:
- Payment processing via Stripe
- Credit management
- Email notifications
- External API integrations
"""

# Avoid importing heavy submodules at package import time to prevent unnecessary side-effects
# (e.g., importing legacy Stripe service when only V2 is needed).

__all__ = []
