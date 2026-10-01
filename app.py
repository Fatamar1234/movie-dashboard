"""
Movie Ratings Explorer
 
Question 1 — Genre Breakdown:
    What's the distribution of genres among the movies that were rated?
Question 2 — Genre Satisfaction:
    Which genres have the highest average rating? Which have the lowest?
 
Run with:  streamlit run app.py
Expects movie_ratings.csv in the same folder as this file.
"""
 
from pathlib import Path
 
import altair as alt
import pandas as pd
import streamlit as st
 
DATA_PATH = Path(__file__).parent / "movie_ratings.csv"
 
st.set_page_config(page_title="Movie Ratings Explorer", layout="wide")
 
 
@st.cache_data
def load_data(path: Path) -> pd.DataFrame:
    return pd.read_csv(path)
 
 
def genre_distribution(df: pd.DataFrame) -> pd.DataFrame:
    """Q1: count genres across distinct movies.
 
    Each movie is counted once (not once per rating), and a movie with
    several pipe-separated genres counts toward each of them.
    """
    movies = df.drop_duplicates("movie_id")[["movie_id", "genres"]]
    genres = movies["genres"].str.split("|").explode()
    counts = genres.value_counts().rename_axis("genre").reset_index(name="movies")
    counts["share_of_movies"] = counts["movies"] / len(movies)
    return counts
 
 
def genre_ratings(df: pd.DataFrame) -> pd.DataFrame:
    """Q2: average rating per genre, using every individual rating.
 
    A rating of a multi-genre movie counts toward each of its genres.
    """
    exploded = df.assign(genre=df["genres"].str.split("|")).explode("genre")
    return (
        exploded.groupby("genre")["rating"]
        .agg(avg_rating="mean", num_ratings="count")
        .reset_index()
    )
 
 
# ---------- Load ----------
if not DATA_PATH.exists():
    st.error(
        f"Couldn't find {DATA_PATH.name}. Put it in the same folder as app.py and rerun."
    )
    st.stop()
 
df = load_data(DATA_PATH)
n_movies = df["movie_id"].nunique()
overall_avg = df["rating"].mean()
 
# One table with both answers per genre. 'unknown' is a placeholder tag
# (2 movies, 10 ratings), so it's left out.
genres = genre_distribution(df).merge(genre_ratings(df), on="genre")
genres = genres[genres["genre"] != "unknown"]
genres["vs_overall"] = genres["avg_rating"].apply(
    lambda r: "Above overall average" if r >= overall_avg else "Below overall average"
)
 
by_count = genres.sort_values("movies", ascending=False)
by_rating = genres.sort_values("avg_rating", ascending=False)
 
st.title("Movie Ratings Explorer")
 
tooltip = [
    alt.Tooltip("genre:N", title="Genre"),
    alt.Tooltip("movies:Q", title="Movies"),
    alt.Tooltip("share_of_movies:Q", title="Share of movies", format=".1%"),
    alt.Tooltip("avg_rating:Q", title="Average rating", format=".2f"),
    alt.Tooltip("num_ratings:Q", title="Ratings", format=","),
]
 
# ---------- Question 1 — Genre Breakdown ----------
st.header("Question 1 — Genre Breakdown")
st.write("What's the distribution of genres among the movies that were rated?")
 
q1a, q1b, q1c = st.columns(3)
q1a.metric("Rated movies", f"{n_movies:,}")
q1b.metric("Most common genre", by_count.iloc[0]["genre"], f"{by_count.iloc[0]['movies']} movies")
q1c.metric("Least common genre", by_count.iloc[-1]["genre"], f"{by_count.iloc[-1]['movies']} movies", delta_color="off")
 
count_chart = (
    alt.Chart(genres)
    .mark_bar(color="#4c78a8")
    .encode(
        x=alt.X("movies:Q", title="Number of movies"),
        y=alt.Y("genre:N", sort="-x", title=None),
        tooltip=tooltip,
    )
    .properties(height=500)
)
st.altair_chart(count_chart, use_container_width=True)
st.caption(
    f"Each of the {n_movies:,} distinct movies is counted once. Movies with several "
    "genres count toward each one, so the bars sum to more than the number of movies. "
    "The 'unknown' genre (2 movies) is excluded."
)
 
# ---------- Question 2 — Genre Satisfaction ----------
st.divider()
st.header("Question 2 — Genre Satisfaction")
st.write("Which genres have the highest average rating? Which have the lowest?")
 
q2a, q2b, q2c = st.columns(3)
q2a.metric("Highest rated genre", by_rating.iloc[0]["genre"], f"{by_rating.iloc[0]['avg_rating']:.2f} avg")
q2b.metric("Lowest rated genre", by_rating.iloc[-1]["genre"], f"{by_rating.iloc[-1]['avg_rating']:.2f} avg", delta_color="inverse")
q2c.metric("Overall average rating", f"{overall_avg:.2f}")
 
