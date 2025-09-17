import os
import pandas as pd
from dotenv import load_dotenv
from notion_client import Client

from dash import Dash, html, dcc
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

        # Get the follow-up status and OA date
        follow_up_status = props["Follow-up Status"]["status"]["name"] if props.get("Follow-up Status", {}).get("status") else "Not started"
        has_oa = bool(props.get("OA Date", {}).get("date"))
        has_interview = bool(props.get("Interview Date", {}).get("date"))

        # Determine the current stage based on available data
        if follow_up_status == "Offer":
            current_stage = "Offer Received"
        elif follow_up_status == "Rejection":
            if has_interview:
                current_stage = "Rejected (Post-Interview)"
            elif has_oa:
                current_stage = "Rejected (Post-OA)"
            else:
                current_stage = "Rejected (Initial)"
        elif follow_up_status == "Withdraw":
            current_stage = "Withdrawn"
        elif has_interview:
            current_stage = "Interview Completed"
        elif has_oa:
            current_stage = "OA Completed"
        elif follow_up_status == "In progress":
            current_stage = "In Review"
        else:
            current_stage = "Applied"

        records.append({
            "Company": props["Company"]["title"][0]["plain_text"] if props.get("Company", {}).get("title") else "",
            "CurrentStage": current_stage,
            "Status": follow_up_status,
            "HasOA": has_oa,
            "HasInterview": has_interview,
            "Position": props["Position"]["rich_text"][0]["plain_text"] if props.get("Position", {}).get("rich_text") else "",
            "Applied_Date": props["Applied Date"]["rich_text"][0]["plain_text"] if props.get("Applied Date", {}).get("rich_text") else "",
            "Link": props["Link"]["url"] if props.get("Link", {}).get("url") else "",
        })
    return pd.DataFrame(records)

pages = fetch_notion_records(database_id)
df = parse_notion_response(pages)

# -------------------------------
# 3. Create Dashboard Data
# -------------------------------
total_apps = len(df)

# % response: anything that is NOT 'Not started'
responded = df[df["Status"] != "Not started"]
response_rate = len(responded) / total_apps * 100 if total_apps else 0

# % with OA
with_oa = df[df["HasOA"] == True]
oa_rate = len(with_oa) / total_apps * 100 if total_apps else 0

# % with interview
with_interview = df[df["HasInterview"] == True]
interview_rate = len(with_interview) / total_apps * 100 if total_apps else 0

# % offer
offers = df[df["Status"] == "Offer"]
offer_rate = len(offers) / total_apps * 100 if total_apps else 0

# % rejected
rejected = df[df["Status"] == "Rejection"]
rejection_rate = len(rejected) / total_apps * 100 if total_apps else 0


# -------------------------------
# 4. Create Sankey data for application flow
# -------------------------------
def build_sankey_data(df):
    # Create flows between stages
    flows = []

    # Applied → Next stages
    applied_count = len(df[df["CurrentStage"] == "Applied"])
    in_review_count = len(df[df["CurrentStage"] == "In Review"])
    oa_completed_count = len(df[df["CurrentStage"] == "OA Completed"])
    interview_count = len(df[df["CurrentStage"] == "Interview Completed"])
    offer_count = len(df[df["CurrentStage"] == "Offer Received"])
    rejected_initial = len(df[df["CurrentStage"] == "Rejected (Initial)"])
    rejected_oa = len(df[df["CurrentStage"] == "Rejected (Post-OA)"])
    rejected_interview = len(df[df["CurrentStage"] == "Rejected (Post-Interview)"])
    withdrawn_count = len(df[df["CurrentStage"] == "Withdrawn"])

    # Build flow connections
    if applied_count > 0:
        flows.append(("Applied", "No Response Yet", applied_count))
    if in_review_count > 0:
        flows.append(("Applied", "In Review", in_review_count))
    if oa_completed_count > 0:
        flows.append(("In Review", "OA Completed", oa_completed_count))
    if interview_count > 0:
        flows.append(("OA Completed", "Interview Completed", interview_count))
    if offer_count > 0:
        flows.append(("Interview Completed", "Offer Received", offer_count))
    if rejected_initial > 0:
        flows.append(("Applied", "Rejected (Initial)", rejected_initial))
    if rejected_oa > 0:
        flows.append(("OA Completed", "Rejected (Post-OA)", rejected_oa))
    if rejected_interview > 0:
        flows.append(("Interview Completed", "Rejected (Post-Interview)", rejected_interview))
    if withdrawn_count > 0:
        flows.append(("Applied", "Withdrawn", withdrawn_count))

    # Create labels list (unique stages)
    all_stages = set()
    for source, target, _ in flows:
        all_stages.add(source)
        all_stages.add(target)
    labels = list(all_stages)

    # Create label mapping
    label_map = {label: i for i, label in enumerate(labels)}

    # Create source, target, and value lists
    source = [label_map[flow[0]] for flow in flows]
    target = [label_map[flow[1]] for flow in flows]
    value = [flow[2] for flow in flows]
    customdata = [f'{flow[0]} → {flow[1]}: {flow[2]} applications' for flow in flows]

    return labels, source, target, value, customdata, None

