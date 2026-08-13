"""Selection and exclusion logic of scripts/purge_e2e_accounts.py.

This is the one place in the purge where a bug is catastrophic: a wrong `True`
deletes a real account and all of its data. No AWS call is involved here.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "purge_e2e_accounts.py"

_spec = importlib.util.spec_from_file_location("purge_e2e_accounts", SCRIPT)
assert _spec and _spec.loader
purge = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(purge)


PERMANENT_ACCOUNT = "e2e-maestro-20260809200952@test.local"


def user(email: str, user_id: str = "id-1") -> dict:
    return {"id": {"S": user_id}, "email": {"S": email}}


class TestIsPurgeable:
    def test_maestro_register_accounts_are_purgeable(self):
        assert purge.is_purgeable("e2e-register-31514654593-1-android@test.local")

    def test_pytest_fixture_accounts_are_purgeable(self):
        assert purge.is_purgeable("e2e-test-1786546452-004c74@test.local")

    def test_phase4_accounts_are_purgeable(self):
        assert purge.is_purgeable("phase4-test-1780952477@test.local")

    def test_permanent_maestro_account_is_protected(self):
        assert PERMANENT_ACCOUNT in purge.PROTECTED_EMAILS
        assert not purge.is_purgeable(PERMANENT_ACCOUNT)

    def test_case_and_whitespace_do_not_defeat_the_exclusion_list(self):
        assert not purge.is_purgeable(f"  {PERMANENT_ACCOUNT.upper()}  ")

    def test_real_account_is_never_purgeable(self):
        assert not purge.is_purgeable("a.real.person@example.com")

    def test_unknown_prefix_is_never_purgeable(self):
        assert not purge.is_purgeable("someone@test.local")
        assert not purge.is_purgeable("admin@test.local")

    def test_e2e_prefix_outside_the_test_domain_is_never_purgeable(self):
        assert not purge.is_purgeable("e2e-test-123@gmail.com")
        assert not purge.is_purgeable("e2e-register-1-ios@live.fr")

    def test_prefix_must_be_at_the_start_of_the_local_part(self):
        assert not purge.is_purgeable("real-e2e-test-1@test.local")

    def test_missing_or_empty_email_is_never_purgeable(self):
        assert not purge.is_purgeable(None)
        assert not purge.is_purgeable("")


class TestSelectAccounts:
    def test_splits_the_measured_dev_population(self):
        users = [
            user("e2e-register-31514654593-1-ios@test.local", "u1"),
            user("e2e-test-1786546452-004c74@test.local", "u2"),
            user("phase4-test-1780952477@test.local", "u3"),
            user(PERMANENT_ACCOUNT, "u4"),
            user("a.real.person@example.com", "u5"),
        ]

        to_purge, to_keep = purge.select_accounts(users)

        assert [item["id"]["S"] for item in to_purge] == ["u1", "u2", "u3"]
        assert [item["id"]["S"] for item in to_keep] == ["u4", "u5"]

    def test_row_without_email_is_kept(self):
        rows = [{"id": {"S": "orphan-row"}}]

        to_purge, to_keep = purge.select_accounts(rows)

        assert to_purge == []
        assert to_keep == rows


class TestScopeGuards:
    def test_only_dev_and_legacy_suffixes_are_allowed(self):
        assert purge.ALLOWED_SUFFIXES == ("-dev", "")
        assert "-staging" not in purge.ALLOWED_SUFFIXES
        assert "-prod" not in purge.ALLOWED_SUFFIXES

    def test_every_child_table_has_known_key_attributes(self):
        for base, _mode, keys in purge.CHILD_TABLES:
            assert purge.key_attributes_for(f"{base}-dev", "-dev") == keys
        assert (
            purge.key_attributes_for("media_artifacts-dev", "-dev")
            == purge.ARTIFACTS_KEY
        )
