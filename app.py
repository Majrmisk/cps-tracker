import streamlit as st
import altair as alt
import datetime
import duckdb
import pandas as pd
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


def get_calendar_data(con, year):
    query = f"""
        SELECT
            timestamp::DATE AS date,
            MIN(free_entries) AS min_free
        FROM occupancy_log
        WHERE YEAR(timestamp) = {year}
        GROUP BY date
        ORDER BY date
    """
    return con.sql(query).df()


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

    st.divider()
    st.subheader("Calendar")

    cal_year = st.number_input(
        "Year",
        value=datetime.date.today().year,
        step=1,
        label_visibility="collapsed"
    )

    df_cal = get_calendar_data(db, cal_year)

    if not df_cal.empty:
        df_cal["date"] = pd.to_datetime(df_cal["date"])

        dow_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        df_cal["day_name"] = df_cal["date"].dt.dayofweek.map(
            dict(enumerate(dow_names))
        )

        jan1 = pd.Timestamp(year=cal_year, month=1, day=1)
        origin = jan1 - pd.Timedelta(days=jan1.dayofweek)
        df_cal["week_num"] = ((df_cal["date"] - origin).dt.days // 7)

        month_labels = (
            df_cal.groupby(df_cal["date"].dt.strftime("%Y-%m"))
            .agg(week_num=("week_num", "min"))
            .reset_index()
            .sort_values("week_num")
        )
        month_labels.columns = ["month_key", "week_num"]
        month_labels["label"] = (
            pd.to_datetime(month_labels["month_key"]).dt.strftime("%b")
        )

        month_tick_expr = " : ".join(
            f"datum.value == {row.week_num} ? '{row.label}'"
            for row in month_labels.itertuples()
        ) + " : ''"

        cal_chart = alt.Chart(df_cal).mark_rect(cornerRadius=2).encode(
            x=alt.X("week_num:O", title=None, axis=alt.Axis(
                orient="top",
                values=month_labels["week_num"].tolist(),
                labelExpr=month_tick_expr,
                labelAngle=0,
                ticks=False,
                domain=False
            )),
            y=alt.Y("day_name:N", sort=dow_names, title=None),
            color=alt.Color(
                "min_free:Q",
                title="Lowest Free",
                scale=alt.Scale(scheme="blues", reverse=True, domain=[0, 150]),
                legend=alt.Legend(direction="horizontal", orient="bottom")
            ),
            tooltip=[
                alt.Tooltip("date:T", title="Date", format="%a %d %b"),
                alt.Tooltip("min_free:Q", title="Lowest Free")
            ]
        )

        st.altair_chart(cal_chart.properties(height=320), use_container_width=True)
    else:
        st.info("No calendar data")


if __name__ == "__main__":
    main()
