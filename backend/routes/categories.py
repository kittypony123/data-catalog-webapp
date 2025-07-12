from flask import Blueprint, request, jsonify, current_app
from backend.models import db, Category
from backend.utils.auth import token_required, admin_required
from datetime import datetime

categories_bp = Blueprint('categories', __name__)


@categories_bp.route('/', methods=['POST'])
@admin_required
def create_category():
    """Create a new category"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    if not data.get('category_name'):
        return jsonify({'error': 'Category name is required'}), 400

    # Check for duplicate names
    existing = Category.query.filter_by(category_name=data['category_name']).first()
    if existing:
        return jsonify({'error': 'Category with this name already exists'}), 409

    try:
        category = Category(
            category_name=data['category_name'],
            description=data.get('description'),
            color_code=data.get('color_code'),
            icon=data.get('icon'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(category)
        db.session.commit()
        
        current_app.logger.info(f"Category created: {category.category_name}")
        
        return jsonify({
            'message': 'Category created successfully',
            'category': category.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create category: {e}")
        return jsonify({'error': 'Failed to create category'}), 500


@categories_bp.route('/', methods=['GET'])
@token_required
def get_categories():
    """Get all categories"""
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    query = Category.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    
    categories = query.order_by(Category.category_name).all()
    
    return jsonify({
        'categories': [category.to_dict() for category in categories]
    })


@categories_bp.route('/<int:category_id>', methods=['GET'])
@token_required
def get_category(category_id):
    """Get specific category"""
    category = Category.query.get_or_404(category_id)
    
    return jsonify({
        'category': category.to_dict()
    })


@categories_bp.route('/<int:category_id>', methods=['PUT'])
@admin_required
def update_category(category_id):
    """Update an existing category"""
    category = Category.query.get_or_404(category_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Check for duplicate names (excluding current category)
        if 'category_name' in data and data['category_name'] != category.category_name:
            existing = Category.query.filter(
                Category.category_id != category_id,
                Category.category_name == data['category_name']
            ).first()
            
            if existing:
                return jsonify({'error': 'Category with this name already exists'}), 409
            
            category.category_name = data['category_name']
        
        # Update other fields
        updateable_fields = ['description', 'color_code', 'icon', 'is_active']
        for field in updateable_fields:
            if field in data:
                setattr(category, field, data[field])
        
        category.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Category updated successfully',
            'category': category.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update category {category_id}: {e}")
        return jsonify({'error': 'Failed to update category'}), 500


@categories_bp.route('/<int:category_id>', methods=['DELETE'])
@admin_required
def delete_category(category_id):
    """Delete a category (soft delete by marking inactive)"""
    category = Category.query.get_or_404(category_id)
    
    # Check if category is in use
    if category.data_assets.count() > 0:
        return jsonify({
            'error': 'Cannot delete category that is in use by data assets',
            'asset_count': category.data_assets.count()
        }), 400
    
    try:
        # Soft delete by marking as inactive
        category.is_active = False
        category.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Category deleted successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete category {category_id}: {e}")
        return jsonify({'error': 'Failed to delete category'}), 500


@categories_bp.route('/<int:category_id>/assets', methods=['GET'])
@token_required
def get_category_assets(category_id):
    """Get all assets in a specific category"""
    category = Category.query.get_or_404(category_id)
    
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status = request.args.get('status', 'Approved')
    
    # Query assets in this category
    query = category.data_assets
    if status:
        query = query.filter_by(approval_status=status)
    
    pagination = query.order_by(category.data_assets.model.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    assets = [asset.to_dict() for asset in pagination.items]
    
    return jsonify({
        'category': category.to_dict(),
        'assets': assets,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@categories_bp.route('/stats', methods=['GET'])
@token_required
def get_category_stats():
    """Get statistics for all categories"""
    categories = Category.query.filter_by(is_active=True).all()
    
    stats = []
    for category in categories:
        approved_count = category.data_assets.filter_by(approval_status='Approved').count()
        pending_count = category.data_assets.filter_by(approval_status='Pending').count()
        total_count = category.data_assets.count()
        
        stats.append({
            'category': category.to_dict(),
            'asset_counts': {
                'approved': approved_count,
                'pending': pending_count,
                'total': total_count
            }
        })
    
    return jsonify({
        'category_stats': stats,
        'total_categories': len(stats)
    })