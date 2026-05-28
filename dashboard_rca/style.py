"""Custom Streamlit styling helpers for the dashboard."""

from __future__ import annotations

import streamlit as st


def inject_custom_css() -> None:
    """Inject institutional dashboard styling without external frameworks."""
    st.markdown(
        """
        <style>
            #MainMenu,
            footer,
            header {
                visibility: hidden;
            }

            .stApp {
                background: #f8f9fa;
            }

            [data-testid="stSidebar"] {
                padding-top: 1rem;
                padding-left: 0.75rem;
                padding-right: 0.75rem;
                background: #ffffff;
                border-right: 1px solid rgba(15, 23, 42, 0.08);
            }

            div[data-testid="stMetric"] {
                background: #ffffff;
                border: 1px solid rgba(15, 23, 42, 0.08);
                border-radius: 8px;
                box-shadow: 0 2px 8px rgba(15, 23, 42, 0.06);
                padding: 1rem 1rem 0.85rem 1rem;
            }

            div[data-testid="stMetric"] label {
                color: #4b5563;
                font-size: 0.85rem;
                font-weight: 600;
                text-transform: uppercase;
                letter-spacing: 0.03em;
            }

            div[data-testid="stMetric"] [data-testid="stMetricValue"] {
                color: #0f172a;
                font-size: 1.6rem;
                font-weight: 700;
            }

            div[data-testid="stMetricDelta"] {
                font-size: 0.85rem;
            }

            .block-container {
                padding-top: 1.5rem;
                padding-bottom: 2rem;
            }
        </style>
        """,
        unsafe_allow_html=True,
    )
