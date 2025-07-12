from flask import Blueprint, request, jsonify, session, redirect, url_for, current_app
import msal
import uuid
from backend.utils.auth import validate_user_in_database, get_current_user

auth_bp = Blueprint('auth', __name__)


def get_msal_app():
    """Create MSAL confidential client application"""
    if not all([
        current_app.config.get('AZURE_CLIENT_ID'),
        current_app.config.get('AZURE_TENANT_ID'),
        current_app.config.get('AZURE_CLIENT_SECRET')
    ]):
        return None
    
    authority = f"https://login.microsoftonline.com/{current_app.config['AZURE_TENANT_ID']}"
    
    return msal.ConfidentialClientApplication(
        current_app.config['AZURE_CLIENT_ID'],
        authority=authority,
        client_credential=current_app.config['AZURE_CLIENT_SECRET'],
        token_cache=get_token_cache()
    )


def get_token_cache():
    """Get token cache from session"""
    cache = msal.SerializableTokenCache()
    if session.get('token_cache'):
        cache.deserialize(session['token_cache'])
    return cache


def save_token_cache(cache):
    """Save token cache to session"""
    if cache.has_state_changed:
        session['token_cache'] = cache.serialize()


@auth_bp.route('/login', methods=['GET'])
def login():
    """Initiate OAuth login flow"""
    msal_app = get_msal_app()
    if not msal_app:
        return jsonify({'error': 'Authentication not configured'}), 500
    
    # Generate state for CSRF protection
    session['auth_state'] = str(uuid.uuid4())
    
    # Build authorization URL
    auth_url = msal_app.get_authorization_request_url(
        scopes=['User.Read'],
        state=session['auth_state'],
        redirect_uri=url_for('auth.callback', _external=True)
    )
    
    return jsonify({'auth_url': auth_url})


@auth_bp.route('/callback', methods=['GET'])
def callback():
    """Handle OAuth callback"""
    # Validate state parameter
    if request.args.get('state') != session.get('auth_state'):
        return jsonify({'error': 'Invalid state parameter'}), 400
    
    # Check for authorization code
    if 'code' not in request.args:
        return jsonify({'error': 'Authorization code not provided'}), 400
    
    msal_app = get_msal_app()
    if not msal_app:
        return jsonify({'error': 'Authentication not configured'}), 500
    
    # Exchange authorization code for tokens
    result = msal_app.acquire_token_by_authorization_code(
        request.args['code'],
        scopes=['User.Read'],
        redirect_uri=url_for('auth.callback', _external=True)
    )
    
    if 'error' in result:
        current_app.logger.error(f"Token acquisition failed: {result}")
        return jsonify({
            'error': 'Authentication failed',
            'details': result.get('error_description')
        }), 400
    
    # Save user information to session
    user_claims = result.get('id_token_claims', {})
    session['user'] = user_claims
    
    # Save token cache
    save_token_cache(msal_app.token_cache)
    
    # Ensure user exists in database
    try:
        user = validate_user_in_database(user_claims)
        current_app.logger.info(f"User authenticated: {user.display_name} ({user.email})")
    except Exception as e:
        current_app.logger.error(f"Failed to create/update user: {e}")
        return jsonify({'error': 'Failed to process user information'}), 500
    
    # Redirect to frontend
    frontend_url = current_app.config.get('APP_BASE_URL', 'http://localhost:3000')
    return redirect(f"{frontend_url}?auth=success")


@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout user"""
    # Clear session
    session.clear()
    
    # Build logout URL
    if current_app.config.get('AZURE_TENANT_ID'):
        authority = f"https://login.microsoftonline.com/{current_app.config['AZURE_TENANT_ID']}"
        logout_url = f"{authority}/oauth2/v2.0/logout"
        return jsonify({'logout_url': logout_url})
    
    return jsonify({'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
def get_current_user_info():
    """Get current user information"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    user = get_current_user()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    return jsonify({
        'user': user.to_dict(include_sensitive=True),
        'permissions': {
            'can_create': user.has_permission('create'),
            'can_update': user.has_permission('update'),
            'can_delete': user.has_permission('delete'),
            'can_approve': user.has_permission('approve'),
            'can_manage_users': user.has_permission('manage_users')
        }
    })


@auth_bp.route('/session', methods=['GET'])
def check_session():
    """Check if user has valid session"""
    if 'user' not in session:
        return jsonify({'authenticated': False}), 200
    
    user_claims = session.get('user')
    user = get_current_user()
    
    if not user:
        # User exists in session but not in database
        session.clear()
        return jsonify({'authenticated': False}), 200
    
    return jsonify({
        'authenticated': True,
        'user': user.to_dict(),
        'session_expires': None  # Could implement session expiry
    })


@auth_bp.route('/refresh', methods=['POST'])
def refresh_token():
    """Refresh authentication token"""
    if 'user' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    msal_app = get_msal_app()
    if not msal_app:
        return jsonify({'error': 'Authentication not configured'}), 500
    
    # Try to get token silently
    accounts = msal_app.get_accounts()
    if accounts:
        result = msal_app.acquire_token_silent(
            scopes=['User.Read'],
            account=accounts[0]
        )
        
        if result and 'access_token' in result:
            save_token_cache(msal_app.token_cache)
            return jsonify({'message': 'Token refreshed successfully'})
    
    return jsonify({'error': 'Failed to refresh token'}), 400