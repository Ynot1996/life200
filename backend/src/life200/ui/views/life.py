"""My profile: start from a CV, then edit details and each section on its own."""

import streamlit as st

from life200.domain.life import SECTIONS, LifeEntry, LifeProfile, MarketDetails
from life200.services.documents import ALL_TYPES
from life200.services.life_store import list_versions, load_profile, restore_version, save_profile
from life200.ui.common import MARKETS, session, user_id
from life200.ui.import_review import render_review, start_import


def _save(profile: LifeProfile) -> None:
    with session() as s, s.begin():
        save_profile(s, user_id(), profile)


with session() as s:
    profile = load_profile(s, user_id())

st.title("My profile")

if render_review(profile):
    st.stop()  # finish the review before anything else

# ---------- First visit: start from a CV ----------
if not profile.entries:
    st.subheader("Start with your CV")
    st.markdown(
        "Upload your current CV and we fill in your details, experience, projects, education "
        "and skills. You can edit everything afterwards. Nothing is invented: we only copy "
        "what your CV says."
    )
    upload = st.file_uploader(
        "Your CV: PDF, Word, OpenDocument, RTF, text, or a photo or scan", type=ALL_TYPES
    )
    if upload and st.button("Read my CV", type="primary"):
        start_import(upload.name, upload.getvalue(), profile)
    st.caption("No CV yet? Fill in the sections below by hand.")

if done := st.session_state.pop("import_done", None):
    st.success(done)

st.caption(
    "This is the only source of facts for your CVs and cover letters. More detail means "
    "better matches and stronger applications."
)

# ---------- Basic details ----------
with st.expander("Basic details", expanded=not profile.first_name), st.form("basics"):
    c1, c2, c3 = st.columns(3)
    first_name = c1.text_input("First name", profile.first_name)
    last_name = c2.text_input("Last name", profile.last_name)
    preferred_name = c3.text_input(
        "Preferred name", profile.preferred_name, help="Used on your CV instead of the first name."
    )
    email = st.text_input("Email", profile.email)
    headline = st.text_input(
        "Headline", profile.headline, placeholder="MSc CS graduate, Python, data"
    )
    target_roles = st.text_input("Roles I want", profile.target_roles)
    links = st.text_area("Links (one per line)", profile.links, height=80)

    st.markdown("**Phone, location and right to work**")
    st.caption(
        "The default is used everywhere. Each market can have its own, e.g. a local phone "
        "number or a different visa. Blank fields use the default."
    )
    markets = st.multiselect(
        "Markets I want to work in",
        list(MARKETS),
        default=[m for m in profile.markets if m in MARKETS],
        format_func=MARKETS.__getitem__,
    )
    shown = ["default", *[m for m in MARKETS if m in profile.markets]]
    contact: dict[str, MarketDetails] = {}
    for tab, key in zip(st.tabs(["Default", *[MARKETS[m] for m in shown[1:]]]), shown, strict=True):
        own = (
            MarketDetails(
                phone=profile.phone, location=profile.location, right_to_work=profile.right_to_work
            )
            if key == "default"
            else profile.market_details.get(key, MarketDetails())
        )
        ph = "" if key == "default" else "Same as default"
        c1, c2 = tab.columns(2)
        contact[key] = MarketDetails(
            phone=c1.text_input("Phone", own.phone, key=f"ph_{key}", placeholder=ph),
            location=c2.text_input("Location", own.location, key=f"loc_{key}", placeholder=ph),
            right_to_work=tab.text_input(
                "Right to work",
                own.right_to_work,
                key=f"rtw_{key}",
                placeholder=ph or "e.g. UK Graduate visa until 2028",
            ),
        )
    st.caption("Added a market? Save, and its tab appears.")
    if st.form_submit_button("Save details", type="primary"):
        default = contact.pop("default")
        _save(
            profile.model_copy(
                update={
                    "first_name": first_name,
                    "last_name": last_name,
                    "preferred_name": preferred_name,
                    "email": email,
                    "phone": default.phone,
                    "location": default.location,
                    "right_to_work": default.right_to_work,
                    "headline": headline,
                    "target_roles": target_roles,
                    "links": links,
                    "markets": markets,
                    "market_details": {**profile.market_details, **contact},
                }
            )
        )
        st.success("Saved.")
        st.rerun()

