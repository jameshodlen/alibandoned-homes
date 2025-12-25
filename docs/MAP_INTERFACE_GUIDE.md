# Map Interface Guide

## React Concepts

### Components

Reusable UI pieces. Each component manages its own logic and rendering.

### Props

Data passed from parent to child component (read-only).

### State

Component's internal data that can change.

### Hooks

Functions that add features to components:

- `useState`: Add state
- `useEffect`: Run code after render
- `useCallback`: Memoize functions
- `useRef`: Persist values without re-rendering

## Leaflet Basics

### Coordinates

Latitude/Longitude format: `[lat, lng]`

- Latitude: -90 to 90 (North/South)
- Longitude: -180 to 180 (East/West)

### Tile Layers

Map divided into 256x256 pixel tiles

- Zoom 0: Entire world in 1 tile
- Zoom 19: Street-level detail

### Markers

Points on map with icons and popups

### Heatmaps

Density visualization using color gradients

## Customization

### Change Map Center

```jsx
const [mapCenter, setMapCenter] = useState([lat, lng]);
```

### Add Custom Marker Icon

```jsx
const icon = L.icon({
  iconUrl: "/path/to/icon.png",
  iconSize: [25, 41],
});
```

### Change Heatmap Colors

```jsx
gradient: {
  0.0: 'blue',
  0.5: 'yellow',
  1.0: 'red'
}
```

## Integration Quick Start

### 1. Installation

```bash
npm install leaflet react-leaflet leaflet.heat leaflet-draw axios
```

### 2. Styles

Import Leaflet CSS in your `index.js` or `App.js`:

```js
import "leaflet/dist/leaflet.css";
```

### 3. Usage inside a page

```jsx
import MapView from "./components/Map/MapView";
import { useMapData } from "./hooks/useMapData";

const Dashboard = () => {
  const { locations } = useMapData();

  return (
    <div className="h-screen w-full">
      <MapView locations={locations} />
    </div>
  );
};
```
