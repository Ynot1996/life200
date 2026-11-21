"""Import review: verification against the document, matching, merging, undo, file types."""

import io
import zipfile

import pytest
from docx import Document
from sqlalchemy.orm import Session

from life200.domain.life import LifeEntry, LifeProfile
from life200.services import auth
from life200.services.documents import UnsupportedDocumentError, read_document
from life200.services.life_store import list_versions, load_profile, restore_version, save_profile
from life200.services.profile_review import apply_plan, combine_text, plan_import, unverified

SOURCE = """Jordan Lee
Software Engineering Intern, Brightfield Analytics (Jun 2025 - Sep 2025)
- Built a FastAPI service that cut report generation time by 40%
- Wrote pytest suites raising coverage from 55% to 90%
MSc Computer Science, University of Birmingham"""

INTERN = LifeEntry(
    kind="job",
    title="Software Engineering Intern",
    org="Brightfield Analytics",
    start="Jun 2025",
    end="Sep 2025",
    text="- Built a FastAPI service that cut report generation time by 40%",
)


# ---------- checking against the document ----------


def test_true_entry_has_no_problems() -> None:
    assert unverified(INTERN, SOURCE) == []


def test_invented_number_and_line_are_flagged() -> None:
    wrong = INTERN.model_copy(
        update={"text": "- Cut report time by 75%\n- Led a team of twelve engineers worldwide"}
    )
    problems = unverified(wrong, SOURCE)
    assert any('"75%"' in p for p in problems)
    assert any("twelve engineers" in p for p in problems)


def test_wrong_company_is_flagged() -> None:
    assert unverified(INTERN.model_copy(update={"org": "Google"}), SOURCE)


# ---------- planning an import ----------


def test_first_import_is_all_new_and_fills_empty_basics() -> None:
    imported = LifeProfile(full_name="Jordan Lee", entries=[INTERN])
    plan = plan_import(LifeProfile(), imported, SOURCE, "cv.pdf")
    assert [n.add for n in plan.new] == [True]
    assert plan.basics[0].use_theirs is True  # empty field: fill it


def test_flagged_items_start_unticked() -> None:
    bad = INTERN.model_copy(update={"text": "- Raised revenue by 300%"})
    plan = plan_import(LifeProfile(), LifeProfile(entries=[bad]), SOURCE, "cv.pdf")
    assert plan.new[0].add is False
    assert plan.problems == 1


def test_my_basics_are_kept_by_default() -> None:
    current = LifeProfile(full_name="Jordan L.")
    plan = plan_import(current, LifeProfile(full_name="Jordan Lee"), SOURCE, "cv.pdf")
    assert plan.basics[0].use_theirs is False


def test_same_entry_with_more_detail_is_changed_and_combined() -> None:
    mine = INTERN.model_copy(update={"text": INTERN.text + "\n- My own note"})
    theirs = INTERN.model_copy(
        update={"text": INTERN.text + "\n- Wrote pytest suites raising coverage from 55% to 90%"}
    )
    current = LifeProfile(entries=[mine])
    plan = plan_import(current, LifeProfile(entries=[theirs]), SOURCE, "cv.pdf")
    assert plan.new == []
    assert len(plan.changed) == 1
    assert plan.changed[0].choice == "combine"

    result = apply_plan(current, plan, LifeEntry(kind="cv", title="cv.pdf", text=SOURCE))
    job = result.entries[0]
    assert "My own note" in job.text  # nothing of mine is lost
    assert "pytest" in job.text  # the CV's new line is added
    assert result.entries[-1].kind == "cv"  # the document is kept for reference


def test_identical_entry_counts_as_already_there() -> None:
    current = LifeProfile(entries=[INTERN])
    plan = plan_import(current, LifeProfile(entries=[INTERN]), SOURCE, "cv.pdf")
    assert (plan.unchanged, plan.new, plan.changed) == (1, [], [])


def test_keep_mine_and_unticked_new_change_nothing() -> None:
    current = LifeProfile(entries=[INTERN])
    other = LifeEntry(
        kind="education", title="MSc Computer Science", org="University of Birmingham"
    )
    theirs = INTERN.model_copy(
        update={"text": INTERN.text + "\n- Wrote pytest suites raising coverage from 55% to 90%"}
    )
    plan = plan_import(current, LifeProfile(entries=[theirs, other]), SOURCE, "cv.pdf")
    plan.changed[0].choice = "keep"
    plan.new[0].add = False
    result = apply_plan(current, plan, LifeEntry(kind="cv", title="cv.pdf", text=SOURCE))
    assert result.entries[0] == INTERN
    assert [e.kind for e in result.entries] == ["job", "cv"]


def test_combine_text_skips_near_duplicates() -> None:
    assert combine_text("- Built X", "- built x\n- New thing") == "- Built X\n- New thing"


# ---------- undo ----------


def test_every_save_can_be_undone(db_session: Session) -> None:
    user = auth.create_user(db_session, "undo@example.com", "long enough pw")
    save_profile(db_session, user.id, LifeProfile(full_name="First"))
    save_profile(db_session, user.id, LifeProfile(full_name="Second"), reason="import cv.pdf")
    save_profile(db_session, user.id, LifeProfile(full_name="Second"))  # no change: no version
    versions = list_versions(db_session, user.id)
    assert [reason for _, _, reason in versions] == ["import cv.pdf"]
    restore_version(db_session, user.id, versions[0][0])
    assert load_profile(db_session, user.id).full_name == "First"
    with pytest.raises(ValueError, match="no such version"):
        restore_version(db_session, user.id + 999, versions[0][0])


# ---------- document types ----------


def test_word_tables_are_read() -> None:
    doc = Document()
    doc.add_paragraph("Jordan Lee")
    table = doc.add_table(rows=1, cols=2)
    table.rows[0].cells[0].text = "Skills"
    table.rows[0].cells[1].text = "Python, SQL"
    out = io.BytesIO()
    doc.save(out)
    text = read_document("cv.docx", out.getvalue()).text
    assert "Jordan Lee" in text
    assert "Skills | Python, SQL" in text


def test_other_formats() -> None:
    odt = io.BytesIO()
    with zipfile.ZipFile(odt, "w") as z:
        z.writestr(
            "content.xml",
            "<office><text:p>Hello</text:p><text:p>World &amp; more</text:p></office>",
        )
    assert read_document("cv.odt", odt.getvalue()).text.split() == ["Hello", "World", "&", "more"]
    assert "Hello" in read_document("cv.rtf", rb"{\rtf1\ansi Hello\par}").text
    assert read_document("cv.html", b"<p>Hi</p>").text.strip() == "Hi"
    photo = read_document("cv.JPG", b"\xff\xd8")
    assert photo.needs_ai_reading
    assert photo.mime == "image/jpeg"
    with pytest.raises(UnsupportedDocumentError, match=r"\.exe"):
        read_document("cv.exe", b"")
