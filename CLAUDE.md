# CLAUDE.md

This file provides guidance to Claude Code when working with the Data Catalog Web Application.

## Repository Overview

This is a comprehensive data catalog and governance platform built with Flask (Python) and React, designed for UK Housing Association data management with enterprise authentication and approval workflows.

## Project Structure

```
data-catalog-webapp/
├── backend/              # Flask application
│   ├── app/             # Application factory
│   ├── config/          # Configuration settings
│   ├── models/          # SQLAlchemy database models
│   ├── routes/          # API route handlers
│   └── utils/           # Utility functions and helpers
├── frontend/            # React frontend
│   ├── public/          # Static files and main HTML
│   └── src/             # React source (placeholder for future)
├── tests/               # Test files
├── deployment/          # Docker and deployment configs
├── docs/                # Documentation
├── app.py              # Main application entry point
└── requirements.txt    # Python dependencies
```

## Development Commands

### Setup and Installation
```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Setup environment
cp .env.example .env
# Edit .env with your configuration

# Initialize database
python -c "from backend.app import create_app; app = create_app(); app.app_context().push(); from backend.models import db; db.create_all()"
```

### Running the Application
```bash
# Development server
python app.py

# Production with Gunicorn
gunicorn --bind 0.0.0.0:5000 --workers 4 app:app
```

### Testing
```bash
# Run all tests
pytest

# Run with coverage
pytest --cov=backend

# Run specific test
pytest tests/test_assets.py -v
```

### Database Management
```bash
# Create all tables
python -c "from backend.app import create_app; from backend.models import db; app = create_app(); app.app_context().push(); db.create_all()"

# Drop all tables (DANGER!)
python -c "from backend.app import create_app; from backend.models import db; app = create_app(); app.app_context().push(); db.drop_all()"
```

### Code Quality
```bash
# Format code
black backend/ tests/

# Lint code
flake8 backend/ tests/

# Security check
bandit -r backend/
safety check
```

## Architecture Overview

### Backend Architecture
- **Flask Application Factory**: Modular app creation in `backend/app/__init__.py`
- **Blueprint-based Routing**: API routes organized by domain in `backend/routes/`
- **SQLAlchemy Models**: Database models with relationships in `backend/models/`
- **MSAL Authentication**: Microsoft Entra ID integration in `backend/routes/auth.py`
- **Role-based Authorization**: Decorators in `backend/utils/auth.py`

### Database Models
- **User/Role**: Authentication and authorization
- **DataAsset**: Core asset metadata with JSON flexibility
- **Category/ReportType**: Asset classification
- **AssetRelationship**: Data lineage (internal and external)
- **Team/TeamMember**: Collaboration features
- **UserFavorite**: Personal bookmarks
- **ApprovalHistory**: Complete audit trail

### Key Features Implemented
1. **Enterprise Authentication**: Microsoft Entra ID with MSAL
2. **Role-based Access Control**: Admin, Data Owner, Contributor roles
3. **Data Asset Management**: CRUD operations with approval workflow
4. **Search and Discovery**: Advanced search with filtering
5. **Data Lineage**: Relationship tracking between assets
6. **Excel Import**: Automated metadata extraction
7. **Team Collaboration**: Shared workspaces and favorites
8. **Audit Trail**: Complete history of all changes

## API Structure

### Base URL
- Development: `http://localhost:5000/api/v1`
- All endpoints are versioned with `/api/v1` prefix

### Authentication Flow
1. `GET /auth/login` - Redirects to Microsoft login
2. `GET /auth/callback` - Handles OAuth callback
3. `GET /auth/me` - Returns current user info
4. `POST /auth/logout` - Clears session

### Core Endpoints
- **Assets**: `/assets/*` - Data asset management
- **Categories**: `/categories/*` - Category management
- **Report Types**: `/report-types/*` - Report type templates
- **Search**: `/search/*` - Search and discovery
- **Teams**: `/teams/*` - Team collaboration
- **Users**: `/users/*` - User management
- **Upload**: `/upload/*` - File upload and analysis

## Frontend Implementation

### Current Frontend
- Single-page React application in `frontend/public/index.html`
- Modern UI with Lucide icons and CSS Grid/Flexbox
- Responsive design with mobile support
- Integration with backend API

### Key Components
- **Authentication**: Microsoft login integration
- **Dashboard**: Overview with statistics
- **Navigation**: Role-based sidebar navigation
- **Asset Management**: Create, view, edit assets
- **Search Interface**: Advanced search with filters

## Configuration

