from flask import Flask
from flask_migrate import Migrate
from flask_cors import CORS
from backend.models import db
from backend.config import config
import os


def create_app(config_name=None):
    """Application factory pattern"""
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'development')
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialize extensions
    db.init_app(app)
    migrate = Migrate(app, db)
    CORS(app, origins=app.config['CORS_ORIGINS'])
    
    # Create upload directory if it doesn't exist
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Register blueprints
    from backend.routes.auth import auth_bp
    from backend.routes.data_assets import assets_bp
    from backend.routes.categories import categories_bp
    from backend.routes.report_types import report_types_bp
    from backend.routes.users import users_bp
    from backend.routes.teams import teams_bp
    from backend.routes.search import search_bp
    from backend.routes.compliance import compliance_bp
    from backend.routes.business_glossary import business_glossary_bp
    from backend.routes.dashboard import dashboard_bp
    from backend.routes.field_compliance import field_compliance_bp
    from backend.routes.lineage import lineage_bp
    
    # API versioning
    api_prefix = f"/api/{app.config['API_VERSION']}"
    
    app.register_blueprint(auth_bp, url_prefix=f"{api_prefix}/auth")
    app.register_blueprint(assets_bp, url_prefix=f"{api_prefix}/assets")
    app.register_blueprint(categories_bp, url_prefix=f"{api_prefix}/categories")
    app.register_blueprint(report_types_bp, url_prefix=f"{api_prefix}/report-types")
    app.register_blueprint(users_bp, url_prefix=f"{api_prefix}/users")
    app.register_blueprint(teams_bp, url_prefix=f"{api_prefix}/teams")
    app.register_blueprint(search_bp, url_prefix=f"{api_prefix}/search")
    app.register_blueprint(compliance_bp, url_prefix=f"{api_prefix}/compliance")
    app.register_blueprint(business_glossary_bp, url_prefix=f"{api_prefix}/glossary")
    app.register_blueprint(dashboard_bp, url_prefix=f"{api_prefix}/dashboard")
    app.register_blueprint(field_compliance_bp, url_prefix=f"{api_prefix}/fields")
    app.register_blueprint(lineage_bp, url_prefix=f"{api_prefix}/lineage")
    
    # Health check endpoint
    @app.route('/health')
    def health_check():
        return {'status': 'healthy', 'version': app.config['API_VERSION']}, 200
    
    # Serve frontend in production
    if config_name == 'production':
        @app.route('/', defaults={'path': ''})
        @app.route('/<path:path>')
        def serve_frontend(path):
            """Serve React frontend in production"""
            from flask import send_from_directory
            frontend_dir = os.path.join(os.path.dirname(app.instance_path), 'frontend', 'build')
            
            if path != "" and os.path.exists(os.path.join(frontend_dir, path)):
                return send_from_directory(frontend_dir, path)
            else:
                return send_from_directory(frontend_dir, 'index.html')
    
    # Initialize database tables
    with app.app_context():
        db.create_all()
        
        # Create default roles if they don't exist
        from backend.models.user import Role
        default_roles = [
            {'role_name': 'Admin', 'description': 'Full system access and user management'},
            {'role_name': 'Data Owner', 'description': 'Can create, edit, and manage data assets'},
            {'role_name': 'Contributor', 'description': 'Can create and edit data assets'}
        ]
        
        for role_data in default_roles:
            if not Role.query.filter_by(role_name=role_data['role_name']).first():
                role = Role(**role_data)
                db.session.add(role)
        
        db.session.commit()
    
    return app