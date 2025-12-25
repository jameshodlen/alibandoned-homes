# Alibandoned Homes Prediction System 🏚️

[![CI/CD Status](https://github.com/jameshodlen/alibandoned-homes/actions/workflows/test.yml/badge.svg)](https://github.com/jameshodlen/alibandoned-homes/actions)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python Level](https://img.shields.io/badge/Python-3.11-blue.svg)](https://www.python.org/)
[![React Version](https://img.shields.io/badge/React-18.0-blue.svg)](https://reactjs.org/)

A comprehensive AI-powered system for predicting, identifying, and managing abandoned properties using geospatial analysis, satellite imagery, and community data.

## 🚀 Features

- **Geospatial Prediction Engine**: Identifying high-risk properties using tax, crime, and utility data.
- **Multi-Source Imagery**: Integration with Sentinel-2 satellite data and Mapillary street view.
- **Computer Vision Analysis**: Automated change detection (SSIM) and abandonment indicators (vegetation, boarding).
- **Interactive React Frontend**: Leaflet mapping, filtering, and administration dashboard.
- **Robust Backend**: FastAPI with async SQLAlchemy, PostGIS, and advanced security (JWT, Rate Limiting).
- **Enterprise-Ready**: Dockerized deployment, CI/CD pipelines, and comprehensive testing.

## 🏗️ Architecture

The system is built as a modular application:

- **Backend**: `backend/` - Python FastAPI application
  - **API**: RESTful endpoints for locations, predictions, and admin tasks.
  - **ML Pipeline**: Scikit-learn random forests and custom heuristic models.
  - **Database**: PostgreSQL + PostGIS for spatial data.
- **Frontend**: `frontend/` - React SPA (Vite/CRA)
  - **UI**: Tailwind CSS + Headless UI.
  - **Map**: React-Leaflet for visualization.

## 🏃 Quick Start

### Using Docker (Recommended)

```bash
# 1. Clone the repository
git clone https://github.com/jameshodlen/alibandoned-homes.git
cd alibandoned-homes

# 2. Configure environment
cp .env.example .env
# Edit .env with your secrets (or leave defaults for dev)

# 3. Launch stack
docker-compose up -d --build

# 4. Access App
# Frontend: http://localhost:3000
# API Docs: http://localhost:8000/docs
```

### Manual Development Setup

See detailed guides:

- [Backend Setup](backend/README.md)
- [Frontend Setup](frontend/README.md)

## 📚 Documentation

We believe in extensive documentation. Check out our guides:

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