# ---------- One tab per section, one card per entry ----------
SINGULAR = {
    "job": "experience",
    "project": "project",
    "education": "education",
    "skill": "skill group",
    "story": "story",
    "award": "item",
}
TEXT_LABEL = {
    "job": "What you did and achieved (one bullet per line, with numbers)",
    "project": "What you built, with what, and the result",
    "education": "Grade, modules, dissertation",
    "skill": "Skills (comma separated)",
    "story": "Situation, Task, Action, Result",
    "award": "Details",
}


def _entry_form(kind: str, entry: LifeEntry, key: str) -> LifeEntry | None:
    """Fields for one entry. Returns the edited entry when Save is pressed."""
    with st.form(key, border=False):
        title = st.text_input(
            "Title", entry.title, placeholder="Role, project, degree, skill group…"
        )
        if kind not in ("skill",):
            c1, c2, c3 = st.columns([2, 1, 1])
            org = c1.text_input("Company / school / place", entry.org)
            start = c2.text_input("Start", entry.start, placeholder="2024-06")
            end = c3.text_input("End", entry.end, placeholder="Present")
        else:
            org, start, end = entry.org, entry.start, entry.end
        text = st.text_area(
            TEXT_LABEL[kind], entry.text, height=180 if kind in ("job", "project", "story") else 90
        )
        if st.form_submit_button("Save", type="primary"):
            return LifeEntry(kind=kind, title=title, org=org, start=start, end=end, text=text)
    return None


def _replace(index: int | None, kind: str, new: LifeEntry | None) -> None:
    """Swap (or delete, or append) the `index`-th entry of `kind`, keeping the rest in order."""
    out: list[LifeEntry] = []
    seen = -1
    for e in profile.entries:
        if e.kind == kind:
            seen += 1
            if seen == index:
                if new is not None:
                    out.append(new)
                continue
        out.append(e)
    if index is None and new is not None:
        out.append(new)
    _save(profile.model_copy(update={"entries": out}))
    st.rerun()


tabs = st.tabs(
    [
        f"{label} ({sum(e.kind == kind for e in profile.entries)})"
        for kind, (label, _) in SECTIONS.items()
    ]
)
for tab, (kind, (_label, hint)) in zip(tabs, SECTIONS.items(), strict=True):
    with tab:
        st.caption(hint)
        items = [e for e in profile.entries if e.kind == kind]
        for i, entry in enumerate(items):
            when = " to ".join(x for x in (entry.start, entry.end) if x)
            head = " · ".join(x for x in (entry.title or "(untitled)", entry.org, when) if x)
            with st.expander(head):
                edited = _entry_form(kind, entry, key=f"{kind}_{i}")
                if edited is not None:
                    _replace(i, kind, edited)
                if st.button("Delete", key=f"del_{kind}_{i}", icon=":material/delete:"):
                    _replace(i, kind, None)
        with st.expander(f"Add {SINGULAR[kind]}", icon=":material/add:"):
            added = _entry_form(kind, LifeEntry(kind=kind), key=f"add_{kind}")
            if added is not None and (added.title or added.text):
                _replace(None, kind, added)


# ---------- Later imports ----------
if profile.entries:
    with st.expander("Import another CV"):
        st.caption(
            "Upload a newer CV, a LinkedIn PDF, a cover letter or a certificate. You review every "
            "change before it is saved, and nothing you have is deleted."
        )
        again = st.file_uploader("Document", type=ALL_TYPES, key="again")
        if again and st.button("Read this document"):
            start_import(again.name, again.getvalue(), profile)

with st.expander("History (undo)"):
    with session() as s:
        versions = list_versions(s, user_id())
    if not versions:
        st.caption("Each time you save, the previous version is kept here.")
    for vid, saved_at, reason in versions[:10]:
        c1, c2 = st.columns([4, 1])
        c1.write(f"{saved_at:%d %b %H:%M}: before {reason}")
        if c2.button("Restore", key=f"restore_{vid}"):
            with session() as s, s.begin():
                restore_version(s, user_id(), vid)
            st.rerun()

with st.expander("What the CV writer sees"):
    options = ["", *[m for m in MARKETS if m in profile.markets]]
    chosen = st.selectbox(
        "Applying in",
        options,
        index=options.index(profile.active_market) if profile.active_market in options else 0,
        format_func=lambda m: MARKETS.get(m, "Default"),
        help="Applications use the details for the job's own market automatically.",
    )
    if chosen != profile.active_market:
        _save(profile.model_copy(update={"active_market": chosen}))
        st.rerun()
    st.text(profile.as_text() or "Nothing yet.")
