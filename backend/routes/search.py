from flask import Blueprint, request, jsonify
from backend.models import db, DataAsset, Category, ReportType, User
from backend.utils.auth import token_required
from sqlalchemy import or_, and_, func

search_bp = Blueprint('search', __name__)


@search_bp.route('/', methods=['GET'])
@token_required
def search_assets():
    """Enhanced global search with faceted filtering across data assets"""
    query_text = request.args.get('q', '').strip()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Enhanced filters
    category_ids = request.args.getlist('category_id')
    report_type_ids = request.args.getlist('report_type_id')
    approval_statuses = request.args.getlist('status')
    owner_ids = request.args.getlist('owner_id')
    is_public = request.args.get('is_public')
    is_sensitive = request.args.get('is_sensitive')
    access_levels = request.args.getlist('access_level')
    has_compliance = request.args.get('has_compliance')
    
    # Date range filters
    created_after = request.args.get('created_after')
    created_before = request.args.get('created_before')
    updated_after = request.args.get('updated_after')
    updated_before = request.args.get('updated_before')
    
    # Advanced filters
    tags = request.args.getlist('tag')
    source_systems = request.args.getlist('source_system')
    data_types = request.args.getlist('data_type')
    sort_by = request.args.get('sort_by', 'relevance')  # relevance, created_date, updated_date, name
    sort_order = request.args.get('sort_order', 'desc')  # asc, desc
    
    # Start with base query
    query = DataAsset.query
    
    # Enhanced text search with field weighting
    if query_text:
        search_terms = query_text.split()
        search_conditions = []
        
        for term in search_terms:
            term_pattern = f'%{term}%'
            term_conditions = or_(
                # Asset name gets highest weight
                DataAsset.asset_name.ilike(term_pattern),
                # Description gets medium weight
                DataAsset.description.ilike(term_pattern),
                # Source system and location
                DataAsset.source_system.ilike(term_pattern),
                DataAsset.source_location.ilike(term_pattern),
                # Business purpose
                DataAsset.business_purpose.ilike(term_pattern),
                # Tags search (enhanced JSON handling)
                func.json_unquote(func.json_extract(DataAsset.tags, '$[*]')).ilike(term_pattern),
                # Schema info search
                func.json_unquote(func.json_extract(DataAsset.schema_info, '$')).ilike(term_pattern)
            )
            search_conditions.append(term_conditions)
        
        # All search terms must match (AND)
        if search_conditions:
            query = query.filter(and_(*search_conditions))
    
    # Apply enhanced filters
    if approval_statuses:
        query = query.filter(DataAsset.approval_status.in_(approval_statuses))
    elif not query_text:  # Default to approved if no specific search
        query = query.filter(DataAsset.approval_status == 'Approved')
    
    if category_ids:
        query = query.filter(DataAsset.category_id.in_([int(c) for c in category_ids]))
    
    if report_type_ids:
        query = query.filter(DataAsset.report_type_id.in_([int(r) for r in report_type_ids]))
    
    if owner_ids:
        query = query.filter(DataAsset.owner_user_id.in_(owner_ids))
    
    if is_public is not None:
        query = query.filter(DataAsset.is_public == (is_public.lower() == 'true'))
    
    if is_sensitive is not None:
        query = query.filter(DataAsset.is_sensitive == (is_sensitive.lower() == 'true'))
    
    if access_levels:
        query = query.filter(DataAsset.access_level.in_(access_levels))
    
    # Date range filters
    if created_after:
        from datetime import datetime
        query = query.filter(DataAsset.created_at >= datetime.fromisoformat(created_after))
    if created_before:
        from datetime import datetime
        query = query.filter(DataAsset.created_at <= datetime.fromisoformat(created_before))
    if updated_after:
        from datetime import datetime
        query = query.filter(DataAsset.updated_at >= datetime.fromisoformat(updated_after))
    if updated_before:
        from datetime import datetime
        query = query.filter(DataAsset.updated_at <= datetime.fromisoformat(updated_before))
    
    # Tag filters
    if tags:
        for tag in tags:
            query = query.filter(func.json_unquote(func.json_extract(DataAsset.tags, '$[*]')).ilike(f'%{tag}%'))
    
    # Source system filters
    if source_systems:
        query = query.filter(DataAsset.source_system.in_(source_systems))
    
    # Data type filters (if stored in schema_info)
    if data_types:
        data_type_conditions = []
        for data_type in data_types:
            data_type_conditions.append(
                func.json_unquote(func.json_extract(DataAsset.schema_info, '$')).ilike(f'%{data_type}%')
            )
        if data_type_conditions:
            query = query.filter(or_(*data_type_conditions))
    
    # Compliance filter
    if has_compliance and has_compliance.lower() == 'true':
        from backend.models.compliance_requirement import AssetCompliance
        compliant_asset_ids = db.session.query(AssetCompliance.asset_id).distinct().subquery()
        query = query.filter(DataAsset.asset_id.in_(compliant_asset_ids))
    
    # Enhanced sorting
    if sort_by == 'relevance' and query_text:
        # Custom relevance scoring based on where match occurs
        query = query.order_by(
            DataAsset.asset_name.ilike(f'%{query_text}%').desc(),  # Exact name matches first
            DataAsset.asset_name.ilike(f'{query_text}%').desc(),   # Name starts with query
            DataAsset.created_at.desc()
        )
    elif sort_by == 'name':
        if sort_order == 'asc':
            query = query.order_by(DataAsset.asset_name.asc())
        else:
            query = query.order_by(DataAsset.asset_name.desc())
    elif sort_by == 'updated_date':
        if sort_order == 'asc':
            query = query.order_by(DataAsset.updated_at.asc())
        else:
            query = query.order_by(DataAsset.updated_at.desc())
    else:  # created_date or default
        if sort_order == 'asc':
            query = query.order_by(DataAsset.created_at.asc())
        else:
            query = query.order_by(DataAsset.created_at.desc())
    
    # Get total count before pagination
    total_count = query.count()
    
    # Paginate results
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    # Format results with enhanced metadata
    results = []
    for asset in pagination.items:
        asset_dict = asset.to_dict()
        
        # Add search relevance information
        if query_text:
            asset_dict['search_score'] = calculate_search_score(asset, query_text)
            asset_dict['search_highlights'] = get_search_highlights(asset, query_text)
        
        # Add compliance summary if available
        try:
            compliance_summary = asset.get_compliance_summary()
            asset_dict['compliance_summary'] = compliance_summary
        except:
            pass
        
        results.append(asset_dict)
    
    # Get facet counts for dynamic filtering
    facets = get_search_facets(query_text, {
        'category_ids': category_ids,
        'report_type_ids': report_type_ids,
        'approval_statuses': approval_statuses,
        'owner_ids': owner_ids,
        'is_public': is_public,
        'is_sensitive': is_sensitive,
        'access_levels': access_levels,
        'tags': tags,
        'source_systems': source_systems
    })
    
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
        'facets': facets,
        'filters_applied': {
            'category_ids': category_ids,
            'report_type_ids': report_type_ids,
            'approval_statuses': approval_statuses,
            'owner_ids': owner_ids,
            'is_public': is_public,
            'is_sensitive': is_sensitive,
            'access_levels': access_levels,
            'tags': tags,
            'source_systems': source_systems,
            'has_compliance': has_compliance,
            'sort_by': sort_by,
            'sort_order': sort_order
        },
        'search_stats': {
            'total_results': total_count,
            'search_time': 0,  # Could implement actual timing
            'query_terms': query_text.split() if query_text else []
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


def get_search_highlights(asset, query_text):
    """Generate search result highlights showing where matches occurred"""
    highlights = {}
    query_lower = query_text.lower()
    
    # Asset name highlighting
    if asset.asset_name and query_lower in asset.asset_name.lower():
        highlights['asset_name'] = highlight_text(asset.asset_name, query_text)
    
    # Description highlighting
    if asset.description and query_lower in asset.description.lower():
        highlights['description'] = highlight_text(asset.description, query_text, max_length=200)
    
    # Business purpose highlighting
    if asset.business_purpose and query_lower in asset.business_purpose.lower():
        highlights['business_purpose'] = highlight_text(asset.business_purpose, query_text, max_length=150)
    
    # Source system highlighting
    if asset.source_system and query_lower in asset.source_system.lower():
        highlights['source_system'] = highlight_text(asset.source_system, query_text)
    
    # Tags highlighting
    if asset.tags:
        highlighted_tags = []
        for tag in asset.tags:
            if query_lower in tag.lower():
                highlighted_tags.append(highlight_text(tag, query_text))
            else:
                highlighted_tags.append(tag)
        highlights['tags'] = highlighted_tags
    
    return highlights


def highlight_text(text, query, max_length=None):
    """Add HTML highlighting to matched text"""
    if not text or not query:
        return text
    
    import re
    # Create case-insensitive regex pattern
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    
    # If max_length specified, find best snippet
    if max_length and len(text) > max_length:
        # Find the first match position
        match = pattern.search(text)
        if match:
            start = max(0, match.start() - max_length // 3)
            end = min(len(text), start + max_length)
            text = text[start:end]
            if start > 0:
                text = '...' + text
            if end < len(text):
                text = text + '...'
    
    # Apply highlighting
    highlighted = pattern.sub(f'<mark>\\g<0></mark>', text)
    return highlighted


def get_search_facets(query_text, current_filters):
    """Get facet counts for dynamic filtering"""
    try:
        # Base query for facet calculation
        base_query = DataAsset.query
        
        # Apply current text search to facet counts
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
                    DataAsset.business_purpose.ilike(term_pattern),
                    func.json_unquote(func.json_extract(DataAsset.tags, '$[*]')).ilike(term_pattern)
                )
                search_conditions.append(term_conditions)
            
            if search_conditions:
                base_query = base_query.filter(and_(*search_conditions))
        
        facets = {}
        
        # Category facets
        category_facets = db.session.query(
            Category.category_id,
            Category.category_name,
            func.count(DataAsset.asset_id).label('count')
        ).join(
            DataAsset, DataAsset.category_id == Category.category_id
        ).filter(
            Category.is_active == True
        )
        
        if query_text:
            category_facets = category_facets.filter(
                DataAsset.asset_id.in_(base_query.with_entities(DataAsset.asset_id).subquery())
            )
        
        category_facets = category_facets.group_by(
            Category.category_id, Category.category_name
        ).order_by(func.count(DataAsset.asset_id).desc()).all()
        
        facets['categories'] = [
            {
                'id': cat_id,
                'name': cat_name,
                'count': count,
                'selected': str(cat_id) in current_filters.get('category_ids', [])
            }
            for cat_id, cat_name, count in category_facets
        ]
        
        # Report type facets
        report_type_facets = db.session.query(
            ReportType.report_type_id,
            ReportType.type_name,
            func.count(DataAsset.asset_id).label('count')
        ).join(
            DataAsset, DataAsset.report_type_id == ReportType.report_type_id
        ).filter(
            ReportType.is_active == True
        )
        
        if query_text:
            report_type_facets = report_type_facets.filter(
                DataAsset.asset_id.in_(base_query.with_entities(DataAsset.asset_id).subquery())
            )
        
        report_type_facets = report_type_facets.group_by(
            ReportType.report_type_id, ReportType.type_name
        ).order_by(func.count(DataAsset.asset_id).desc()).all()
        
        facets['report_types'] = [
            {
                'id': rt_id,
                'name': rt_name,
                'count': count,
                'selected': str(rt_id) in current_filters.get('report_type_ids', [])
            }
            for rt_id, rt_name, count in report_type_facets
        ]
        
        # Owner facets
        owner_facets = db.session.query(
            User.user_id,
            User.display_name,
            func.count(DataAsset.asset_id).label('count')
        ).join(
            DataAsset, DataAsset.owner_user_id == User.user_id
        ).filter(
            User.is_active == True
        )
        
        if query_text:
            owner_facets = owner_facets.filter(
                DataAsset.asset_id.in_(base_query.with_entities(DataAsset.asset_id).subquery())
            )
        
        owner_facets = owner_facets.group_by(
            User.user_id, User.display_name
        ).order_by(func.count(DataAsset.asset_id).desc()).limit(20).all()
        
        facets['owners'] = [
            {
                'id': user_id,
                'name': display_name,
                'count': count,
                'selected': user_id in current_filters.get('owner_ids', [])
            }
            for user_id, display_name, count in owner_facets
        ]
        
        # Status facets
        status_facets = base_query.with_entities(
            DataAsset.approval_status,
            func.count(DataAsset.asset_id).label('count')
        ).group_by(DataAsset.approval_status).all()
        
        facets['statuses'] = [
            {
                'status': status,
                'count': count,
                'selected': status in current_filters.get('approval_statuses', [])
            }
            for status, count in status_facets
        ]
        
        # Access level facets
        access_level_facets = base_query.with_entities(
            DataAsset.access_level,
            func.count(DataAsset.asset_id).label('count')
        ).filter(
            DataAsset.access_level.isnot(None)
        ).group_by(DataAsset.access_level).all()
        
        facets['access_levels'] = [
            {
                'level': level,
                'count': count,
                'selected': level in current_filters.get('access_levels', [])
            }
            for level, count in access_level_facets
        ]
        
        # Source system facets
        source_system_facets = base_query.with_entities(
            DataAsset.source_system,
            func.count(DataAsset.asset_id).label('count')
        ).filter(
            DataAsset.source_system.isnot(None)
        ).group_by(DataAsset.source_system).order_by(
            func.count(DataAsset.asset_id).desc()
        ).limit(15).all()
        
        facets['source_systems'] = [
            {
                'system': system,
                'count': count,
                'selected': system in current_filters.get('source_systems', [])
            }
            for system, count in source_system_facets
        ]
        
        # Data sensitivity facets
        sensitivity_facets = [
            {
                'type': 'Public',
                'count': base_query.filter(DataAsset.is_public == True).count(),
                'selected': current_filters.get('is_public') == 'true'
            },
            {
                'type': 'Sensitive',
                'count': base_query.filter(DataAsset.is_sensitive == True).count(),
                'selected': current_filters.get('is_sensitive') == 'true'
            }
        ]
        
        facets['sensitivity'] = sensitivity_facets
        
        return facets
        
    except Exception as e:
        # Return empty facets on error
        return {
            'categories': [],
            'report_types': [],
            'owners': [],
            'statuses': [],
            'access_levels': [],
            'source_systems': [],
            'sensitivity': []
        }


@search_bp.route('/facets', methods=['GET'])
@token_required
def get_facets():
    """Get facet options for advanced search filtering"""
    query_text = request.args.get('q', '').strip()
    
    # Get current filter context for facet calculation
    current_filters = {
        'category_ids': request.args.getlist('category_id'),
        'report_type_ids': request.args.getlist('report_type_id'),
        'approval_statuses': request.args.getlist('status'),
        'owner_ids': request.args.getlist('owner_id'),
        'is_public': request.args.get('is_public'),
        'is_sensitive': request.args.get('is_sensitive'),
        'access_levels': request.args.getlist('access_level'),
        'source_systems': request.args.getlist('source_system')
    }
    
    facets = get_search_facets(query_text, current_filters)
    
    return jsonify({
        'facets': facets,
        'query': query_text
    })


@search_bp.route('/export', methods=['POST'])
@token_required
def export_search_results():
    """Export search results to CSV/Excel"""
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No search parameters provided'}), 400
    
    # Extract search parameters from request
    query_text = data.get('query', '')
    filters = data.get('filters', {})
    export_format = data.get('format', 'csv')  # csv or excel
    
    # Recreate the search query (without pagination)
    query = DataAsset.query
    
    # Apply the same filters as the main search
    # (Implementation similar to main search but without pagination)
    
    # For now, return placeholder
    return jsonify({
        'message': 'Export functionality not yet implemented',
        'parameters': {
            'query': query_text,
            'format': export_format,
            'filters': filters
        }
    })