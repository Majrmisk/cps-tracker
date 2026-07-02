import streamlit as st
import altair as alt
import datetime
import duckdb
from zoneinfo import ZoneInfo

st.set_page_config(
    page_title="CPS Tracker",
    layout="centered"
)


@st.cache_resource
def get_connection():
    return duckdb.connect(
        f"md:cps_tracker?motherduck_token={st.secrets['MOTHERDUCK_TOKEN']}"
    )


def get_latest_log(con):
    return con.sql(
        "SELECT * FROM occupancy_log ORDER BY timestamp DESC"
    ).fetchone()


def get_history(con, selected_date):
    query = f"""
        SELECT timestamp, free_entries
        FROM occupancy_log
        WHERE timestamp::DATE = '{selected_date}'
        ORDER BY timestamp
    """
    df = con.sql(query).df()

    if not df.empty:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        df["timestamp"] = df["timestamp"].dt.tz_convert("Europe/Berlin")

    return df


def get_week_history(con, any_date):
    week_start = any_date - datetime.timedelta(days=any_date.weekday())
    week_end = week_start + datetime.timedelta(days=6)
    query = f"""
        SELECT timestamp, free_entries
        FROM occupancy_log
        WHERE timestamp::DATE BETWEEN '{week_start}' AND '{week_end}'
        ORDER BY timestamp
    """
    df = con.sql(query).df()

    if not df.empty:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
        df["timestamp"] = df["timestamp"].dt.tz_convert("Europe/Berlin")

    return df, week_start, week_end


def main():
    st.title("CPS Tracker")

    db = get_connection()
    if not db:
        st.error("Could not connect to database.")
        return

    latest = get_latest_log(db)
    if latest:
        utc = latest[0].replace(tzinfo=datetime.timezone.utc)
        cet = utc.astimezone(ZoneInfo("Europe/Berlin"))

        st.markdown(
            f"""
                <span style='font-size: 80px; font-weight: bold;'>
                    {latest[1]}
                </span>

                <span style='font-size: 20px; margin-left: 5px;'>
                    free entries
                </span>
            """,
            unsafe_allow_html=True
        )
        st.progress(latest[1] / 150)
        st.caption(f"Last updated: {cet.strftime('%d/%m %H:%M')}")
    else:
        st.warning("No data")

    st.divider()
    st.subheader("History")

    view = st.radio("View", ["Day", "Week"], horizontal=True, label_visibility="collapsed")

    selected_date = st.date_input(
        "",
        datetime.date.today(),
        label_visibility="collapsed"
    )

    if view == "Day":
        df = get_history(db, selected_date)
        x_title = "Time"
        x_format = "%H:%M"
    else:
        df, week_start, week_end = get_week_history(db, selected_date)
        x_title = "Date & Time"
        x_format = "%a %H:%M"
        st.caption(f"Week of {week_start.strftime('%d %b')} – {week_end.strftime('%d %b %Y')}")

    if not df.empty:
        chart = alt.Chart(df).mark_area(
            color="#2e2ef5",
            opacity=0.5,
            line=True
        ).encode(
            x=alt.X("timestamp", title=x_title),
            y=alt.Y(
                "free_entries",
                title="Free Entries",
                scale=alt.Scale(domain=[0, 150])
            ),
            tooltip=[
                alt.Tooltip("timestamp", title=x_title, format=x_format),
                alt.Tooltip("free_entries", title="Free Entries")
            ]
        )
        st.altair_chart(chart)
    else:
        st.info("No data")


if __name__ == "__main__":
    main()
