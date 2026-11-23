"""Life200 (Streamlit).

Anyone can search jobs. Signing in (Google, or a password for admins) adds: your profile,
matched jobs with tailored CVs and cover letters, and an application tracker.

Run from the project folder:  make app
Google sign-in needs backend/.streamlit/secrets.toml (see README).
"""

import streamlit as st

from life200.services.auth import authenticate, sign_in_with_google
from life200.ui.common import google_configured, session

st.set_page_config(
    page_title="Life200 — junior jobs for international applicants", page_icon="🔎", layout="wide"
)


def _sync_google_user() -> None:
    """After Google sign-in, find or create the account and remember its id."""
    if "user_id" in st.session_state or not google_configured() or not st.user.is_logged_in:
        return
    email = str(st.user.get("email") or "")
    if not email or st.user.get("email_verified") is False:
        st.error("Google did not share a verified email, so we cannot sign you in.")
        return
    with session() as s, s.begin():
        user = sign_in_with_google(s, email, st.user.get("name"))  # type: ignore[arg-type]
        st.session_state["user_id"], st.session_state["email"] = user.id, user.email
        st.session_state["is_admin"] = user.is_admin


def sign_in_page() -> None:
    st.title("Sign in")
    st.markdown(
        "Free account: save your profile once, get jobs matched to you, and a tailored CV and "
        "cover letter for each one in a minute. Track every application in one place."
    )
    if google_configured():
        if st.button("Continue with Google", type="primary", icon=":material/login:"):
            st.login("google")
    else:
        st.info("Google sign-in is not set up yet (see README: Google sign-in).")
    with st.expander("Admin sign-in with email and password"), st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Sign in"):
            with session() as s, s.begin():
                user = authenticate(s, email, password)
                if user is not None:
                    st.session_state["user_id"], st.session_state["email"] = user.id, user.email
            if user is None:
                st.error("Wrong email or password.")
            else:
                st.rerun()


def sign_out() -> None:
    st.session_state.clear()
    if google_configured() and st.user.is_logged_in:
        st.logout()
    st.rerun()


_sync_google_user()
signed_in = "user_id" in st.session_state

find_jobs = st.Page(
    "views/jobs.py", title="Find jobs", icon=":material/travel_explore:", default=not signed_in
)
if signed_in:
    pages = [
        st.Page("views/apply.py", title="Matches and apply", icon=":material/bolt:", default=True),
        find_jobs,
        st.Page("views/life.py", title="My profile", icon=":material/badge:"),
        st.Page("views/tracker.py", title="My applications", icon=":material/view_kanban:"),
        st.Page("views/interview.py", title="Interview prep", icon=":material/record_voice_over:"),
    ]
    if st.session_state.get("is_admin"):
        pages.append(
            st.Page("views/costs.py", title="AI costs (admin)", icon=":material/payments:")
        )
else:
    pages = [find_jobs, st.Page(sign_in_page, title="Sign in", icon=":material/login:")]

with st.sidebar:
    if signed_in:
        st.caption(f"Signed in as {st.session_state['email']}")
        if st.button("Sign out"):
            sign_out()
    else:
        st.caption("Searching is free. Sign in to save your profile and apply faster.")

st.navigation(pages).run()
