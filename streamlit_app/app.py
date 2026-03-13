from datetime import datetime, time, timezone

import streamlit as st
from api_client import api_request, build_public_short_link


def init_state() -> None:
    st.session_state.setdefault("auth_token", "")
    st.session_state.setdefault("auth_email", "")
    st.session_state.setdefault("last_created_short_url", "")
    st.session_state.setdefault("last_created_short_code", "")


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(248, 214, 120, 0.28), transparent 32%),
                radial-gradient(circle at top right, rgba(123, 176, 255, 0.20), transparent 28%),
                linear-gradient(180deg, #fffaf0 0%, #f4f2eb 100%);
        }
        .main-title {
            font-size: 3rem;
            font-weight: 800;
            line-height: 1;
            color: #1f2937;
            margin-bottom: 0.4rem;
        }
        .lead {
            color: #4b5563;
            font-size: 1.05rem;
            max-width: 48rem;
        }
        .card {
            border: 1px solid rgba(31, 41, 55, 0.08);
            background: rgba(255, 255, 255, 0.74);
            border-radius: 20px;
            padding: 1rem 1.1rem;
            box-shadow: 0 18px 50px rgba(15, 23, 42, 0.06);
        }
        .small-note {
            color: #6b7280;
            font-size: 0.9rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_header() -> None:
    st.markdown('<div class="main-title">Short Links</div>', unsafe_allow_html=True)
    st.markdown(
        '<div class="lead">Сервис для создания коротких ссылок, управления ими, и просмотра статистики и истории истекших ссылок.</div>',
        unsafe_allow_html=True,
    )


def normalize_error(payload: dict | list | str | None) -> str:
    if isinstance(payload, dict):
        detail = payload.get("detail")
        if isinstance(detail, str):
            return detail
        return str(payload)
    if isinstance(payload, list):
        return str(payload)
    if isinstance(payload, str):
        return payload
    return "Unknown error."


def auth_sidebar() -> None:
    st.sidebar.header("Account")

    if st.session_state.auth_token:
        st.sidebar.success(f"Logged in as {st.session_state.auth_email}")
        if st.sidebar.button("Log out", use_container_width=True):
            st.session_state.auth_token = ""
            st.session_state.auth_email = ""
            st.rerun()
        return

    with st.sidebar.expander("Register", expanded=True):
        with st.form("register_form", clear_on_submit=False):
            email = st.text_input("Email", key="register_email")
            password = st.text_input(
                "Password", type="password", key="register_password"
            )
            submitted = st.form_submit_button(
                "Create account", use_container_width=True
            )
        if submitted:
            status_code, payload, _ = api_request(
                "POST",
                "/auth/register",
                payload={"email": email, "password": password},
            )
            if status_code == 201:
                st.sidebar.success("Account created.")
            else:
                st.sidebar.error(normalize_error(payload))

    with st.sidebar.expander("Login", expanded=True):
        with st.form("login_form", clear_on_submit=False):
            email = st.text_input("Email ", key="login_email")
            password = st.text_input("Password ", type="password", key="login_password")
            submitted = st.form_submit_button("Log in", use_container_width=True)
        if submitted:
            status_code, payload, _ = api_request(
                "POST",
                "/auth/login",
                payload={"email": email, "password": password},
            )
            if status_code == 200 and isinstance(payload, dict):
                st.session_state.auth_token = payload["access_token"]
                st.session_state.auth_email = email
                st.rerun()
            else:
                st.sidebar.error(normalize_error(payload))


def create_link_panel() -> None:
    st.subheader("Create link")
    with st.form("create_link_form"):
        original_url = st.text_input(
            "Original URL", placeholder="https://example.com/article"
        )
        custom_alias = st.text_input("Custom alias", placeholder="optional")
        with st.expander("Optional expiration"):
            expires_enabled = st.checkbox("Set expiration")
            expires_date = st.date_input(
                "Expiration date (UTC)", value=datetime.now(timezone.utc).date()
            )
            expires_time = st.time_input(
                "Expiration time (UTC)", value=time(hour=12, minute=0)
            )
        submitted = st.form_submit_button("Shorten", use_container_width=True)

    if submitted:
        payload: dict[str, str] = {"original_url": original_url}
        if custom_alias.strip():
            payload["custom_alias"] = custom_alias.strip()
        if expires_enabled:
            expires_at = datetime.combine(
                expires_date, expires_time, tzinfo=timezone.utc
            )
            payload["expires_at"] = expires_at.replace(
                second=0, microsecond=0
            ).isoformat()

        status_code, response_payload, _ = api_request(
            "POST",
            "/links/shorten",
            payload=payload,
            token=st.session_state.auth_token or None,
        )
        if status_code == 201 and isinstance(response_payload, dict):
            short_url = build_public_short_link(response_payload["short_code"])
            st.session_state.last_created_short_url = short_url
            st.session_state.last_created_short_code = response_payload["short_code"]
        else:
            st.error(normalize_error(response_payload))

    if st.session_state.last_created_short_url:
        st.success("Short link created.")
        st.text_input(
            "Short link",
            value=st.session_state.last_created_short_url,
            disabled=True,
            key="last_created_short_url_field",
        )
        st.caption(f"Short code: {st.session_state.last_created_short_code}")
        st.link_button(
            "Open short link",
            st.session_state.last_created_short_url,
            use_container_width=True,
        )


def search_and_stats_panel() -> None:
    left_column, right_column = st.columns(2)

    with left_column:
        st.subheader("Search by original URL")
        with st.form("search_links_form"):
            original_url = st.text_input(
                "Original URL to search",
                placeholder="https://example.com/article",
            )
            submitted = st.form_submit_button("Search", use_container_width=True)
        if submitted:
            status_code, payload, _ = api_request(
                "GET",
                f"/links/search?original_url={request_quote(original_url)}",
            )
            if status_code == 200 and isinstance(payload, list):
                if payload:
                    st.dataframe(payload, use_container_width=True)
                else:
                    st.info("No active short links found for this URL.")
            else:
                st.error(normalize_error(payload))

    with right_column:
        st.subheader("Link stats")
        with st.form("stats_form"):
            short_code = st.text_input("Short code", placeholder="short_code")
            submitted = st.form_submit_button("Show stats", use_container_width=True)
        if submitted:
            status_code, payload, _ = api_request("GET", f"/links/{short_code}/stats")
            if status_code == 200 and isinstance(payload, dict):
                st.json(payload)
                st.markdown(f"[Open short link]({build_public_short_link(short_code)})")
            else:
                st.error(normalize_error(payload))


def manage_links_panel() -> None:
    st.subheader("Manage your link")
    st.caption("Update and delete require login as the owner of the link.")

    update_column, delete_column = st.columns(2)

    with update_column:
        with st.form("update_form"):
            short_code = st.text_input("Short code to update", placeholder="short_code")
            new_url = st.text_input(
                "New original URL", placeholder="https://example.com/new"
            )
            submitted = st.form_submit_button("Update link", use_container_width=True)
        if submitted:
            status_code, payload, _ = api_request(
                "PUT",
                f"/links/{short_code}",
                payload={"original_url": new_url},
                token=st.session_state.auth_token or None,
            )
            if status_code == 200 and isinstance(payload, dict):
                st.success("Link updated.")
                st.json(payload)
            else:
                st.error(normalize_error(payload))

    with delete_column:
        with st.form("delete_form"):
            short_code = st.text_input(
                "Short code to delete", placeholder="short_code", key="delete_short_code"
            )
            submitted = st.form_submit_button("Delete link", use_container_width=True)
        if submitted:
            status_code, payload, _ = api_request(
                "DELETE",
                f"/links/{short_code}",
                token=st.session_state.auth_token or None,
            )
            if status_code == 204:
                st.success("Link deleted.")
            else:
                st.error(normalize_error(payload))


def history_panel() -> None:
    st.subheader("Expired links history")
    st.markdown(
        '<div class="small-note">История автоматически удаленных по TTL ссылок.</div>',
        unsafe_allow_html=True,
    )
    st.button("Refresh history", use_container_width=True)

    status_code, payload, _ = api_request("GET", "/links/history/expired")
    if status_code == 200 and isinstance(payload, list):
        if payload:
            st.dataframe(payload, use_container_width=True)
        else:
            st.info("No expired links archived yet.")
    else:
        st.error(normalize_error(payload))


def redirect_panel() -> None:
    st.subheader("Try a short link")
    with st.form("redirect_form"):
        short_code = st.text_input(
            "Short code to open", placeholder="short_code", key="open_short_code"
        )
        submitted = st.form_submit_button("Check redirect", use_container_width=True)
    if submitted:
        status_code, payload, headers = api_request(
            "GET",
            f"/links/{short_code}",
            accept_redirects=False,
        )
        if status_code in {302, 307}:
            destination = headers.get("Location", "")
            st.success("Redirect is working.")
            if destination:
                st.markdown(f"[Open destination]({destination})")
        else:
            st.error(normalize_error(payload))


def request_quote(value: str) -> str:
    from urllib.parse import quote

    return quote(value, safe="")


def main() -> None:
    st.set_page_config(
        page_title="Short Links UI",
        page_icon=":link:",
        layout="wide",
    )
    init_state()
    inject_styles()
    render_header()
    auth_sidebar()

    create_tab, discover_tab, manage_tab, history_tab = st.tabs(
        ["Create", "Search & Stats", "Manage", "History"]
    )

    with create_tab:
        with st.container(border=True):
            create_link_panel()

    with discover_tab:
        with st.container(border=True):
            search_and_stats_panel()
            redirect_panel()

    with manage_tab:
        with st.container(border=True):
            manage_links_panel()

    with history_tab:
        with st.container(border=True):
            history_panel()


if __name__ == "__main__":
    main()
