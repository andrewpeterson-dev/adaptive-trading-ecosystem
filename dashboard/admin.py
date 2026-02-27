"""
Admin dashboard — only visible to users with is_admin=True.
Shows platform stats, user management, and system overview.
"""

import streamlit as st
from sqlalchemy import select, func, update
from datetime import datetime, timedelta

from dashboard.auth import get_db
from db.models import User, BrokerCredential


def render_admin_dashboard():
    """Render the admin panel. Only call if user is admin."""
    if not st.session_state.get("is_admin"):
        st.error("Access denied.")
        return

    st.subheader("Admin Dashboard")

    db = get_db()
    try:
        # Platform stats
        total_users = db.execute(select(func.count(User.id))).scalar()
        active_users = db.execute(select(func.count(User.id)).where(User.is_active == True)).scalar()
        verified_users = db.execute(select(func.count(User.id)).where(User.email_verified == True)).scalar()

        week_ago = datetime.utcnow() - timedelta(days=7)
        month_ago = datetime.utcnow() - timedelta(days=30)
        new_7d = db.execute(select(func.count(User.id)).where(User.created_at >= week_ago)).scalar()
        new_30d = db.execute(select(func.count(User.id)).where(User.created_at >= month_ago)).scalar()
        total_broker_connections = db.execute(select(func.count(BrokerCredential.id))).scalar()

        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Total Users", total_users)
        col2.metric("Active", active_users)
        col3.metric("Verified", verified_users)
        col4.metric("Broker Connections", total_broker_connections)

        col5, col6 = st.columns(2)
        col5.metric("New (7d)", new_7d)
        col6.metric("New (30d)", new_30d)

        # User list
        st.markdown("---")
        st.markdown("#### User Management")

        users = db.execute(
            select(User).order_by(User.created_at.desc())
        ).scalars().all()

        for user in users:
            with st.expander(f"{user.display_name} ({user.email})"):
                col_a, col_b, col_c = st.columns(3)
                col_a.markdown(f"**ID:** {user.id}")
                col_b.markdown(f"**Joined:** {user.created_at.strftime('%Y-%m-%d')}")
                col_c.markdown(f"**Verified:** {'Yes' if user.email_verified else 'No'}")

                # Toggle active
                new_active = st.checkbox(
                    "Account Active",
                    value=user.is_active,
                    key=f"active_{user.id}",
                )
                if new_active != user.is_active:
                    db.execute(
                        update(User).where(User.id == user.id).values(is_active=new_active)
                    )
                    db.commit()
                    st.success(f"{'Enabled' if new_active else 'Disabled'} {user.email}")
                    st.rerun()
    finally:
        db.close()
