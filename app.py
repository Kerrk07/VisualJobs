import os
import pandas as pd
from dotenv import load_dotenv
from notion_client import Client

from dash import Dash, html, dcc, Input, Output
import plotly.graph_objects as go

# -------------------------------
# 1. Load environment and Notion API
# -------------------------------
load_dotenv()
notion_token = os.getenv("NOTION_API_KEY")
database_id = os.getenv("NOTION_DATABASE_ID")

notion = Client(auth=notion_token)

# -------------------------------
# 2. Query and Parse Notion DB
# -------------------------------
def fetch_notion_records(database_id):
    results = []
    response = notion.databases.query(database_id=database_id)
    results.extend(response["results"])
    while response.get("has_more"):
        response = notion.databases.query(
            database_id=database_id, start_cursor=response["next_cursor"]
        )
        results.extend(response["results"])
    return results

def parse_notion_response(pages):
    records = []
    for page in pages:
        props = page["properties"]
        records.append({
            "Company": props["Company"]["title"][0]["plain_text"] if props["Company"]["title"] else "",
            "Stage": props["Stage"]["status"]["name"] if props["Stage"]["status"] else "",
            "Follow-up": props["Follow-up Status"]["status"]["name"] if props["Follow-up Status"]["status"] else "",
            "Position": props["Position"]["rich_text"][0]["plain_text"] if props["Position"]["rich_text"] else "",
            "Applied Date": props["Applied Date"]["rich_text"][0]["plain_text"] if props["Applied Date"]["rich_text"] else "",
            "Link": props["Link"]["url"] if props["Link"]["url"] else "",
        })
    return pd.DataFrame(records)

pages = fetch_notion_records(database_id)
df = parse_notion_response(pages)

# -------------------------------
# 3. Create Sankey data
# -------------------------------
def build_sankey_data(df):
    grouped = df.groupby(["Stage", "Follow-up"]).size().reset_index(name="count")

    labels = list(pd.unique(grouped["Stage"].tolist() + grouped["Follow-up"].tolist()))
    label_map = {label: i for i, label in enumerate(labels)}

    source = [label_map[row["Stage"]] for _, row in grouped.iterrows()]
    target = [label_map[row["Follow-up"]] for _, row in grouped.iterrows()]
    value = grouped["count"].tolist()
    customdata = [f'{row["Stage"]} → {row["Follow-up"]}' for _, row in grouped.iterrows()]

    # For click detail
    detail_lookup = {
        key: df[(df["Stage"] == key[0]) & (df["Follow-up"] == key[1])]
        for key in zip(grouped["Stage"], grouped["Follow-up"])
    }

    return labels, source, target, value, customdata, detail_lookup

labels, source, target, value, customdata, detail_lookup = build_sankey_data(df)

# -------------------------------
# 4. Build Dash App
# -------------------------------
app = Dash(__name__)

fig = go.Figure(go.Sankey(
    node=dict(label=labels, pad=15, thickness=20),
    link=dict(
        source=source,
        target=target,
        value=value,
        customdata=customdata,
        hovertemplate="%{customdata}<br>Count: %{value}<extra></extra>"
    )
))

app.layout = html.Div([
    html.H2("🎯 VisualJobs – Notion Job Tracker Sankey"),
    dcc.Graph(id="sankey", figure=fig),
    html.Div(id="details", style={"whiteSpace": "pre-wrap", "marginTop": 20})
])

@app.callback(
    Output("details", "children"),
    Input("sankey", "clickData")
)
def show_details(clickData):
    if clickData:
        label = clickData["points"][0]["customdata"]
        stage, followup = label.split(" → ")
        df_sub = detail_lookup.get((stage, followup))
        if df_sub is not None and not df_sub.empty:
            return "\n".join(
                f"{r.Company} | {r.Position} | {r['Applied Date']} | {r.Link}"
                for r in df_sub.itertuples()
            )
    return "Click on a path to see detailed applications."

# -------------------------------
# 5. Run
# -------------------------------
if __name__ == "__main__":
    app.run_server(debug=True)
