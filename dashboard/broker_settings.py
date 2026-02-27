"""
Broker credential management page.
Users add/edit/remove their encrypted broker API keys here.
"""

import streamlit as st
from sqlalchemy import select, delete

from dashboard.auth import get_db
from db.models import BrokerCredential, BrokerType
from db.encryption import encrypt_value, decrypt_value


def render_broker_settings():
    """Render the broker settings management page."""
    user_id = st.session_state.get("user_id")
    if not user_id:
        return

    st.subheader("Broker Connections")
    st.markdown("Connect your brokerage accounts. API keys are encrypted at rest.")

    # Load existing credentials
    db = get_db()
    try:
        creds = db.execute(
            select(BrokerCredential).where(BrokerCredential.user_id == user_id)
        ).scalars().all()
    finally:
        db.close()

    # Display existing connections
    if creds:
        st.markdown("#### Your Connected Brokers")
        for cred in creds:
            with st.expander(f"{cred.broker_type.value.title()} — {cred.nickname or 'Unnamed'} ({'Paper' if cred.is_paper else 'Live'})"):
                st.markdown(f"**Type:** {cred.broker_type.value.title()}")
                st.markdown(f"**Mode:** {'Paper' if cred.is_paper else 'Live'}")
                st.markdown(f"**Added:** {cred.created_at.strftime('%Y-%m-%d')}")

                # Show masked key
                try:
                    key_preview = decrypt_value(cred.encrypted_api_key)
                    st.markdown(f"**API Key:** `{key_preview[:6]}...{key_preview[-4:]}`")
                except Exception:
                    st.markdown("**API Key:** `[encrypted]`")

                if st.button(f"Remove", key=f"remove_{cred.id}"):
                    db = get_db()
                    try:
                        db.execute(delete(BrokerCredential).where(BrokerCredential.id == cred.id))
                        db.commit()
                        st.success("Broker removed.")
                        st.rerun()
                    except Exception as e:
                        db.rollback()
                        st.error(f"Failed to remove: {e}")
                    finally:
                        db.close()

    # Add new broker
    st.markdown("---")
    st.markdown("#### Add Broker Connection")

    with st.form("add_broker_form"):
        broker_type = st.selectbox("Broker", ["Alpaca", "Webull"])
        nickname = st.text_input("Nickname (optional)", placeholder="e.g. My Paper Account")
        api_key = st.text_input("API Key", type="password")
        api_secret = st.text_input("API Secret", type="password")
        is_paper = st.checkbox("Paper Trading", value=True)
        submitted = st.form_submit_button("Save Broker", use_container_width=True)

        if submitted:
            if not api_key or not api_secret:
                st.error("API Key and Secret are required.")
            else:
                db = get_db()
                try:
                    cred = BrokerCredential(
                        user_id=user_id,
                        broker_type=BrokerType.ALPACA if broker_type == "Alpaca" else BrokerType.WEBULL,
                        encrypted_api_key=encrypt_value(api_key),
                        encrypted_api_secret=encrypt_value(api_secret),
                        is_paper=is_paper,
                        nickname=nickname.strip() or None,
                    )
                    db.add(cred)
                    db.commit()
                    st.success(f"{broker_type} credentials saved (encrypted).")
                    st.rerun()
                except Exception as e:
                    db.rollback()
                    st.error(f"Failed to save: {e}")
                finally:
                    db.close()
