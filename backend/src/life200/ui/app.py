"""Life200 (Streamlit). Log in, then: jobs, my life, matches and apply, tracker.

Run from the project folder:  make app
Create your login first:      make admin EMAIL=you@example.com
"""

import streamlit as st

from life200.services.auth import authenticate
from life200.ui.common import session

st.set_page_config(page_title="Life200", page_icon="🔎", layout="wide")


def login() -> None:
    st.title("Life200")
    st.caption(
        "Junior and intern jobs in the UK, Singapore, Japan and Taiwan, with tailored applications."
    )
    with st.form("login"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        if st.form_submit_button("Log in", type="primary"):
            with session() as s:
                user = authenticate(s, email, password)
            if user is None:
                st.error("Wrong email or password.")
            else:
                st.session_state["user_id"] = user.id
                st.session_state["email"] = user.email
                st.rerun()
    st.caption("No account? Run `make admin EMAIL=you@example.com` in the project folder.")


if "user_id" not in st.session_state:
    st.navigation([st.Page(login, title="Log in")]).run()
    st.stop()

with st.sidebar:
    st.caption(f"Logged in as {st.session_state['email']}")
    if st.button("Log out"):
        st.session_state.clear()
        st.rerun()

st.navigation(
    [
        st.Page("views/apply.py", title="Matches and apply", icon="🎯", default=True),
        st.Page("views/jobs.py", title="All junior jobs", icon="📋"),
        st.Page("views/life.py", title="My life", icon="📝"),
        st.Page("views/tracker.py", title="My applications", icon="📌"),
    ]
).run()
