"""Unit tests for arXiv HTML affiliation parsing (no network)."""

from __future__ import annotations

from paper_intelligence.external.arxiv_html import _parse


FOOTNOTE_HTML = """
<html><body>
<div class="ltx_authors">
  <span class="ltx_personname">Honghao Lin</span>
  <span class="ltx_personname">David P. Woodruff</span>
</div>
<span class="ltx_note ltx_role_footnotetext">
  <sup class="ltx_note_mark">0</sup>
  <span class="ltx_note_type">footnotetext: </span>
  Co-first authors. Email:
  <span class="ltx_font_typewriter">honghaol@google.com</span>,
  <span class="ltx_font_typewriter">woodruffd@google.com</span>.
</span>
<span class="ltx_note ltx_role_footnotetext">
  <sup class="ltx_note_mark">1</sup>
  <span class="ltx_note_type">footnotetext: </span>
  Google Research.
</span>
<span class="ltx_note ltx_role_footnotetext">
  <sup class="ltx_note_mark">2</sup>
  <span class="ltx_note_type">footnotetext: </span>
  Carnegie Mellon University.
</span>
</body></html>
"""


def test_parse_extracts_org_footnotes_and_emails():
    emails, affiliations = _parse(FOOTNOTE_HTML)
    assert "honghaol@google.com" in emails
    assert "woodruffd@google.com" in emails
    assert "Google Research" in affiliations
    assert "Carnegie Mellon University" in affiliations
    # Meta authorship footnote must not become an org candidate.
    assert not any("co-first" in a.casefold() for a in affiliations)


def test_parse_still_reads_inline_affiliation_nodes():
    html = """
    <span class="ltx_role_affiliation">Stanford University</span>
    <span class="ltx_role_affiliation">alice@stanford.edu</span>
    """
    emails, affiliations = _parse(html)
    assert "alice@stanford.edu" in emails
    assert "Stanford University" in affiliations
    assert not any("@" in a for a in affiliations)
