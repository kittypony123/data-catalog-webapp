from flask import Blueprint, request, jsonify, current_app
from backend.models import db, User, Role, UserFavorite
from backend.utils.auth import token_required, admin_required, get_current_user_id, get_current_user
from datetime import datetime

users_bp = Blueprint('users', __name__)


@users_bp.route('/', methods=['GET'])
@admin_required
def get_users():
    """Get all users (admin only)"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    role_id = request.args.get('role_id', type=int)
    search = request.args.get('search', '').strip()
    
    query = User.query
    
    # Filter by role
    if role_id:
        query = query.filter_by(role_id=role_id)
    
    # Search by name or email
    if search:
        query = query.filter(
            db.or_(
                User.display_name.ilike(f'%{search}%'),
                User.email.ilike(f'%{search}%')
            )
        )
    
    # Order by display name
    query = query.order_by(User.display_name)
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    users = [user.to_dict(include_sensitive=True) for user in pagination.items]
    
    return jsonify({
        'users': users,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@users_bp.route('/<user_id>', methods=['GET'])
@token_required
def get_user(user_id):
    """Get specific user"""
    current_user = get_current_user()
    
    # Users can view their own profile, admins can view any
    if current_user.user_id != user_id and current_user.role.role_name != 'Admin':
        return jsonify({'error': 'Access denied'}), 403
    
    user = User.query.get_or_404(user_id)
    include_sensitive = (current_user.user_id == user_id or current_user.role.role_name == 'Admin')
    
    return jsonify({
        'user': user.to_dict(include_sensitive=include_sensitive)
    })


@users_bp.route('/<user_id>/role', methods=['PUT'])
@admin_required
def update_user_role(user_id):
    """Update user's role (admin only)"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if not data or 'role_id' not in data:
        return jsonify({'error': 'Role ID is required'}), 400
    
    role = Role.query.get(data['role_id'])
    if not role:
        return jsonify({'error': 'Invalid role'}), 400
    
    try:
        old_role = user.role.role_name if user.role else None
        user.role_id = data['role_id']
        db.session.commit()
        
        current_app.logger.info(f"User role updated: {user.display_name} from {old_role} to {role.role_name}")
        
        return jsonify({
            'message': 'User role updated successfully',
            'user': user.to_dict(include_sensitive=True)
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update user role: {e}")
        return jsonify({'error': 'Failed to update user role'}), 500


@users_bp.route('/<user_id>/status', methods=['PUT'])
@admin_required
def update_user_status(user_id):
    """Update user's active status (admin only)"""
    user = User.query.get_or_404(user_id)
    data = request.get_json()
    
    if not data or 'is_active' not in data:
        return jsonify({'error': 'Active status is required'}), 400
    
    try:
        user.is_active = bool(data['is_active'])
        db.session.commit()
        
        status = 'activated' if user.is_active else 'deactivated'
        current_app.logger.info(f"User {status}: {user.display_name}")
        
        return jsonify({
            'message': f'User {status} successfully',
            'user': user.to_dict(include_sensitive=True)
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update user status: {e}")
        return jsonify({'error': 'Failed to update user status'}), 500


@users_bp.route('/roles', methods=['GET'])
@token_required
def get_roles():
    """Get all available roles"""
    roles = Role.query.order_by(Role.role_name).all()
    
    return jsonify({
        'roles': [role.to_dict() for role in roles]
    })


@users_bp.route('/me/favorites', methods=['GET'])
@token_required
def get_my_favorites():
    """Get current user's favorite assets"""
    user_id = get_current_user_id()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    pagination = UserFavorite.query.filter_by(user_id=user_id)\
        .order_by(UserFavorite.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    favorites = [fav.to_dict() for fav in pagination.items]
    
    return jsonify({
        'favorites': favorites,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@users_bp.route('/me/favorites/<int:asset_id>', methods=['POST'])
@token_required
def add_favorite(asset_id):
    """Add asset to favorites"""
    user_id = get_current_user_id()
    data = request.get_json() or {}
    
    try:
        favorite = UserFavorite.add_favorite(
            user_id=user_id,
            asset_id=asset_id,
            notes=data.get('notes')
        )
        
        if not favorite:
            return jsonify({'error': 'Asset not found'}), 404
        
        db.session.commit()
        
        return jsonify({
            'message': 'Asset added to favorites',
            'favorite': favorite.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to add favorite: {e}")
        return jsonify({'error': 'Failed to add favorite'}), 500


@users_bp.route('/me/favorites/<int:asset_id>', methods=['DELETE'])
@token_required
def remove_favorite(asset_id):
    """Remove asset from favorites"""
    user_id = get_current_user_id()
    
    try:
        removed = UserFavorite.remove_favorite(user_id=user_id, asset_id=asset_id)
        
        if not removed:
            return jsonify({'error': 'Favorite not found'}), 404
        
        db.session.commit()
        
        return jsonify({'message': 'Asset removed from favorites'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to remove favorite: {e}")
        return jsonify({'error': 'Failed to remove favorite'}), 500


@users_bp.route('/me/favorites/<int:asset_id>', methods=['PUT'])
@token_required
def update_favorite_notes(asset_id):
    """Update notes for a favorite asset"""
    user_id = get_current_user_id()
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    favorite = UserFavorite.query.filter_by(user_id=user_id, asset_id=asset_id).first()
    if not favorite:
        return jsonify({'error': 'Favorite not found'}), 404
    
    try:
        favorite.notes = data.get('notes')
        db.session.commit()
        
        return jsonify({
            'message': 'Favorite notes updated',
            'favorite': favorite.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update favorite notes: {e}")
        return jsonify({'error': 'Failed to update favorite notes'}), 500


@users_bp.route('/me/profile', methods=['PUT'])
@token_required
def update_my_profile():
    """Update current user's profile"""
    user = get_current_user()
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    try:
        # Users can only update their display name
        if 'display_name' in data:
            user.display_name = data['display_name'].strip()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Profile updated successfully',
            'user': user.to_dict(include_sensitive=True)
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update profile: {e}")
        return jsonify({'error': 'Failed to update profile'}), 500


@users_bp.route('/stats', methods=['GET'])
@admin_required
def get_user_stats():
    """Get user statistics (admin only)"""
    total_users = User.query.count()
    active_users = User.query.filter_by(is_active=True).count()
    
    # Count by role
    role_stats = []
    roles = Role.query.all()
    for role in roles:
        count = User.query.filter_by(role_id=role.role_id, is_active=True).count()
        role_stats.append({
            'role': role.to_dict(),
            'user_count': count
        })
    
    # Recent activity
    recent_logins = User.query.filter(User.last_login.isnot(None))\
        .order_by(User.last_login.desc()).limit(10).all()
    
    return jsonify({
        'total_users': total_users,
        'active_users': active_users,
        'inactive_users': total_users - active_users,
        'role_distribution': role_stats,
        'recent_logins': [
            {
                'user': user.to_dict(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            } for user in recent_logins
        ]
    })