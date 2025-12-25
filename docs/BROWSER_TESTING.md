# Browser Testing Guide

Due to the complexity of the application stack, the first run requires building containers and installing dependencies which may take time.

## 1. Prerequisites

Ensure you have the stack running:

```bash
docker-compose up -d
```

Wait for all services to be `healthy`.

## 2. Manual Walkthrough Script

Perform the following steps to verify the application features:

### A. Viewer Flow

1. **Open Application**: Navigate to `http://localhost:3000`.
2. **Interact with Map**:
   - Zoom in/out to Detroit area.
   - Toggle layers (Street/Satellite/Dark) using the top-right selector.
3. **View Locations**:
   - Click on existing markers (Red/Yellow/Green).
   - Verify Popup shows Address, Status, and Confidence.

### B. Reporting Flow

1. **Report Abandoned Home**:
   - Click the "Add Location" button (or map click if enabled).
   - Fill form:
     - Address: "123 Test St"
     - Condition: "Roof collapsed"
     - Status: "Predicted"
   - Submit.
   - Verify new marker appears.

### C. Admin & Advanced Flow

1. **Access Admin**: Navigate to `http://localhost:3000/admin`.
2. **Review Dashboard**: Check stats (Total Locations, Pending Reviews).
3. **Imagery Analysis**:
   - Select a location.
   - Click "Fetch Imagery" (simulates Mapillary/Sentinel).
   - View results.

## 3. Automated E2E Testing

We have configured Cypress for automated browser testing.

```bash
cd frontend
npm run cypress:run
```

This will automatically execute the user flows and record a video in `frontend/cypress/videos`.
