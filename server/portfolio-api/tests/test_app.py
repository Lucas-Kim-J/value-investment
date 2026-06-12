import app


def test_fernet_secret_roundtrip():
    """Exchange API secrets are Fernet-encrypted at rest; decrypt must recover the plaintext."""
    assert app._dec_secret(app._enc_secret("s3cr3t-key")) == "s3cr3t-key"


def test_slugify_lowercases_and_dashes_non_alnum():
    assert app._slugify("Hello World! 测试") == "hello-world-测试"
