# User Manual: Abandoned Homes Prediction System

Welcome to the Abandoned Homes Prediction System. This guide will help you specifically manage the day-to-day operations of the application, from reviewing AI predictions to managing field data.

## 1. Getting Started

### Accessing the App

1.  Open your web browser (Chrome or Edge recommended).
2.  Navigate to [http://localhost:3000](http://localhost:3000) (or your deployment URL).
3.  **Login**: Use the credentials provided during setup (or default `admin` / `password` if dev mode).

### The Main Interface

- **The Map**: Shows all tracked properties.
  - 🔴 **Red Markers**: High probability of abandonment.
  - 🟡 **Yellow Markers**: Medium probability / Needs review.
  - 🟢 **Green Markers**: Likely occupied / Confirmed safe.
- **Sidebar**: Displays details for the selected property.

---

## 2. Typical Workflow

### A. Reviewing a Prediction

The AI runs automatically in the background. Your job is to verify its findings.

1.  Click on a **Red Marker** on the map.
2.  Review the **AI Confidence Score** in the sidebar.
3.  Check the **Satellite Imagery**. use the "Toggle Satellite" button.
    - Look for: Overgrown grass, damaged roofs, missing windows.
4.  Check **Street View** (if available) for a closer look.

### B. Changing Status

Once you have made a decision:

1.  Click the **Edit Status** dropdown.
2.  Select:
    - `Confirmed Abandoned`: You are sure it's empty.
    - `Occupied`: The AI was wrong; people live here.
    - `Investigate`: Send a field team to check.

### C. Adding a New Location Manually

If you spot an abandoned home that isn't on the map:

1.  Click the **(+) Add Location** button in the top right.
2.  Click the location on the map.
3.  Fill in any known details (address, notes).
4.  Click **Save**.

---

## 3. Data Entry & Photos

Uploading clear photos helps the AI learn better.

- **How to Upload**: Open a location -> Click "Photos" tab -> "Upload Photo".
- **Best Practices**:
  - ✅ **Do**: Take photos from the street.
  - ✅ **Do**: Capture the front door and windows.
  - ✅ **Do**: Use good lighting (daytime).
  - ❌ **Don't**: Upload blurry photos.
  - ❌ **Don't**: Take photos with people clearly visible (privacy).

---

## 4. Retraining the Model

As you confirm more homes (marking them "Confirmed Abandoned" or "Occupied"), the system accumulates "Ground Truth" data.

**When to Retrain:**

- After you have verified/added **20-50 new locations**.
- If the AI seems to be making the same mistake repeatedly.

**How to Retrain:**

1.  Go to the **Settings** page (Gear icon).
2.  Scroll to the **Machine Learning** section.
3.  Click **"Retrain Model"**.
4.  Wait for the success message (usually 1-5 minutes).

**Note**: The system will be slightly slower during training.

---

## 5. Troubleshooting

- **App is unresponsive**: Try refreshing the page.
- **"Backend Offline"**: The server might be restarting. Wait 1 minute.
- **Map not loading**: Check your internet connection.