### Environment Variables
```bash
# Flask
FLASK_ENV=development
FLASK_SECRET_KEY=your-secret-key

# Database
DB_USERNAME=username
DB_PASSWORD=password
DB_HOST=server.database.windows.net
DB_NAME=database_name

# Microsoft Entra ID
AZURE_TENANT_ID=tenant-id
AZURE_CLIENT_ID=client-id
AZURE_CLIENT_SECRET=client-secret

# Application
APP_BASE_URL=http://localhost:5000
API_VERSION=v1
```

### Database Configuration
- **Development**: SQLite fallback if SQL Server not configured
- **Production**: Microsoft Fabric SQL Analytics Endpoint
- **Connection**: Uses pyodbc with SQL Server ODBC driver

## Testing Strategy

### Test Structure
```
tests/
├── conftest.py          # Test configuration and fixtures
├── test_auth.py         # Authentication tests
├── test_models.py       # Database model tests
├── test_assets.py       # Asset management tests
├── test_search.py       # Search functionality tests
└── test_api.py          # API integration tests
```

### Test Categories
- **Unit Tests**: Model validation, utility functions
- **Integration Tests**: API endpoint testing
- **Authentication Tests**: MSAL integration
- **Database Tests**: Model relationships and queries

## Deployment

### Docker Deployment
```bash
# Build image
docker build -f deployment/Dockerfile -t data-catalog .

# Run with docker-compose
cd deployment
docker-compose up -d
```

### Azure App Service
- Uses Azure DevOps pipeline in `deployment/azure-pipelines.yml`
- Separate environments for development and production
- Automatic deployment on branch pushes

## Security Considerations

### Authentication & Authorization
- Microsoft Entra ID for enterprise SSO
- Session-based authentication with secure cookies
- Role-based access control with decorators
- CSRF protection for sensitive operations

### Data Protection
- Automatic PII detection in uploaded files
- Access level controls (Public, Internal, Restricted, Confidential)
- Audit trail for all data modifications
- Input validation and SQL injection prevention

## Common Development Tasks

### Adding New API Endpoint
1. Create route handler in appropriate `backend/routes/*.py` file
2. Add authentication/authorization decorators
3. Update tests in corresponding test file
4. Document in API section above

### Adding New Database Model
1. Create model in `backend/models/*.py`
2. Import in `backend/models/__init__.py`
3. Add relationships to related models
4. Create/update database with new schema

### Adding New Frontend View
1. Add component in frontend/public/index.html
2. Update navigation in Sidebar component
3. Add route in ViewRenderer component
4. Integrate with backend API

### Debugging Common Issues
1. **Database Connection**: Check environment variables and ODBC driver
2. **Authentication**: Verify Entra ID configuration and redirect URIs
3. **File Upload**: Check file permissions and supported formats
4. **API Errors**: Check Flask logs and network requests in browser

## Code Style and Conventions

### Python (Backend)
- Follow PEP 8 style guidelines
- Use Black for code formatting
- Use type hints where appropriate
- Document functions with docstrings
- Use SQLAlchemy ORM, avoid raw SQL

### JavaScript (Frontend)
- Use modern React hooks and functional components
- Follow camelCase naming convention
- Use async/await for API calls
- Keep components focused and reusable

### Database
- Use snake_case for table and column names
- Include created_at/updated_at timestamps
- Use meaningful foreign key names
- Add indexes for frequently queried columns

## Performance Considerations

### Database
- Indexes on commonly searched fields
- Pagination for large result sets
- Efficient relationship loading
- Connection pooling in production

### API
- Request/response size optimization
- Caching for frequent queries
- Rate limiting for public endpoints
- Asynchronous processing for heavy operations

### Frontend
- Lazy loading for large datasets
- Debounced search inputs
- Optimistic UI updates
- Responsive image loading

## Monitoring and Logging

### Application Logging
- Structured logging with Python logging module
- Different log levels for development vs production
- Request/response logging for API endpoints
- Error tracking with stack traces

### Health Checks
- `/health` endpoint for application status
- Database connectivity checks
- Authentication service checks
- File system access checks

## Future Enhancements

### Planned Features
1. **Advanced Lineage Visualization**: Interactive graph-based lineage
2. **Data Quality Dashboard**: Comprehensive quality metrics
3. **Automated Discovery**: API-based asset discovery
4. **Notification System**: Email/webhook notifications
5. **Advanced Analytics**: Usage patterns and trends
6. **Compliance Reporting**: Automated compliance dashboards
7. **API Integration Framework**: Connect external data systems
8. **Mobile App**: Native mobile application

### Technical Improvements
1. **Caching Layer**: Redis for performance optimization
2. **Async Processing**: Celery for background tasks
3. **Full-text Search**: Elasticsearch integration
4. **Real-time Updates**: WebSocket support
5. **Microservices**: Break into smaller services
6. **GraphQL API**: Alternative to REST API

This documentation should help with development, deployment, and maintenance of the Data Catalog Web Application.