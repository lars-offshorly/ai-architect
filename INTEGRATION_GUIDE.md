# Service Integration Guide: AI Dashboard Generator

This guide explains how to integrate the AI Dashboard Generator service into your external application or service. It focuses on the primary workflow for generating dashboards.

## Integration Workflow

The integration flow follows these three steps:

1. **Prepare Template**: Customize a dashboard template's widgets or add mock data.
2. **Generate Dashboard**: Submit the configuration to the dashboard generation endpoint.
3. **Display Dashboard**: Use the returned URL to embed or link to the dashboard.

---

### Step 1: Prepare Template

Start with a dashboard configuration that fits your needs. You can personalize widgets, filters, and data configurations.

**Example Personalization Logic (Pseudo-code):**
```python
# 1. Load the template
template = load_template_config("hr_management")

# 2. Personalize values
template["dashboard_name"] = "Regional HR Hub - North America"
template["widgets"][0]["calculation"]["datasets"][0]["filters"]["region"] = "North America"

# 3. Add dynamic report content
template["report"] = "Customized report content for North America..."
```

---

### Step 2: Generate Dashboard

Submit the personalized payload to the `/generate/` endpoint.

**Request:**
- **URL**: `POST /api/v1/dashboards/generate/`
- **Payload**:
```json
{
  "dashboard_name": "Regional HR Hub - North America",
  "source": "analytics",
  "report": "...",
  "widgets": [...]
}
```

**Response:**
On success, you will receive the dashboard ID and a URL.
```json
{
  "success": true,
  "dashboard": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "name": "Regional HR Hub - North America - 0414241700",
    "url": "/dashboard/550e8400-e29b-41d4-a716-446655440000"
  }
}
```

---

### Step 3: Display the Dashboard

The response provides a relative URL. You should concatenate this with your Dashboard platform's base URL to display it to the user.

**Implementation Example (JavaScript):**
```javascript
async function handleGenerate() {
  const response = await api.post('/dashboards/generate/', templateData);
  if (response.success) {
    const dashboardUrl = `${DASHBOARD_PLATFORM_BASE}${response.dashboard.url}`;
    // Either redirect the user or embed in an iframe
    window.open(dashboardUrl, '_blank');
  }
}
```

## Summary of Endpoints

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/api/v1/dashboards/generate/` | `POST` | Create a new dashboard with positioned widgets. |
