import numpy as np
import pandas as pd


CHART_TYPES = {
    "line": "Line Chart",
    "area": "Area Chart",
    "bar": "Bar / Column Chart",
    "pie": "Pie Chart",
    "donut": "Donut Chart",
    "scatter": "Scatter Plot",
    "histogram": "Histogram",
    "box": "Box Plot",
    "heatmap": "Correlation Heatmap",
    "map": "Geographic Map",
    "candlestick": "Candlestick",
    "treemap": "Treemap",
}

CHART_DETAILS = {
    "line": ("↗", "Track change over time or across ordered categories."),
    "area": ("◒", "Emphasize volume, totals, and cumulative movement."),
    "bar": ("▥", "Compare values across categories with clear columns."),
    "pie": ("◔", "Show how categories contribute to a whole."),
    "donut": ("◉", "Present part-to-whole proportions in a compact view."),
    "scatter": ("⁙", "Find relationships, clusters, and outliers between measures."),
    "histogram": ("▤", "Understand the distribution of a numeric column."),
    "box": ("▣", "Compare spread, median, and unusual observations."),
    "heatmap": ("▦", "Inspect correlation strength across numeric columns."),
    "map": ("⌖", "Compare a numeric measure across geographic locations."),
    "candlestick": ("◫", "Analyze OHLC price movement for crypto markets."),
    "treemap": ("▧", "Explore hierarchical proportions with nested rectangles."),
}


def _plotly():
    try:
        import plotly.express as px
        import plotly.graph_objects as go

        return px, go
    except ImportError as exc:
        raise RuntimeError("Plotly is not installed. Install the requirements first.") from exc


def _sample(df, max_rows=5000):
    if len(df) <= max_rows:
        return df
    return df.sample(max_rows, random_state=42).sort_index()


def build_chart(dataframe, chart_type, x=None, y=None, color=None, aggregation="none"):
    px, go = _plotly()
    df = _sample(dataframe.copy())
    if x and x not in df.columns:
        x = None
    if y and y not in df.columns:
        y = None
    if color and color not in df.columns:
        color = None

    if aggregation != "none" and x and y and pd.api.types.is_numeric_dtype(df[y]):
        grouped = df.groupby(x, dropna=False)[y]
        aggregation_map = {"mean": "mean", "sum": "sum", "median": "median", "count": "count"}
        if aggregation in aggregation_map:
            df = grouped.agg(aggregation_map[aggregation]).reset_index()

    if chart_type in {"line", "area", "bar", "scatter", "box", "violin", "bubble"} and not x:
        x = df.columns[0] if len(df.columns) else None
    if chart_type in {"line", "area", "bar", "scatter", "box", "violin", "bubble"} and not y:
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        y = numeric[0] if numeric else (df.columns[1] if len(df.columns) > 1 else None)
    if chart_type in {"pie", "donut", "treemap"} and not x:
        x = df.columns[0] if len(df.columns) else None
    if chart_type in {"pie", "donut", "treemap"} and not y:
        numeric = df.select_dtypes(include=[np.number]).columns.tolist()
        y = numeric[0] if numeric else None

    if chart_type == "line":
        fig = px.line(df, x=x, y=y, color=color)
    elif chart_type == "area":
        fig = px.area(df, x=x, y=y, color=color)
    elif chart_type == "bar":
        fig = px.bar(df, x=x, y=y, color=color)
    elif chart_type == "pie":
        fig = px.pie(df, names=x, values=y, color=color)
    elif chart_type == "donut":
        fig = px.pie(df, names=x, values=y, color=color, hole=0.55)
    elif chart_type == "scatter":
        fig = px.scatter(df, x=x, y=y, color=color)
    elif chart_type == "histogram":
        source = y or x or df.columns[0]
        fig = px.histogram(df, x=source, color=color)
    elif chart_type == "box":
        fig = px.box(df, x=x, y=y, color=color)
    elif chart_type == "violin":
        fig = px.violin(df, x=x, y=y, color=color, box=True, points="outliers")
    elif chart_type == "bubble":
        size = y
        fig = px.scatter(df, x=x, y=y, color=color, size=size)
    elif chart_type == "heatmap":
        corr = df.select_dtypes(include=[np.number]).corr()
        if corr.empty:
            raise ValueError("A correlation heatmap needs at least two numeric columns.")
        fig = px.imshow(corr, text_auto=True, aspect="auto", color_continuous_scale="Viridis")
    elif chart_type == "map":
        if not x or not y:
            raise ValueError("A geographic map needs a location column and a numeric value column.")
        fig = px.choropleth(df, locations=x, color=y, color_continuous_scale="Viridis")
    elif chart_type == "candlestick":
        required = {"open", "high", "low", "close"}
        normalized = {str(col).lower(): col for col in df.columns}
        if not required.issubset(normalized):
            raise ValueError("Candlesticks need open, high, low, and close columns.")
        date_col = x or df.columns[0]
        fig = go.Figure(
            data=[
                go.Candlestick(
                    x=df[date_col],
                    open=df[normalized["open"]],
                    high=df[normalized["high"]],
                    low=df[normalized["low"]],
                    close=df[normalized["close"]],
                )
            ]
        )
    elif chart_type == "treemap":
        fig = px.treemap(df, path=[x], values=y)
    else:
        raise ValueError("Unknown chart type.")

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=50, b=20),
        title=CHART_TYPES.get(chart_type, "Visualization"),
    )
    return fig
