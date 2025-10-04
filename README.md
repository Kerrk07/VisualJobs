# VisualJobs

A personal dashboard to visualize job hunting progress using Notion data and Plotly Sankey diagrams.

## Overview

VisualJobs pulls data from a Notion database and generates visualizations showing how job applications flow through various stages (Applied, Recruiter, Interview, Offer, etc.). It also displays metrics like response rate and offer rate.

## Setup

### 1. Clone and Install

```bash
git clone https://github.com/yourusername/visualjobs.git
cd visualjobs
conda create -n visualjobs python=3.10
conda activate visualjobs
pip install -r requirements.txt
```

### 2. Configure Notion

Create a `.env` file:

```
NOTION_API_KEY=your_notion_integration_key
NOTION_DATABASE_ID=your_database_id
```

Ensure your Notion integration has access to the database.

### 3. Notion Database Schema

Required properties:

| Property | Type | Description |
|----------|------|-------------|
| Company | Title | Company name |
| Status | Select | Application status |
| Source | Select | Application source |
| Applied Date | Date | Application date |

Example Status values: Applied, Rejected, Recruiter, Interview, Offer, Accepted, Declined

Example Source values: Direct Apply, Recruiter, Referral, Job Board

## Usage

```bash
python app.py
```

Open `http://127.0.0.1:8050` in your browser.

## License

MIT
