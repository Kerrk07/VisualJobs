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
            "Applied_Date": props["Applied Date"]["rich_text"][0]["plain_text"] if props["Applied Date"]["rich_text"] else "",
            "Link": props["Link"]["url"] if props["Link"]["url"] else "",
        })
    return pd.DataFrame(records)

pages = fetch_notion_records(database_id)
df = parse_notion_response(pages)

# -------------------------------
# 3. Create Dashboard Data
# -------------------------------
total_apps = len(df)

# % response: anything that is NOT 'No started'
responded = df[df["Follow-up"] != "Not started"]
response_rate = len(responded) / total_apps * 100 if total_apps else 0

# % offer
offers = df[df["Follow-up"] == "Offer"]
offer_rate = len(offers) / total_apps * 100 if total_apps else 0

# % accepted
accepted = df[df["Follow-up"] == "Accepted"]
accept_rate = len(accepted) / len(offers) * 100 if len(offers) else 0


# -------------------------------
# 4. Create Sankey data
# -------------------------------
def build_sankey_data(df):
    grouped = df.groupby(["Stage", "Follow-up"]).size().reset_index(name="count")

    labels = pd.Series(grouped["Stage"].tolist() + grouped["Follow-up"].tolist()).unique().tolist()
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
# 5. Build Dash App
# -------------------------------
app = Dash(__name__)

link_color = [f"rgba(0,0,200,0.1)"] * len(value)

fig = go.Figure(go.Sankey(
    node=dict(label=labels, pad=15, thickness=20),
    link=dict(
        source=source,
        target=target,
        value=value,
        customdata=customdata,
        hovertemplate="%{customdata}<br>Value: %{value}<extra></extra>",
        color=link_color
    )
))

summary_text = f"""
Total Applications: {total_apps}
Response Rate: {response_rate:.1f}%
Offer Rate: {offer_rate:.1f}%
Acceptance Rate: {accept_rate:.1f}%
"""

summary_text = html.Div([
    html.P(f"📋 Total Applications: {total_apps}"),
    html.P(f"📬 Response Rate: {response_rate:.1f}%"),
    html.P(f"🎯 Offer Rate: {offer_rate:.1f}%"),
    html.P(f"✅ Acceptance Rate: {accept_rate:.1f}%"),
])

app.layout = html.Div([
    html.H1(
    "VisualJobs",
    style={
        "fontFamily": "sans-serif",
        "color": "rgba(0, 0, 0, 0.5)",
        "textAlign": "center",
        "fontSize": "48px"
    }),
    dcc.Graph(id="sankey", figure=fig),

    html.Div(summary_text, id="summary", style={
    "fontFamily": "sans-serif",
    "color": "rgba(0, 0, 0, 0.5)",  # 50% opacity dark gray
    "textAlign": "center",
    "fontSize": "20px",
    "lineHeight": "2",
    "marginTop": "30px"
    })
])

# -------------------------------
# 5. Run
# -------------------------------
if __name__ == "__main__":
    app.run_server(debug=True)
