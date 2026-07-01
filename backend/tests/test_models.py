"""ContentItem media-URL sanitization (defense in depth against a hostile source)."""
from __future__ import annotations

import pytest

from app.models import ContentItem, SourceType, Stance


def _item(**kw) -> ContentItem:
    base = dict(id="x", source_type=SourceType.NEWS, url="https://ok.com")
    base.update(kw)
    return ContentItem(**base)


@pytest.mark.parametrize("bad", ["javascript:alert(1)", "data:text/html,<script>", "  JAVASCRIPT:x"])
def test_dangerous_media_urls_nulled(bad):
    it = _item(thumbnail_url=bad, embed_url=bad)
    assert it.thumbnail_url is None
    assert it.embed_url is None


def test_http_media_urls_preserved():
    it = _item(thumbnail_url="https://cdn/img.jpg", embed_url="http://yt/embed")
    assert it.thumbnail_url == "https://cdn/img.jpg"
    assert it.embed_url == "http://yt/embed"


def test_defaults_are_unclassified():
    assert _item().classification.stance is Stance.UNCLASSIFIED


def test_text_for_classification_joins_title_and_body():
    assert _item(title="T", body="B").text_for_classification() == "T\n\nB"
    assert _item(title=None, body="only body").text_for_classification() == "only body"


def test_html_entities_decoded_in_text():
    it = _item(title="Trump&#39;s &quot;plan&quot; &amp; more", body="a &lt;b&gt; c")
    assert it.title == "Trump's \"plan\" & more"
    assert it.body == "a <b> c"

