# Data Catalog & Governance Platform

[\![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[\![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[\![Flask](https://img.shields.io/badge/Flask-2.0+-green.svg)](https://flask.palletsprojects.com/)
[\![React](https://img.shields.io/badge/React-18+-blue.svg)](https://reactjs.org/)

A comprehensive **enterprise-grade data catalog and governance platform** designed for UK Housing Associations, featuring advanced compliance tracking, interactive data lineage visualization, and sophisticated search capabilities.

## 🌟 Key Features

- **📊 Interactive Dashboard**: Real-time compliance metrics with D3.js visualizations
- **🔍 Advanced Search**: Faceted search with smart suggestions and highlighting
- **🌐 Data Lineage**: Interactive D3.js graphs with multi-level traversal
- **🔒 Compliance Tracking**: GDPR-ready field-level privacy controls
- **📚 Business Glossary**: Terminology management and standardization
- **🏢 Enterprise SSO**: Microsoft Entra ID integration with role-based access

## 🏗️ Architecture

### Backend (Flask)
- SQLAlchemy database models for assets, compliance, and lineage
- RESTful API routes for all functionality
- Microsoft Entra ID authentication
- Comprehensive compliance tracking

### Frontend (React)
- Single-page application with modern UI
- D3.js data lineage visualization
- Advanced search interface
- Interactive dashboard with charts

## 🚀 Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/kittypony123/data-catalog-webapp.git
cd data-catalog-webapp
```

2. **Set up environment**
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

3. **Configure and run**
```bash
cp .env.example .env
# Edit .env with your configuration
python app.py
```

Visit `http://localhost:5000` to access the application.

## 🎯 Use Cases

**For UK Housing Associations:**
- Regulatory compliance (GDPR, Data Protection Act 2018)
- Data discovery and understanding
- Privacy management for tenant information

**For Data Teams:**
- Comprehensive metadata management
- Data lineage tracking
- Quality monitoring and collaboration

## 🔐 Features

- **Security**: Microsoft Entra ID SSO, role-based access control
- **Compliance**: Field-level privacy controls, risk assessment
- **Visualization**: Interactive D3.js lineage graphs
- **Search**: Advanced faceted search with real-time filtering
- **Analytics**: Comprehensive dashboard with compliance metrics

## 📈 Technology Stack

- **Backend**: Flask, SQLAlchemy, Microsoft Entra ID
- **Frontend**: React, D3.js, Modern CSS
- **Database**: SQL Server / SQLite
- **Deployment**: Docker, Azure App Service ready

---

**Built for the UK Housing Association sector** 🏠

*Empowering data governance through technology*
