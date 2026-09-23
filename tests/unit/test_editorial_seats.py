"""Editorial seats policy must stay wired into selectors."""

from __future__ import annotations

from paper_intelligence.editorial.seats import (
    format_seats_xml,
    load_editorial_seats,
    newsletter_rubric_body,
)


def test_seats_policy_loads_tech_and_product():
    data = load_editorial_seats("v001")
    assert set(data["seats"]) >= {"TECH", "PRODUCT"}
    assert "Anchor test" in format_seats_xml("v001")
    assert "Reject for this seat" in format_seats_xml("v001")


def test_newsletter_rubric_embeds_shared_seats():
    body = newsletter_rubric_body("v001")
    assert '<seat name="TECH">' in body
    assert '<seat name="PRODUCT">' in body
    assert "I can have my team try this on our stack" in body


def test_newsletter_script_loads_shared_seats():
    from pathlib import Path
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "select_newsletter", root / "scripts" / "select_newsletter.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rubric = mod.build_user_rubric()
    assert '<seat name="TECH">' in rubric
    assert "Reject for this seat" in rubric
    assert mod.PROMPT_VERSION == "newsletter_select_v002"


def test_linkedin_script_loads_shared_seats():
    from pathlib import Path
    import importlib.util

    root = Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location(
        "select_linkedin", root / "scripts" / "select_linkedin.py"
    )
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    rubric = mod.build_user_rubric()
    assert '<seat name="TECH">' in rubric
    assert "LinkedIn" in rubric or "linkedin" in rubric.lower() or "publishing lens" in rubric
    assert mod.PROMPT_VERSION == "linkedin_select_v002"