rating_bars = (
    alt.Chart(genres)
    .mark_bar()
    .encode(
        x=alt.X("avg_rating:Q", title="Average rating (1–5)", scale=alt.Scale(domain=[1, 5])),
        y=alt.Y("genre:N", sort="-x", title=None),
        color=alt.Color(
            "vs_overall:N",
            title=None,
            scale=alt.Scale(
                domain=["Above overall average", "Below overall average"],
                range=["#2b8a6e", "#c9673a"],
            ),
            legend=alt.Legend(orient="top"),
        ),
        tooltip=tooltip,
    )
)
overall_line = (
    alt.Chart(pd.DataFrame({"overall": [overall_avg]}))
    .mark_rule(strokeDash=[4, 4], color="gray")
    .encode(x="overall:Q")
)
st.altair_chart(
    (rating_bars + overall_line).properties(height=500),
    use_container_width=True
)
st.caption(
    "Averages use all individual ratings; a rating for a multi-genre movie counts toward "
    f"each of its genres. The dashed line is the overall average ({overall_avg:.2f}). "
    "The 'unknown' genre (10 ratings) is excluded."
)
 
with st.expander("See the numbers for Questions 1 and 2"):
    st.dataframe(
        by_count[["genre", "movies", "share_of_movies", "avg_rating", "num_ratings"]]
        .style.format(
            {"share_of_movies": "{:.1%}", "avg_rating": "{:.2f}", "num_ratings": "{:,}"}
        ),
        hide_index=True,
        width="stretch",
    )
 # new line 


st.divider()
st.header("Ratings Over Time")
st.write("How has the mean rating changed across movie release years?")
 
 
def ratings_by_release_year(df: pd.DataFrame) -> pd.DataFrame:
    """Mean rating for each movie release year, using every individual rating.
 
    Rows without a release year are dropped. A 5-year centered rolling
    average (weighted by number of ratings) smooths out noisy years.
    """
    by_year = (
        df.dropna(subset=["year"])
        .groupby("year")["rating"]
        .agg(avg_rating="mean", num_ratings="count", rating_sum="sum")
        .reset_index()
    )
    by_year["year"] = by_year["year"].astype(int)
    roll_sum = by_year["rating_sum"].rolling(5, center=True, min_periods=1).sum()
    roll_n = by_year["num_ratings"].rolling(5, center=True, min_periods=1).sum()
    by_year["rolling_avg"] = roll_sum / roll_n
    return by_year.drop(columns="rating_sum")
 
 
by_year = ratings_by_release_year(df)
early = df[df["year"] < 1960]["rating"].mean()
late = df[df["year"] >= 1990]["rating"].mean()
 
q3a, q3b, q3c = st.columns(3)
q3a.metric("Release years covered", f"{by_year['year'].min()}–{by_year['year'].max()}")
q3b.metric("Avg rating, movies before 1960", f"{early:.2f}")
q3c.metric("Avg rating, movies from 1990 on", f"{late:.2f}", f"{late - early:+.2f} vs. pre-1960")
 
year_tooltip = [
    alt.Tooltip("year:O", title="Release year"),
    alt.Tooltip("avg_rating:Q", title="Mean rating", format=".2f"),
    alt.Tooltip("rolling_avg:Q", title="5-year average", format=".2f"),
    alt.Tooltip("num_ratings:Q", title="Ratings", format=","),
]
x_year = alt.X("year:Q", title="Movie release year", axis=alt.Axis(format="d"))
base = alt.Chart(by_year)
 
yearly_points = base.mark_circle(color="#4c78a8", opacity=0.55).encode(
    x=x_year,
    y=alt.Y("avg_rating:Q", title="Mean rating (1–5)", scale=alt.Scale(domain=[2.5, 4.5])),
    size=alt.Size("num_ratings:Q", title="Number of ratings", scale=alt.Scale(range=[15, 400])),
    tooltip=year_tooltip,
)
yearly_line = base.mark_line(color="#4c78a8", opacity=0.3, strokeWidth=1).encode(
    x=x_year, y="avg_rating:Q"
)
trend_line = base.mark_line(color="#c9673a", strokeWidth=3).encode(
    x=x_year, y="rolling_avg:Q", tooltip=year_tooltip
)
overall_rule = (
    alt.Chart(pd.DataFrame({"overall": [overall_avg]}))
    .mark_rule(strokeDash=[4, 4], color="gray")
    .encode(y="overall:Q")
)
 
st.altair_chart(
    (yearly_line + yearly_points + trend_line + overall_rule)
    .properties(height=480, title="Rating over Time: mean rating by movie release year"),
    use_container_width=True,
)
st.caption(
    "Blue dots are each release year's mean rating, sized by how many ratings that year has. "
    "The orange line is a 5-year rolling average weighted by number of ratings. "
    f"The dashed line is the overall average ({overall_avg:.2f}). "
    "Early years have few ratings, so their dots jump around more. "
    "Ratings for 30 rows with no release year are excluded."
)
 
