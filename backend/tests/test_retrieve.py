"""Retriever dedup/interleave/cap and the http(s)-only URL guard."""
from __future__ import annotations

from app.models import ContentItem, SourceType
from app.pipeline.retrieve import _dedup, _round_robin, _norm_title


def _item(url: str, title: str, src: SourceType = SourceType.NEWS) -> ContentItem:
    return ContentItem(id=url, source_type=src, title=title, url=url)


def test_exact_url_dedup():
    out = _dedup([_item("https://a.com", "One"), _item("https://a.com", "One again")])
    assert len(out) == 1


def test_near_identical_titles_collapse():
    items = [
        _item("https://x.com/1", "Tv9 Marathi News Top Headline Today 3 PM Maharashtra"),
        _item("https://x.com/2", "Tv9 Marathi News Top Headline Today 2 PM Maharashtra"),
    ]
    assert len(_dedup(items)) == 1


def test_distinct_titles_kept():
    items = [
        _item("https://x.com/1", "Supreme Court rules on birthright citizenship"),
        _item("https://x.com/2", "Electric vehicle sales climb in Europe"),
    ]
    assert len(_dedup(items)) == 2


def test_non_http_url_dropped():
    items = [
        _item("javascript:alert(1)", "evil"),
        _item("https://ok.com", "good"),
        _item("ftp://x.com/f", "ftp"),
    ]
    out = _dedup(items)
    assert [it.url for it in out] == ["https://ok.com"]


def test_round_robin_interleaves_for_diversity():
    a = [_item(f"https://a/{i}", f"a{i}") for i in range(3)]
    b = [_item(f"https://b/{i}", f"b{i}") for i in range(2)]
    urls = [it.url for it in _round_robin([a, b])]
    # first two come from different lists → the mix isn't front-loaded by one source
    assert urls[0].startswith("https://a") and urls[1].startswith("https://b")


def test_norm_title_strips_punctuation_and_case():
    assert _norm_title("Hello, WORLD! | 3 PM") == "hello world  3 pm"
    assert _norm_title(None) == ""
