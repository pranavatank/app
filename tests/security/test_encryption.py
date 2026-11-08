from core.encryption import generate_salt, hash_password, verify_password, derive_key


def test_password_hash_and_verify():
    salt = generate_salt()
    pwd = "S3cureP@ssw0rd"
    h = hash_password(pwd, salt)
    assert isinstance(h, str) and len(h) > 0
    assert verify_password(pwd, salt, h)
    assert not verify_password("wrong", salt, h)


def test_derive_key_consistency():
    salt = generate_salt()
    k1 = derive_key("password123", salt)
    k2 = derive_key("password123", salt)
    assert k1 == k2
