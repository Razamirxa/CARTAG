from fastapi.testclient import TestClient

from cartag.config import get_settings
from cartag.main import create_app


def site_client(tmp_path) -> tuple[TestClient, str]:
    """A built website as the build leaves it: Home and Shop pre-rendered, an empty shell for the rest."""
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets" / "app.js").write_text("console.log(1)", encoding="utf-8")
    (tmp_path / "index.html").write_text(
        '<link rel="canonical" href="__PUBLIC_BASE_URL__/"><div id="root">HOME</div>', encoding="utf-8"
    )
    (tmp_path / "shop").mkdir()
    (tmp_path / "shop" / "index.html").write_text('<div id="root">SHOP</div>', encoding="utf-8")
    (tmp_path / "app.html").write_text('<div id="root"></div>', encoding="utf-8")
    settings = get_settings().model_copy(update={"web_dist_dir": str(tmp_path)})
    return TestClient(create_app(settings=settings)), settings.public_base_url.rstrip("/")


def test_public_pages_come_pre_rendered_with_the_real_address(tmp_path):
    client, base = site_client(tmp_path)

    home = client.get("/")
    assert "HOME" in home.text and f'href="{base}/"' in home.text and "__PUBLIC_BASE_URL__" not in home.text
    assert "SHOP" in client.get("/shop").text
    assert "SHOP" in client.get("/shop/").text


def test_every_other_page_gets_the_empty_shell(tmp_path):
    client, _ = site_client(tmp_path)

    for path in ("/account", "/login", "/admin/batches", "/no-such-page", "/../.env"):
        res = client.get(path)
        assert res.status_code == 200 and res.text == '<div id="root"></div>', path
    assert client.get("/assets/app.js").text == "console.log(1)"
    assert client.get("/api/nothing").status_code == 404


def test_robots_and_sitemap_list_only_the_public_pages(tmp_path):
    client, base = site_client(tmp_path)

    robots = client.get("/robots.txt").text
    assert "Disallow: /admin" in robots and "Disallow: /account" in robots and "Disallow: /t/" in robots
    assert f"Sitemap: {base}/sitemap.xml" in robots

    sitemap = client.get("/sitemap.xml")
    assert sitemap.headers["content-type"].startswith("application/xml")
    assert f"<loc>{base}/</loc>" in sitemap.text and f"<loc>{base}/shop</loc>" in sitemap.text
    assert "account" not in sitemap.text