with st.expander("See the numbers for Question 3"):
    st.dataframe(
        by_year.style.format(
            {"avg_rating": "{:.2f}", "rolling_avg": "{:.2f}", "num_ratings": "{:,}"}
        ),
        hide_index=True,
        width="stretch",
    )
 


# ---------- Question 4 — Best Movies, With a Floor ----------
st.divider()
st.header("Question 4 — Best Movies, With a Floor")
st.write(
    "What are the top 5 best-rated movies, once you only count movies with at least "
    "50 ratings? What changes if you raise that floor to 150?"
)
 
 
@st.cache_data
def movie_stats(df: pd.DataFrame) -> pd.DataFrame:
    """Mean rating and number of ratings for every movie (grouped by movie_id)."""
    return (
        df.groupby(["movie_id", "title"])["rating"]
        .agg(avg_rating="mean", num_ratings="count")
        .reset_index()
    )
 
 
def top_movies(stats: pd.DataFrame, floor: int, n: int = 5) -> pd.DataFrame:
    """Top n movies by mean rating among movies with at least `floor` ratings.
 
    Ties on mean rating are broken by number of ratings.
    """
    eligible = stats[stats["num_ratings"] >= floor]
    top = eligible.sort_values(["avg_rating", "num_ratings"], ascending=False).head(n).copy()
    top["rank"] = range(1, len(top) + 1)
    return top
 
 
stats = movie_stats(df)
top50 = top_movies(stats, 50)
top150 = top_movies(stats, 150)
dropped = top50[~top50["movie_id"].isin(top150["movie_id"])]
added = top150[~top150["movie_id"].isin(top50["movie_id"])]
 
q4a, q4b, q4c = st.columns(3)
q4a.metric("Movies with 50+ ratings", f"{(stats['num_ratings'] >= 50).sum():,}")
q4b.metric("Movies with 150+ ratings", f"{(stats['num_ratings'] >= 150).sum():,}")
q4c.metric("Top-5 movies that change", f"{len(dropped)} of 5")
 
STATUS_COLORS = alt.Scale(
    domain=["In both top 5s", "Only in the 50+ top 5", "Only in the 150+ top 5"],
    range=["#4c78a8", "#c9673a", "#2b8a6e"],
)
 
 
def top_chart(top: pd.DataFrame, floor: int) -> alt.Chart:
    in_both = top["movie_id"].isin(top50["movie_id"]) & top["movie_id"].isin(top150["movie_id"])
    only_label = "Only in the 50+ top 5" if floor == 50 else "Only in the 150+ top 5"
    top = top.assign(status=["In both top 5s" if b else only_label for b in in_both])
    bars = (
        alt.Chart(top)
        .mark_bar()
        .encode(
            x=alt.X("avg_rating:Q", title="Mean rating (1–5)", scale=alt.Scale(domain=[1, 5])),
            y=alt.Y("title:N", sort=alt.EncodingSortField("rank", order="ascending"), title=None,
                    axis=alt.Axis(labelLimit=260)),
            color=alt.Color("status:N", title=None, scale=STATUS_COLORS,
                            legend=alt.Legend(orient="bottom")),
            tooltip=[
                alt.Tooltip("rank:O", title="Rank"),
                alt.Tooltip("title:N", title="Movie"),
                alt.Tooltip("avg_rating:Q", title="Mean rating", format=".3f"),
                alt.Tooltip("num_ratings:Q", title="Ratings", format=","),
            ],
        )
    )
    labels = bars.mark_text(align="left", dx=4, color="gray").encode(
        text=alt.Text("avg_rating:Q", format=".2f"), color=alt.value("gray")
    )
    return (bars + labels).properties(height=260, title=f"Top 5 with at least {floor} ratings")
 
 
left4, right4 = st.columns(2)

with left4:
    st.altair_chart(
        top_chart(top50, 50),
        use_container_width=True
    )

with right4:
    st.altair_chart(
        top_chart(top150, 150),
        use_container_width=True
    )
if len(dropped):
    st.markdown(
        "**What changes at 150:** "
        + ", ".join(f"{t} ({n} ratings)" for t, n in zip(dropped["title"], dropped["num_ratings"]))
        + " drop out because they have fewer than 150 ratings. "
        + ", ".join(added["title"])
        + " move up into the top 5."
    )
 
st.caption(
    "Mean rating uses every individual rating for the movie. Ties are broken by number of "
    "ratings. Without any floor, the top of the list is movies rated 5.0 by only 1–3 people."
)
 
with st.expander("Try your own floor"):
    floor = st.slider("Minimum number of ratings", 1, 300, 50, step=5)
    custom = top_movies(stats, floor, n=10)
    st.write(f"{(stats['num_ratings'] >= floor).sum():,} movies have at least {floor} ratings. Top 10:")
    st.dataframe(
        custom[["rank", "title", "avg_rating", "num_ratings"]].style.format(
            {"avg_rating": "{:.3f}", "num_ratings": "{:,}"}
        ),
        hide_index=True,
        width="stretch",
    )