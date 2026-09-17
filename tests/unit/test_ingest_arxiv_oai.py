"""Unit tests for OAI ingest parsing (fixture XML; no network, no DB)."""

from __future__ import annotations

import xml.etree.ElementTree as ET

from paper_intelligence.ingest import arxiv_oai as ingest
from paper_intelligence.ingest.repository import normalize_url, parse_iso_datetime


OAI_OPEN = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<OAI-PMH xmlns="http://www.openarchives.org/OAI/2.0/">\n'
    "  <ListRecords>\n"
)
OAI_CLOSE = "  </ListRecords>\n</OAI-PMH>\n"

RECORD_CS = """
<record>
  <header>
    <identifier>oai:arXiv.org:2601.00099</identifier>
    <datestamp>2026-01-06</datestamp>
    <setSpec>cs:cs:AI</setSpec>
  </header>
  <metadata>
    <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
      <id>2601.00099</id>
      <created>2026-01-05</created>
      <updated>2026-01-06</updated>
      <authors>
        <author>
          <keyname>Smith</keyname>
          <forenames>Ada</forenames>
          <affiliation>Amazon</affiliation>
        </author>
        <author>
          <keyname>Jones</keyname>
          <forenames>Bob</forenames>
          <affiliation>Stanford University</affiliation>
          <affiliation>Google DeepMind</affiliation>
        </author>
      </authors>
      <title>An Example AI Paper</title>
      <categories>cs.AI cs.LG</categories>
      <abstract>  Example   abstract. </abstract>
    </arXiv>
  </metadata>
</record>
"""

RECORD_DELETED = """
<record>
  <header status="deleted">
    <identifier>oai:arXiv.org:1400.0002</identifier>
    <datestamp>2026-01-04</datestamp>
  </header>
</record>
"""

RECORD_MATH = """
<record>
  <header>
    <identifier>oai:arXiv.org:1300.0001</identifier>
    <datestamp>2026-01-03</datestamp>
  </header>
  <metadata>
    <arXiv xmlns="http://arxiv.org/OAI/arXiv/">
      <id>1300.0001</id>
      <created>2013-01-01</created>
      <title>Pure Math</title>
      <categories>math.NA</categories>
      <abstract>No cs.</abstract>
      <authors><author><keyname>Doe</keyname><forenames>Jane</forenames></author></authors>
    </arXiv>
  </metadata>
</record>
"""


def _first_record(xml_body: str):
    root = ET.fromstring(OAI_OPEN + xml_body + OAI_CLOSE)
    return root.find("oai:ListRecords/oai:record", ingest.OAI_NS)


def test_parse_record_keeps_created_for_published_at():
    rec = ingest.parse_record(_first_record(RECORD_CS))
    assert rec["deleted"] is False
    assert rec["arxiv_id"] == "2601.00099"
    assert rec["authors"] == ["Ada Smith", "Bob Jones"]
    assert rec["authors_structured"][0]["affiliation"] == "Amazon"
    assert rec["authors_structured"][1]["affiliations"] == [
        "Stanford University",
        "Google DeepMind",
    ]
    assert rec["categories"] == ["cs.AI", "cs.LG"]
    item = ingest.record_to_item(rec)
    assert item["published_at"] == parse_iso_datetime("2026-01-05")
    assert item["canonical_url"] == "https://arxiv.org/abs/2601.00099"
    assert item["source"] == "arxiv_oai"
    assert item["raw_metadata"]["authors_structured"][0]["name"] == "Ada Smith"
    from paper_intelligence.ingest.repository import affiliation_lines_from_structured

    lines = affiliation_lines_from_structured(rec["authors_structured"])
    assert lines == [
        "Affiliation: Amazon",
        "Affiliation: Stanford University",
        "Affiliation: Google DeepMind",
    ]


def test_parse_deleted_and_category_filter():
    deleted = ingest.parse_record(_first_record(RECORD_DELETED))
    assert deleted["deleted"] is True
    math = ingest.parse_record(_first_record(RECORD_MATH))
    assert ingest.category_matches(math["categories"]) is False
    assert ingest.category_matches(["cs.AI"]) is True


def test_normalize_url_strips_version():
    assert normalize_url("https://arxiv.org/abs/2601.00099v2") == "https://arxiv.org/abs/2601.00099"
