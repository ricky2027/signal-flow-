import pytest
from app import retrieval


def test_private_dns_and_schemes_blocked(monkeypatch):
    monkeypatch.setattr(
        retrieval.socket,
        "getaddrinfo",
        lambda *a, **kw: [(2, 1, 6, "", ("127.0.0.1", 443))],
    )
    with pytest.raises(ValueError, match="Non-public DNS"):
        retrieval._fetch("https://public.example/page")
    with pytest.raises(ValueError):
        retrieval._fetch("file:///etc/passwd")
    with pytest.raises(ValueError):
        retrieval._fetch("https://public.example:8443/")


def test_html_normalization():
    parser = retrieval.Text()
    parser.feed("<p>A real fact.</p><script>ignore</script><p>Second fact.</p>")
    assert retrieval.normalize(" ".join(parser.parts)) == "A real fact. Second fact."
