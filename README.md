# Data Catalog Web Application

A comprehensive data catalog and governance platform built with Flask and React, designed for UK Housing Association data management with enterprise authentication and approval workflows.

## Features

### Core Functionality
- **Data Asset Management**: Create, update, and manage data assets with rich metadata
- **Advanced Search**: Full-text search across assets with filtering and suggestions
- **Data Lineage**: Track relationships between assets (internal and external)
- **Approval Workflow**: Admin approval process for new assets with audit trail
- **Categories & Report Types**: Organize assets with flexible categorization

### Enterprise Features
- **Microsoft Entra ID Authentication**: Secure SSO integration
- **Role-Based Access Control**: Admin, Data Owner, and Contributor roles
- **Team Collaboration**: Team workspaces and shared assets
- **Personal Favorites**: Bookmark and annotate assets
- **Excel Import**: Automated metadata extraction from Excel/CSV files

### Data Governance
- **Approval History**: Complete audit trail of all changes
- **Data Quality Scoring**: Automated quality assessment
- **PII Detection**: Automatic identification of sensitive data
- **Compliance Tracking**: Built-in compliance status monitoring

## Architecture

### Backend (Flask/Python)
- **Framework**: Flask with SQLAlchemy ORM
- **Database**: Microsoft Fabric SQL Analytics Endpoint (or SQLite for development)
- **Authentication**: Microsoft Entra ID with MSAL
- **API**: RESTful endpoints with versioning (`/api/v1`)

### Frontend (React)
- **Framework**: React 18 with hooks
- **UI**: Modern design with Lucide icons and D3.js visualizations
- **Architecture**: Component-based with responsive design
- **Integration**: Direct API consumption of Flask backend

### Database Schema
- **Users & Roles**: Role-based permission system
- **Data Assets**: Core asset metadata with flexible JSON storage
- **Asset Relationships**: Internal and external lineage tracking
- **Teams & Favorites**: Collaboration and personalization features
- **Approval History**: Complete audit trail

## Quick Start

### Prerequisites
- Python 3.8+
- Microsoft Azure account (for Entra ID)
- SQL Server or SQLite for development

### Installation

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd data-catalog-webapp
   ```

2. **Set up Python environment**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Initialize database**
   ```bash
   python -c "from backend.app import create_app; app = create_app(); app.app_context().push(); from backend.models import db; db.create_all()"
   ```

5. **Run the application**
   ```bash
   python app.py
   ```

6. **Access the application**
   - Open http://localhost:5000
   - Sign in with Microsoft account

## Configuration

### Environment Variables

#### Flask Configuration
- `FLASK_ENV`: `development` or `production`
- `FLASK_SECRET_KEY`: Secret key for sessions (change in production)

#### Database Configuration
- `DB_USERNAME`: Database username
- `DB_PASSWORD`: Database password
- `DB_HOST`: Database host (e.g., `your-workspace.sql.azuresynapse.net`)
- `DB_NAME`: Database name
- `DB_DRIVER`: ODBC driver (default: `ODBC Driver 17 for SQL Server`)

#### Microsoft Entra ID Configuration
- `AZURE_TENANT_ID`: Your Azure tenant ID
- `AZURE_CLIENT_ID`: Application client ID
- `AZURE_CLIENT_SECRET`: Application client secret

#### Application Configuration
- `APP_BASE_URL`: Base URL for the application (default: `http://localhost:5000`)
- `API_VERSION`: API version (default: `v1`)

### Microsoft Entra ID Setup

1. **Register Application**
   - Go to Azure Portal > Entra ID > App registrations
   - Create new registration
   - Set redirect URI: `{APP_BASE_URL}/api/v1/auth/callback`

2. **Configure Authentication**
   - Enable ID tokens
   - Add redirect URIs for your environment
   - Configure logout URL

3. **Set Permissions**
   - Add Microsoft Graph permissions: `User.Read`
   - Grant admin consent if required

4. **Create Client Secret**
   - Go to Certificates & secrets
   - Create new client secret
   - Copy the secret value to `AZURE_CLIENT_SECRET`

## API Documentation

### Authentication Endpoints
- `GET /api/v1/auth/login` - Initiate OAuth login
- `GET /api/v1/auth/callback` - OAuth callback handler
- `POST /api/v1/auth/logout` - Logout user
- `GET /api/v1/auth/me` - Get current user info

### Data Assets
- `GET /api/v1/assets` - List assets with filtering
- `POST /api/v1/assets` - Create new asset
- `GET /api/v1/assets/{id}` - Get asset details
- `PUT /api/v1/assets/{id}` - Update asset
- `DELETE /api/v1/assets/{id}` - Delete asset
- `POST /api/v1/assets/{id}/approve` - Approve asset (admin)
- `POST /api/v1/assets/{id}/reject` - Reject asset (admin)

