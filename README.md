# Alibandoned Homes Prediction System 🏚️

[![CI/CD Status](https://github.com/jameshodlen/alibandoned-homes/actions/workflows/test.yml/badge.svg)](https://github.com/jameshodlen/alibandoned-homes/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Level](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![React Version](https://img.shields.io/badge/React-18.0-blue.svg)](https://reactjs.org/)

A comprehensive AI-powered system for predicting, identifying, and managing abandoned properties using geospatial analysis, satellite imagery, and community data.

## 🚀 Features

- **Geospatial Prediction Engine**: Identifying high-risk properties using tax, crime, and utility data.
- **Remote Sensing Pipeline**: Advanced cloud masking, mosaic normalization, and vegetation canopy analysis (adapted from USFS research).
- **Multi-Source Imagery**: Integration with Sentinel-2 satellite data, Mapillary street view, and commercial imagery support (Planet Dove).
- **Computer Vision Analysis**: Automated change detection (SSIM) and abandonment indicators.
- **Interactive React Frontend**: Leaflet mapping, filtering, and administration dashboard.
- **Robust Backend**: FastAPI with async SQLAlchemy, PostGIS, and advanced security (JWT, Rate Limiting).
- **Enterprise-Ready**: Dockerized deployment, CI/CD pipelines, and comprehensive ops tooling (Setup Wizard, Makefile).

## 🏗️ Architecture

The system is built as a modular application:

- **Backend**: `backend/` - Python FastAPI application
  - **API**: RESTful endpoints for locations, predictions, and admin tasks.
  - **ML Pipeline**: Random forests, remote sensing modules (masking, normalization), and heuristic models.
  - **Database**: PostgreSQL + PostGIS for spatial data.
- **Frontend**: `frontend/` - React SPA (Vite/CRA)
  - **UI**: Tailwind CSS + Headless UI.
  - **Map**: React-Leaflet for visualization.

## 🏃 Quick Start

### 1. Automated Setup (Recommended)

We provide a wizard to handle prerequisites, configuration, and deployment.

```bash
# 1. Clone the repository
git clone https://github.com/jameshodlen/alibandoned-homes.git
cd alibandoned-homes

# 2. Run the Setup Wizard
# This generates secrets, checks Docker dependencies, and launches the app.
make setup
# OR
python scripts/setup_wizard.py
```

### 2. Manual Access

- **Frontend**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **User Manual**: [docs/USER_MANUAL.md](docs/USER_MANUAL.md)

### 3. Common Commands (Makefile)

```bash
make up      # Start services
make down    # Stop services
make logs    # View logs
make update  # Pull and rebuild
```

### Manual Development Setup (Legacy)

See detailed guides:

- [Backend Setup](backend/README.md)
- [Frontend Setup](frontend/README.md)

## 📚 Documentation

We believe in extensive documentation. Check out our guides:

- **[User Manual](docs/USER_MANUAL.md)**: Daily usage guide for administrators.
- **[API Guide](docs/API_GUIDE.md)**: Full API reference and authentication details.
- **[Advanced Features](docs/ADVANCED_FEATURES.md)**: Guide to imagery analysis and privacy-safe exports.
- **[Deployment Guide](docs/DEPLOYMENT_GUIDE.md)**: Production setup with Docker and security hardening.
- **[Testing Guide](docs/TESTING_GUIDE.md)**: How we test (Unit, Integration, E2E) and best practices.
- **[Docker Concepts](docs/DOCKER_CONCEPTS.md)**: Educational primer on containerization.

## 🧪 Testing

We run a comprehensive test suite including E2E tests with Cypress.

```bash
# Run backend tests
cd backend && pytest

# Run frontend tests
cd frontend && npm test

# Run E2E tests
cd frontend && npm run cypress:run
```

## 🔐 Security & Privacy

- **Privacy First**: Public exports automatically obfuscate coordinates to ~110m precision.
- **Secure**: Implements HSTS, CSP headers, and JWT authentication with tiered rate limiting.

## 🤝 Contributing

Contributions are welcome! Please read our [Contribution Guidelines](CONTRIBUTING.md) (coming soon).

1.  Fork the Project
2.  Create your Feature Branch (`git checkout -b feature/AmazingFeature`)
3.  Commit your Changes (`git commit -m 'Add some AmazingFeature'`)
4.  Push to the Branch (`git push origin feature/AmazingFeature`)
5.  Open a Pull Request

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

_Built with ❤️ for urban revitalization._
