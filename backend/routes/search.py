from flask import Blueprint, request, jsonify
from backend.models import db, DataAsset, Category, ReportType, User
from backend.utils.auth import token_required
from sqlalchemy import or_, and_, func

search_bp = Blueprint('search', __name__)


@search_bp.route('/', methods=['GET'])
@token_required
def search_assets():
    """Global search across data assets"""
    query_text = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Filters
    category_id = request.args.get('category_id', type=int)
    report_type_id = request.args.get('report_type_id', type=int)
    approval_status = request.args.get('status', 'Approved')
    owner_id = request.args.get('owner_id')
    is_public = request.args.get('is_public')
    is_sensitive = request.args.get('is_sensitive')
    
    # Start with base query for approved assets
    query = DataAsset.query
    
    # Text search across multiple fields
    if query_text:
        search_terms = query_text.split()
        search_conditions = []
        
        for term in search_terms:
            term_pattern = f'%{term}%'
            term_conditions = or_(
                DataAsset.asset_name.ilike(term_pattern),
                DataAsset.description.ilike(term_pattern),
                DataAsset.source_system.ilike(term_pattern),
                DataAsset.source_location.ilike(term_pattern),
                func.json_unquote(func.json_extract(DataAsset.tags, '$[*]')).ilike(term_pattern)
            )
            search_conditions.append(term_conditions)
        
        # All search terms must match (AND)
        if search_conditions:
            query = query.filter(and_(*search_conditions))
    
    # Apply filters
    if approval_status:
        query = query.filter(DataAsset.approval_status == approval_status)
    
    if category_id:
        query = query.filter(DataAsset.category_id == category_id)
    
    if report_type_id:
        query = query.filter(DataAsset.report_type_id == report_type_id)
    
    if owner_id:
        query = query.filter(DataAsset.owner_user_id == owner_id)
    
    if is_public is not None:
        query = query.filter(DataAsset.is_public == (is_public.lower() == 'true'))
    
    if is_sensitive is not None:
        query = query.filter(DataAsset.is_sensitive == (is_sensitive.lower() == 'true'))
    
    # Order by relevance (exact name matches first, then by created date)
    if query_text:
        query = query.order_by(
            DataAsset.asset_name.ilike(f'%{query_text}%').desc(),
            DataAsset.created_at.desc()
        )
    else:
        query = query.order_by(DataAsset.created_at.desc())
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format results
    results = []
    for asset in pagination.items:
        asset_dict = asset.to_dict()
        
        # Add search relevance information
        if query_text:
            asset_dict['search_score'] = calculate_search_score(asset, query_text)
        
        results.append(asset_dict)
    
    return jsonify({
        'results': results,
        'query': query_text,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        },
        'filters_applied': {
            'category_id': category_id,
            'report_type_id': report_type_id,
            'approval_status': approval_status,
            'owner_id': owner_id,
            'is_public': is_public,
            'is_sensitive': is_sensitive
        }
    })


@search_bp.route('/suggestions', methods=['GET'])
@token_required
def get_search_suggestions():
    """Get search suggestions based on query"""
    query_text = request.args.get('q', '').strip()
    limit = min(request.args.get('limit', 10, type=int), 20)
    
    if not query_text or len(query_text) < 2:
        return jsonify({'suggestions': []})
    
    suggestions = []
    
    # Asset name suggestions
    asset_suggestions = DataAsset.query.filter(
        and_(
            DataAsset.approval_status == 'Approved',
            DataAsset.asset_name.ilike(f'%{query_text}%')
        )
    ).limit(limit).all()
    
    for asset in asset_suggestions:
        suggestions.append({
            'type': 'asset',
            'text': asset.asset_name,
            'category': 'Data Asset',
            'asset_id': asset.asset_id
        })
    
    # Category suggestions
    if len(suggestions) < limit:
        category_suggestions = Category.query.filter(
            and_(
                Category.is_active == True,
                Category.category_name.ilike(f'%{query_text}%')
            )
        ).limit(limit - len(suggestions)).all()
        
        for category in category_suggestions:
            suggestions.append({
                'type': 'category',
                'text': category.category_name,
                'category': 'Category',
                'category_id': category.category_id
            })
    
    # Report type suggestions
    if len(suggestions) < limit:
        report_type_suggestions = ReportType.query.filter(
            and_(
                ReportType.is_active == True,
                ReportType.type_name.ilike(f'%{query_text}%')
            )
        ).limit(limit - len(suggestions)).all()
        
        for rt in report_type_suggestions:
            suggestions.append({
                'type': 'report_type',
                'text': rt.type_name,
                'category': 'Report Type',
                'report_type_id': rt.report_type_id
            })
    
    return jsonify({
        'suggestions': suggestions,
        'query': query_text
    })