labels, source, target, value, customdata, _ = build_sankey_data(df)

# -------------------------------
# 5. Build Dash App
# -------------------------------
app = Dash(__name__)

link_color = [f"rgba(0,0,200,0.1)"] * len(value)

# Create modern color scheme for different stages
node_colors = []
for label in labels:
    if "Applied" in label:
        node_colors.append("#6366F1")  # Indigo
    elif "Review" in label or "No Response" in label:
        node_colors.append("#94A3B8")  # Slate gray
    elif "OA" in label:
        node_colors.append("#F59E0B")  # Amber
    elif "Interview" in label:
        node_colors.append("#8B5CF6")  # Violet
    elif "Offer" in label:
        node_colors.append("#10B981")  # Emerald green
    elif "Rejected" in label:
        node_colors.append("#EF4444")  # Red
    elif "Withdrawn" in label:
        node_colors.append("#6B7280")  # Gray
    else:
        node_colors.append("#94A3B8")  # Default slate gray

# Create gradient colors for links based on source node
link_colors = []
for s_idx in source:
    source_label = labels[s_idx]
    if "Applied" in source_label:
        link_colors.append("rgba(99, 102, 241, 0.4)")  # Indigo
    elif "OA" in source_label:
        link_colors.append("rgba(245, 158, 11, 0.4)")  # Amber
    elif "Interview" in source_label:
        link_colors.append("rgba(139, 92, 246, 0.4)")  # Violet
    else:
        link_colors.append("rgba(148, 163, 184, 0.4)")  # Slate

fig = go.Figure(go.Sankey(
    node=dict(
        label=labels,
        pad=25,
        thickness=20,
        line=dict(color="white", width=2),
        color=node_colors,
        hovertemplate='%{label}<br>Count: %{value}<extra></extra>'
    ),
    link=dict(
        source=source,
        target=target,
        value=value,
        customdata=customdata,
        hovertemplate="%{customdata}<extra></extra>",
        color=link_colors
    )
))

fig.update_layout(
    title={
        'text': "Application Pipeline Flow",
        'font': {'size': 24, 'color': 'rgba(0, 0, 0, 0.5)', 'family': 'sans-serif'}
    },
    font={'size': 12, 'color': '#4B5563'},
    height=600,
    paper_bgcolor='#F9FAFB',
    plot_bgcolor='#F9FAFB'
)

summary_text = html.Div([
    html.Div([
        html.Div([
            html.H1(f"{total_apps}", style={"margin": "0", "color": "#6366F1", "fontSize": "48px", "fontWeight": "bold"}),
            html.P("Applications", style={"margin": "0", "fontSize": "14px", "color": "#6B7280", "fontWeight": "500"})
        ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}),

        html.Div([
            html.H1(f"{response_rate:.0f}%", style={"margin": "0", "color": "#8B5CF6", "fontSize": "48px", "fontWeight": "bold"}),
            html.P("Response Rate", style={"margin": "0", "fontSize": "14px", "color": "#6B7280", "fontWeight": "500"})
        ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}),

        html.Div([
            html.H1(f"{oa_rate:.0f}%", style={"margin": "0", "color": "#F59E0B", "fontSize": "48px", "fontWeight": "bold"}),
            html.P("OA Rate", style={"margin": "0", "fontSize": "14px", "color": "#6B7280", "fontWeight": "500"})
        ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}),

        html.Div([
            html.H1(f"{interview_rate:.0f}%", style={"margin": "0", "color": "#EC4899", "fontSize": "48px", "fontWeight": "bold"}),
            html.P("Interview Rate", style={"margin": "0", "fontSize": "14px", "color": "#6B7280", "fontWeight": "500"})
        ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}),

        html.Div([
            html.H1(f"{offer_rate:.0f}%", style={"margin": "0", "color": "#10B981", "fontSize": "48px", "fontWeight": "bold"}),
            html.P("Offer Rate", style={"margin": "0", "fontSize": "14px", "color": "#6B7280", "fontWeight": "500"})
        ], style={"textAlign": "center", "padding": "20px", "backgroundColor": "white", "borderRadius": "12px", "boxShadow": "0 1px 3px rgba(0,0,0,0.1)"}),
    ], style={"display": "grid", "gridTemplateColumns": "repeat(5, 1fr)", "gap": "20px", "marginTop": "30px"})
])

app.layout = html.Div([
    html.H1(
        "VisualJobs",
        style={
            "fontFamily": "sans-serif",
            "color": "rgba(0, 0, 0, 0.5)",
            "textAlign": "center",
            "fontSize": "48px"
        }
    ),
    dcc.Graph(
        id="sankey",
        figure=fig,
        style={"height": "600px"}
    ),
    summary_text
], style={
    "padding": "40px",
    "backgroundColor": "#F9FAFB",
    "minHeight": "100vh",
    "fontFamily": "system-ui, -apple-system, sans-serif"
})

# -------------------------------
# 5. Run
# -------------------------------
if __name__ == "__main__":
    app.run(debug=True)
