from functools import wraps
from flask import session, jsonify, current_app, request
from backend.models import User
import jwt
from datetime import datetime, timedelta


def token_required(f):
    """Decorator to ensure user is authenticated"""
    @wraps(f)
    def decorated(*args, **kwargs):
        # Check if user is in session (MSAL authentication)
        if 'user' not in session:
            return jsonify({'error': 'Authentication required'}), 401
        
        # Optionally validate token expiry
        user_claims = session.get('user')
        if not user_claims or not user_claims.get('oid'):
            return jsonify({'error': 'Invalid authentication token'}), 401
        
        # Update last login if user exists in database
        user = User.query.filter_by(user_id=user_claims.get('oid')).first()
        if user:
            user.last_login = datetime.utcnow()
        
        return f(*args, **kwargs)
    return decorated


def admin_required(f):
    """Decorator to ensure user has admin role"""
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        user_claims = session.get('user')
        user = User.query.filter_by(user_id=user_claims.get('oid')).first()
        
        if not user or not user.role or user.role.role_name != 'Admin':
            return jsonify({'error': 'Admin access required'}), 403
        
        return f(*args, **kwargs)
    return decorated


def permission_required(permission):
    """Decorator to check specific permissions"""
    def decorator(f):
        @wraps(f)
        @token_required
        def decorated(*args, **kwargs):
            user_claims = session.get('user')
            user = User.query.filter_by(user_id=user_claims.get('oid')).first()
            
            if not user or not user.has_permission(permission):
                return jsonify({'error': f'Permission "{permission}" required'}), 403
            
            return f(*args, **kwargs)
        return decorated
    return decorator


def asset_owner_or_admin_required(f):
    """Decorator to ensure user owns the asset or is admin"""
    @wraps(f)
    @token_required
    def decorated(*args, **kwargs):
        user_claims = session.get('user')
        user = User.query.filter_by(user_id=user_claims.get('oid')).first()
        
        if not user:
            return jsonify({'error': 'User not found'}), 404
        
        # Admin can access anything
        if user.role and user.role.role_name == 'Admin':
            return f(*args, **kwargs)
        
        # Check if user owns the asset (asset_id should be in URL parameters)
        asset_id = kwargs.get('asset_id') or request.view_args.get('asset_id')
        if asset_id:
            from backend.models.data_asset import DataAsset
            asset = DataAsset.query.get(asset_id)
            if asset and asset.is_editable_by(user):
                return f(*args, **kwargs)
        
        return jsonify({'error': 'Asset owner or admin access required'}), 403
    return decorated


def get_current_user():
    """Get current authenticated user from session"""
    if 'user' not in session:
        return None
    
    user_claims = session.get('user')
    if not user_claims or not user_claims.get('oid'):
        return None
    
    return User.query.filter_by(user_id=user_claims.get('oid')).first()


def get_current_user_id():
    """Get current user ID from session"""
    user_claims = session.get('user')
    return user_claims.get('oid') if user_claims else None


def validate_user_in_database(user_claims):
    """Ensure user exists in database, create if necessary"""
    user_id = user_claims.get('oid')
    email = user_claims.get('email') or user_claims.get('preferred_username')
    display_name = user_claims.get('name') or user_claims.get('given_name', '') + ' ' + user_claims.get('family_name', '')
    
    user = User.query.filter_by(user_id=user_id).first()
    
    if not user:
        # Create new user with default role (Contributor)
        from backend.models.user import Role
        from backend.models import db
        
        default_role = Role.query.filter_by(role_name='Contributor').first()
        if not default_role:
            # Create default role if it doesn't exist
            default_role = Role(role_name='Contributor', description='Can create and edit data assets')
            db.session.add(default_role)
            db.session.commit()
        
        user = User(
            user_id=user_id,
            email=email,
            display_name=display_name.strip(),
            role_id=default_role.role_id
        )
        db.session.add(user)
        db.session.commit()
    
    # Update last login
    user.last_login = datetime.utcnow()
    db.session.commit()
    
    return user


def generate_api_key(user_id, expires_hours=24):
    """Generate API key for programmatic access"""
    payload = {
        'user_id': user_id,
        'exp': datetime.utcnow() + timedelta(hours=expires_hours),
        'iat': datetime.utcnow()
    }
    
    return jwt.encode(payload, current_app.config['SECRET_KEY'], algorithm='HS256')


def validate_api_key(token):
    """Validate API key"""
    try:
        payload = jwt.decode(token, current_app.config['SECRET_KEY'], algorithms=['HS256'])
        user_id = payload.get('user_id')
        user = User.query.filter_by(user_id=user_id).first()
        return user
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None