@search_bp.route('/filters', methods=['GET'])
@token_required
def get_search_filters():
    """Get available filter options for search"""
    # Get active categories with asset counts
    categories = db.session.query(
        Category,
        func.count(DataAsset.asset_id).label('asset_count')
    ).outerjoin(
        DataAsset, and_(
            DataAsset.category_id == Category.category_id,
            DataAsset.approval_status == 'Approved'
        )
    ).filter(
        Category.is_active == True
    ).group_by(Category.category_id).all()
    
    category_filters = [
        {
            'id': cat.category_id,
            'name': cat.category_name,
            'asset_count': count
        }
        for cat, count in categories
    ]
    
    # Get active report types with asset counts
    report_types = db.session.query(
        ReportType,
        func.count(DataAsset.asset_id).label('asset_count')
    ).outerjoin(
        DataAsset, and_(
            DataAsset.report_type_id == ReportType.report_type_id,
            DataAsset.approval_status == 'Approved'
        )
    ).filter(
        ReportType.is_active == True
    ).group_by(ReportType.report_type_id).all()
    
    report_type_filters = [
        {
            'id': rt.report_type_id,
            'name': rt.type_name,
            'asset_count': count
        }
        for rt, count in report_types
    ]
    
    # Get users who own assets
    owners = db.session.query(
        User,
        func.count(DataAsset.asset_id).label('asset_count')
    ).join(
        DataAsset, DataAsset.owner_user_id == User.user_id
    ).filter(
        and_(
            DataAsset.approval_status == 'Approved',
            User.is_active == True
        )
    ).group_by(User.user_id).all()
    
    owner_filters = [
        {
            'id': user.user_id,
            'name': user.display_name,
            'asset_count': count
        }
        for user, count in owners
    ]
    
    # Get approval status counts
    status_counts = db.session.query(
        DataAsset.approval_status,
        func.count(DataAsset.asset_id).label('count')
    ).group_by(DataAsset.approval_status).all()
    
    status_filters = [
        {
            'status': status,
            'count': count
        }
        for status, count in status_counts
    ]
    
    return jsonify({
        'categories': category_filters,
        'report_types': report_type_filters,
        'owners': owner_filters,
        'statuses': status_filters
    })


def calculate_search_score(asset, query_text):
    """Calculate relevance score for search results"""
    score = 0
    query_lower = query_text.lower()
    
    # Exact name match gets highest score
    if asset.asset_name.lower() == query_lower:
        score += 100
    elif query_lower in asset.asset_name.lower():
        score += 50
    
    # Description match
    if asset.description and query_lower in asset.description.lower():
        score += 20
    
    # Source system match
    if asset.source_system and query_lower in asset.source_system.lower():
        score += 15
    
    # Tags match
    if asset.tags:
        for tag in asset.tags:
            if query_lower in tag.lower():
                score += 10
    
    # Category/report type name match
    if asset.category and query_lower in asset.category.category_name.lower():
        score += 10
    
    if asset.report_type and query_lower in asset.report_type.type_name.lower():
        score += 10
    
    # Recent assets get slight boost
    from datetime import datetime, timedelta
    if asset.created_at and asset.created_at > datetime.utcnow() - timedelta(days=30):
        score += 5
    
    return score


@search_bp.route('/saved', methods=['GET'])
@token_required
def get_saved_searches():
    """Get user's saved searches (placeholder for future implementation)"""
    # This would require a SavedSearch model
    return jsonify({
        'saved_searches': [],
        'message': 'Saved searches feature not yet implemented'
    })


@search_bp.route('/recent', methods=['GET'])
@token_required
def get_recent_searches():
    """Get user's recent search queries (placeholder for future implementation)"""
    # This would require tracking search history
    return jsonify({
        'recent_searches': [],
        'message': 'Recent searches feature not yet implemented'
    })