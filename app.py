"""Root Streamlit entrypoint.

The dashboard implementation now lives in `dashboard_rca/`, which keeps the
workspace easier to navigate while preserving `streamlit run app.py` as the
launch command.
"""

from dashboard_rca.ui import main


if __name__ == "__main__":
    main()