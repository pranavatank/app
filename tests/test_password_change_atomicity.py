"""Password changes must preserve all encrypted secrets as one transaction."""

import base64

import pytest

import core.auth as auth
from core.database import get_connection
from core.encryption import decrypt_field, encrypt_field, derive_key


OLD_PASSWORD = "test-old-master-72!"
NEW_PASSWORD = "test-new-master-94!"


@pytest.fixture
def secret_records():
    conn = get_connection()
    conn.execute("DELETE FROM AuthSecurity")
    conn.execute("DELETE FROM BankAccount")
    conn.execute("DELETE FROM Person")
    conn.commit()
    conn.close()

    auth.setup_master_password(OLD_PASSWORD)
    record = auth._get_auth_record()
    salt = base64.b64decode(record["password_salt"])
    key = derive_key(OLD_PASSWORD, salt)
    conn = get_connection()
    person_id = conn.execute(
        "INSERT INTO Person (full_name, ais_tis_password_enc) VALUES (?, ?)",
        ("Atomicity fixture", encrypt_field("tax-secret", key)),
    ).lastrowid
    conn.commit()
    conn.close()
    conn = get_connection()
    account_ids = []
    for n, secret in enumerate(("bank-secret-one", "bank-secret-two")):
        account_ids.append(conn.execute(
            "INSERT INTO BankAccount (person_id, bank_name, account_type, statement_password_enc) VALUES (?, ?, ?, ?)",
            (person_id, f"Fixture Bank {n}", "Savings", encrypt_field(secret, key)),
        ).lastrowid)
    conn.commit()
    conn.close()
    return key, person_id, account_ids


def _snapshot():
    conn = get_connection()
    rows = {
        "auth": tuple(conn.execute("SELECT password_hash, password_salt FROM AuthSecurity").fetchone()),
        "banks": [tuple(r) for r in conn.execute("SELECT account_id, statement_password_enc FROM BankAccount ORDER BY account_id")],
        "people": [tuple(r) for r in conn.execute("SELECT person_id, ais_tis_password_enc FROM Person ORDER BY person_id")],
    }
    conn.close()
    return rows


def test_password_change_reencrypts_every_secret(secret_records):
    old_key, person_id, account_ids = secret_records
    ok, message, new_key = auth.change_password(OLD_PASSWORD, NEW_PASSWORD)
    assert ok, message
    assert new_key
    assert auth.verify_login(NEW_PASSWORD)[0]
    assert not auth.verify_login(OLD_PASSWORD)[0]

    conn = get_connection()
    try:
        for account_id, expected in zip(account_ids, ("bank-secret-one", "bank-secret-two")):
            value = conn.execute("SELECT statement_password_enc FROM BankAccount WHERE account_id=?", (account_id,)).fetchone()[0]
            assert decrypt_field(value, new_key) == expected
            with pytest.raises(Exception):
                decrypt_field(value, old_key)
        value = conn.execute("SELECT ais_tis_password_enc FROM Person WHERE person_id=?", (person_id,)).fetchone()[0]
        assert decrypt_field(value, new_key) == "tax-secret"
        with pytest.raises(Exception):
            decrypt_field(value, old_key)
    finally:
        conn.close()


def test_wrong_old_password_does_not_mutate_anything(secret_records):
    before = _snapshot()
    ok, _, key = auth.change_password("wrong-old", NEW_PASSWORD)
    assert not ok and key is None
    assert _snapshot() == before


def test_secret_reencryption_failure_rolls_back_all_changes(secret_records, monkeypatch):
    before = _snapshot()

    def fail_encrypt(*args, **kwargs):
        raise ValueError("injected re-encryption failure")

    monkeypatch.setattr(auth, "encrypt_field", fail_encrypt)
    ok, _, key = auth.change_password(OLD_PASSWORD, NEW_PASSWORD)
    assert not ok and key is None
    assert _snapshot() == before


def test_sql_failure_rolls_back_secret_and_auth_updates(secret_records, monkeypatch):
    before = _snapshot()
    original_get_connection = auth.get_connection

    class FailingConnection:
        def __init__(self, conn):
            self._conn = conn

        def execute(self, sql, params=()):
            if sql.lstrip().startswith("UPDATE AuthSecurity"):
                raise RuntimeError("injected SQL failure")
            return self._conn.execute(sql, params)

        def __getattr__(self, name):
            return getattr(self._conn, name)

    monkeypatch.setattr(auth, "get_connection", lambda: FailingConnection(original_get_connection()))
    ok, _, key = auth.change_password(OLD_PASSWORD, NEW_PASSWORD)
    assert not ok and key is None
    assert _snapshot() == before