### Categories & Report Types
- `GET /api/v1/categories` - List categories
- `POST /api/v1/categories` - Create category (admin)
- `GET /api/v1/report-types` - List report types
- `POST /api/v1/report-types` - Create report type (admin)

### Search
- `GET /api/v1/search?q={query}` - Search assets
- `GET /api/v1/search/suggestions?q={query}` - Get search suggestions
- `GET /api/v1/search/filters` - Get available filters

### Teams & Users
- `GET /api/v1/teams` - List teams
- `POST /api/v1/teams` - Create team
- `GET /api/v1/users` - List users (admin)
- `PUT /api/v1/users/{id}/role` - Update user role (admin)

## Development

### Project Structure
```
data-catalog-webapp/
├── backend/
│   ├── app/              # Flask application factory
│   ├── config/           # Configuration settings
│   ├── models/           # SQLAlchemy models
│   ├── routes/           # API route handlers
│   └── utils/            # Utility functions
├── frontend/
│   ├── public/           # Static frontend files
│   └── src/              # React source code
├── tests/                # Test files
├── deployment/           # Deployment configurations
├── docs/                 # Documentation
├── app.py               # Main application entry point
├── requirements.txt     # Python dependencies
└── README.md           # This file
```

### Database Models

#### Core Models
- **User**: User accounts with role-based permissions
- **Role**: Permission roles (Admin, Data Owner, Contributor)
- **DataAsset**: Core data asset with metadata and relationships
- **Category**: Asset categorization
- **ReportType**: Template-based asset types

#### Relationship Models
- **AssetRelationship**: Internal and external asset relationships
- **UserFavorite**: User bookmarks and notes
- **Team/TeamMember**: Collaboration workspaces
- **ApprovalHistory**: Complete audit trail

### Adding New Features

1. **Backend API Endpoint**
   - Add route handler in `backend/routes/`
   - Update model if needed in `backend/models/`
   - Add authentication/authorization decorators

2. **Frontend Component**
   - Add React component in frontend
   - Integrate with API endpoints
   - Update navigation if needed

3. **Database Changes**
   - Update model definitions
   - Create migration if needed
   - Update seed data

## Deployment

### Azure App Service

1. **Create App Service**
   ```bash
   az webapp create --resource-group myResourceGroup --plan myAppServicePlan --name myDataCatalog --runtime "PYTHON|3.9"
   ```

2. **Configure Environment Variables**
   ```bash
   az webapp config appsettings set --resource-group myResourceGroup --name myDataCatalog --settings FLASK_ENV=production
   ```

3. **Deploy Application**
   ```bash
   az webapp deployment source config-zip --resource-group myResourceGroup --name myDataCatalog --src data-catalog.zip
   ```

### Docker Deployment

1. **Build Image**
   ```bash
   docker build -t data-catalog .
   ```

2. **Run Container**
   ```bash
   docker run -p 5000:5000 --env-file .env data-catalog
   ```

## Testing

### Run Tests
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend

# Run specific test file
pytest tests/test_assets.py
```

### Test Categories
- **Unit Tests**: Model and utility function tests
- **Integration Tests**: API endpoint tests
- **Authentication Tests**: MSAL integration tests

## Security Considerations

### Authentication & Authorization
- Microsoft Entra ID integration for enterprise SSO
- Role-based access control (RBAC)
- Session management with secure cookies
- CSRF protection for state parameters

### Data Protection
- Automatic PII detection and flagging
- Access level controls (Public, Internal, Restricted, Confidential)
- Audit trail for all data changes
- Secure file upload handling

### Production Security
- HTTPS enforcement
- Secure session configuration
- Environment variable protection
- SQL injection prevention with SQLAlchemy ORM

## Troubleshooting

### Common Issues

1. **Authentication Failed**
   - Check Entra ID configuration
   - Verify redirect URIs match
   - Ensure client secret is correct

2. **Database Connection Error**
   - Verify database credentials
   - Check network connectivity
   - Ensure ODBC driver is installed

3. **File Upload Issues**
   - Check file size limits
   - Verify supported file formats
   - Ensure upload directory permissions

### Logging
- Application logs available in console output
- Configure log level with `FLASK_ENV`
- Check Azure App Service logs for deployment issues

## Contributing

1. Fork the repository
2. Create feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'Add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open Pull Request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Support

For support and questions:
- Create an issue in the repository
- Contact the development team
- Check the documentation in the `docs/` directory