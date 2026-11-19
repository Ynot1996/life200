import pytest

from life200.services.tagging import (
    Seniority,
    SponsorMatcher,
    SponsorStatus,
    classify_seniority,
    is_training_ad,
    name_key,
)

# ---------- Company names ----------


@pytest.mark.parametrize(
    ("raw", "key"),
    [
        ("Monzo Bank Ltd.", "monzo bank"),
        ("MONZO BANK LIMITED", "monzo bank"),
        ("Marks & Spencer PLC", "marks and spencer"),
        ("Aquapark Developments Limited T/A Prima Building Solutions Ltd", "aquapark developments"),
        ("The Hut Group", "hut"),
    ],
)
def test_name_key(raw: str, key: str) -> None:
    assert name_key(raw) == key


@pytest.fixture
def matcher() -> SponsorMatcher:
    names = [
        "Monzo Bank Limited",
        "Example Fintech Limited",
        "Deliveroo Hop Limited",
        "Amazon UK Services Ltd.",
        "Amazon Web Services EMEA SARL",
        "Advance AI Ltd",
        "PRMA Consulting Ltd",
        "Gradiant UK Ltd",
        "Thoughtworks Technologies Ltd",
    ]
    return SponsorMatcher((name_key(n), n) for n in names)


def test_exact_match_after_normalising(matcher: SponsorMatcher) -> None:
    m = matcher.match("Monzo Bank Ltd")
    assert m.status is SponsorStatus.LICENSED
    assert m.matched_name == "Monzo Bank Limited"


def test_spacing_difference_is_likely(matcher: SponsorMatcher) -> None:
    m = matcher.match("AdvanceAi")
    assert m.status is SponsorStatus.LIKELY
    assert m.matched_name == "Advance AI Ltd"


def test_short_name_matches_a_unique_longer_register_name(matcher: SponsorMatcher) -> None:
    m = matcher.match("Deliveroo")
    assert m.status is SponsorStatus.LIKELY
    assert m.matched_name == "Deliveroo Hop Limited"


def test_short_name_with_several_candidates_is_not_guessed(matcher: SponsorMatcher) -> None:
    # The register has both "Amazon UK Services" and "Amazon Web Services EMEA".
    assert matcher.match("Amazon").status is SponsorStatus.NOT_FOUND


def test_near_identical_long_name_is_likely(matcher: SponsorMatcher) -> None:
    assert matcher.match("Thoughtworks Technolgies").status is SponsorStatus.LIKELY


@pytest.mark.parametrize("company", ["PA Consulting", "Radiant", "Deliver", "Monzo Coffee"])
def test_similar_looking_names_are_not_matched(matcher: SponsorMatcher, company: str) -> None:
    assert matcher.match(company).status is SponsorStatus.NOT_FOUND


def test_different_company_is_not_matched(matcher: SponsorMatcher) -> None:
    assert matcher.match("Monzo Coffee Roasters").status is SponsorStatus.NOT_FOUND


def test_recruiter_is_flagged_as_agency(matcher: SponsorMatcher) -> None:
    assert matcher.match("Tech Recruitment Specialists Ltd").status is SponsorStatus.AGENCY


def test_missing_company_is_unknown(matcher: SponsorMatcher) -> None:
    assert matcher.match(None).status is SponsorStatus.UNKNOWN
    assert matcher.match("  ").status is SponsorStatus.UNKNOWN


def test_empty_register_finds_nothing() -> None:
    assert SponsorMatcher([]).match("Monzo").status is SponsorStatus.NOT_FOUND
    assert SponsorMatcher([]).match("Ltd").status is SponsorStatus.NOT_FOUND


@pytest.mark.parametrize(
    ("company", "title", "description", "expected"),
    [
        ("IT Career Switch", "Trainee Data Analyst", "", True),
        ("Back 2 Work", "Junior Developer", "", True),
        ("Acme Ltd", "Junior Developer", "Complete our training and get a job guarantee.", True),
        ("Acme Ltd", "Junior Developer", "Join our engineering team.", False),
        (None, "Graduate Analyst", "", False),
    ],
)
def test_is_training_ad(company: str | None, title: str, description: str, expected: bool) -> None:
    assert is_training_ad(company, title, description) is expected


# ---------- Seniority ----------


@pytest.mark.parametrize(
    ("title", "description", "expected"),
    [
        ("Junior Python Developer", "Great team.", Seniority.JUNIOR),
        ("Graduate Software Engineer", "2-year graduate programme.", Seniority.JUNIOR),
        ("Senior Data Engineer", "", Seniority.NOT_JUNIOR),
        ("Lead Developer", "", Seniority.NOT_JUNIOR),
        (
            "Junior Developer",
            "You will need 3+ years of commercial experience.",
            Seniority.NOT_JUNIOR,
        ),
        ("Junior Developer", "At least 2 years experience with Python.", Seniority.NOT_JUNIOR),
        ("Junior Developer", "0-1 years experience welcome.", Seniority.JUNIOR),
        ("Software Engineer", "Founded 10 years ago.", Seniority.UNCLEAR),
        ("Software Engineer", "Build APIs.", Seniority.UNCLEAR),
    ],
)
def test_classify_seniority(title: str, description: str, expected: Seniority) -> None:
    level, reason = classify_seniority(title, description)
    assert level is expected
    assert reason
