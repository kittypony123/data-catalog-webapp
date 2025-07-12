from flask import Blueprint, request, jsonify, current_app
from backend.models import db, BusinessTerm, TermUsage, DataAsset
from backend.utils.auth import token_required, admin_required, get_current_user_id
from datetime import datetime, timedelta
from sqlalchemy import func, and_

business_glossary_bp = Blueprint('business_glossary', __name__)


@business_glossary_bp.route('/terms', methods=['POST'])
@token_required
def create_business_term():
    """Create a new business term"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required_fields = ['term_name', 'definition']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Check for duplicate term name
    existing_term = BusinessTerm.query.filter_by(term_name=data['term_name']).first()
    if existing_term:
        return jsonify({'error': 'Term name already exists'}), 409

    try:
        term = BusinessTerm(
            term_name=data['term_name'],
            definition=data['definition'],
            context=data.get('context'),
            domain=data.get('domain'),
            synonyms=data.get('synonyms', []),
            examples=data.get('examples', []),
            term_type=data.get('term_type', 'Standard'),
            sensitivity_level=data.get('sensitivity_level', 'Public'),
            business_owner=data.get('business_owner'),
            technical_owner=data.get('technical_owner'),
            authoritative_source=data.get('authoritative_source'),
            created_by_user_id=get_current_user_id()
        )
        
        db.session.add(term)
        db.session.commit()
        
        current_app.logger.info(f"Business term created: {term.term_name}")
        
        return jsonify({
            'message': 'Business term created successfully',
            'term': term.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create business term: {e}")
        return jsonify({'error': 'Failed to create business term'}), 500


@business_glossary_bp.route('/terms', methods=['GET'])
@token_required
def get_business_terms():
    """Get all business terms with filtering and search"""
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    domain = request.args.get('domain')
    term_type = request.args.get('term_type')
    status = request.args.get('status', 'Approved')
    search = request.args.get('search', '').strip()
    include_draft = request.args.get('include_draft', 'false').lower() == 'true'
    
    # Build query
    query = BusinessTerm.query
    
    # Apply filters
    if domain:
        query = query.filter(BusinessTerm.domain == domain)
    if term_type:
        query = query.filter(BusinessTerm.term_type == term_type)
    if status and not include_draft:
        query = query.filter(BusinessTerm.status == status)
    elif include_draft:
        query = query.filter(BusinessTerm.status.in_(['Approved', 'Draft']))
    
    # Text search
    if search:
        query = query.filter(
            db.or_(
                BusinessTerm.term_name.ilike(f'%{search}%'),
                BusinessTerm.definition.ilike(f'%{search}%'),
                BusinessTerm.context.ilike(f'%{search}%')
            )
        )
    
    # Order by term name
    query = query.order_by(BusinessTerm.term_name)
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    terms = []
    for term in pagination.items:
        term_dict = term.to_dict()
        term_dict['usage_count'] = term.get_usage_count()
        term_dict['needs_review'] = term.needs_review()
        terms.append(term_dict)
    
    return jsonify({
        'terms': terms,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@business_glossary_bp.route('/terms/<int:term_id>', methods=['GET'])
@token_required
def get_business_term(term_id):
    """Get specific business term with relationships"""
    term = BusinessTerm.query.get_or_404(term_id)
    
    # Get term usages
    term_usages = TermUsage.query.filter_by(term_id=term_id).all()
    
    term_dict = term.to_dict(include_relationships=True)
    term_dict['usage_count'] = len(term_usages)
    term_dict['usages'] = [usage.to_dict() for usage in term_usages]
    term_dict['needs_review'] = term.needs_review()
    term_dict['days_since_update'] = term.days_since_last_update()
    
    return jsonify({
        'term': term_dict
    })


@business_glossary_bp.route('/terms/<int:term_id>', methods=['PUT'])
@token_required
def update_business_term(term_id):
    """Update business term"""
    term = BusinessTerm.query.get_or_404(term_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Check for duplicate term name (if changed)
    if 'term_name' in data and data['term_name'] != term.term_name:
        existing_term = BusinessTerm.query.filter_by(term_name=data['term_name']).first()
        if existing_term:
            return jsonify({'error': 'Term name already exists'}), 409

    try:
        # Update fields
        updateable_fields = [
            'term_name', 'definition', 'context', 'domain', 'synonyms', 'examples',
            'term_type', 'sensitivity_level', 'business_owner', 'technical_owner',
            'authoritative_source', 'status', 'version'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(term, field, data[field])
        
        # Handle date fields
        if 'approval_date' in data:
            term.approval_date = datetime.fromisoformat(data['approval_date']) if data['approval_date'] else None
        if 'review_date' in data:
            term.review_date = datetime.fromisoformat(data['review_date']) if data['review_date'] else None
        
        # Set approval metadata if status changed to Approved
        if data.get('status') == 'Approved' and term.status != 'Approved':
            term.approval_date = datetime.utcnow()
            term.approved_by_user_id = get_current_user_id()
        
        term.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Business term updated successfully',
            'term': term.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update business term {term_id}: {e}")
        return jsonify({'error': 'Failed to update business term'}), 500


@business_glossary_bp.route('/terms/<int:term_id>/relationships', methods=['POST'])
@token_required
def add_term_relationship(term_id):
    """Add relationship between terms"""
    term = BusinessTerm.query.get_or_404(term_id)
    data = request.get_json()
    
    if not data or not data.get('related_term_id'):
        return jsonify({'error': 'Related term ID is required'}), 400
    
    related_term_id = data['related_term_id']
    related_term = BusinessTerm.query.get_or_404(related_term_id)
    
    if term_id == related_term_id:
        return jsonify({'error': 'Term cannot be related to itself'}), 400

    try:
        term.add_related_term(related_term_id)
        db.session.commit()
        
        return jsonify({
            'message': 'Term relationship added successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to add term relationship: {e}")
        return jsonify({'error': 'Failed to add term relationship'}), 500


@business_glossary_bp.route('/terms/<int:term_id>/relationships/<int:related_term_id>', methods=['DELETE'])
@token_required
def remove_term_relationship(term_id, related_term_id):
    """Remove relationship between terms"""
    term = BusinessTerm.query.get_or_404(term_id)
    related_term = BusinessTerm.query.get_or_404(related_term_id)

    try:
        term.remove_related_term(related_term_id)
        db.session.commit()
        
        return jsonify({
            'message': 'Term relationship removed successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to remove term relationship: {e}")
        return jsonify({'error': 'Failed to remove term relationship'}), 500


@business_glossary_bp.route('/terms/<int:term_id>/usage', methods=['POST'])
@token_required
def link_term_to_asset(term_id):
    """Link a business term to a data asset"""
    term = BusinessTerm.query.get_or_404(term_id)
    data = request.get_json()
    
    if not data or not data.get('asset_id'):
        return jsonify({'error': 'Asset ID is required'}), 400
    
    asset_id = data['asset_id']
    asset = DataAsset.query.get_or_404(asset_id)
    
    # Check if link already exists
    existing_usage = TermUsage.query.filter_by(term_id=term_id, asset_id=asset_id).first()
    if existing_usage:
        return jsonify({'error': 'Term is already linked to this asset'}), 409

    try:
        term_usage = TermUsage(
            term_id=term_id,
            asset_id=asset_id,
            usage_context=data.get('usage_context'),
            confidence_score=data.get('confidence_score'),
            verified=data.get('verified', False),
            created_by_user_id=get_current_user_id()
        )
        
        db.session.add(term_usage)
        db.session.commit()
        
        return jsonify({
            'message': 'Term linked to asset successfully',
            'term_usage': term_usage.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to link term to asset: {e}")
        return jsonify({'error': 'Failed to link term to asset'}), 500


@business_glossary_bp.route('/usage/<int:usage_id>', methods=['PUT'])
@token_required
def update_term_usage(usage_id):
    """Update term usage information"""
    term_usage = TermUsage.query.get_or_404(usage_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Update fields
        updateable_fields = ['usage_context', 'confidence_score', 'verified']
        
        for field in updateable_fields:
            if field in data:
                setattr(term_usage, field, data[field])
        
        db.session.commit()
        
        return jsonify({
            'message': 'Term usage updated successfully',
            'term_usage': term_usage.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update term usage {usage_id}: {e}")
        return jsonify({'error': 'Failed to update term usage'}), 500


@business_glossary_bp.route('/usage/<int:usage_id>', methods=['DELETE'])
@token_required
def remove_term_usage(usage_id):
    """Remove term usage link"""
    term_usage = TermUsage.query.get_or_404(usage_id)

    try:
        db.session.delete(term_usage)
        db.session.commit()
        
        return jsonify({
            'message': 'Term usage removed successfully'
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to remove term usage {usage_id}: {e}")
        return jsonify({'error': 'Failed to remove term usage'}), 500


@business_glossary_bp.route('/dashboard', methods=['GET'])
@token_required
def get_glossary_dashboard():
    """Get business glossary dashboard statistics"""
    try:
        # Overall statistics
        total_terms = BusinessTerm.query.count()
        approved_terms = BusinessTerm.query.filter_by(status='Approved').count()
        draft_terms = BusinessTerm.query.filter_by(status='Draft').count()
        total_usage_links = TermUsage.query.count()
        verified_usage_links = TermUsage.query.filter_by(verified=True).count()
        
        # Domain statistics
        domain_stats = BusinessTerm.get_domain_statistics()
        
        # Term type breakdown
        type_breakdown = db.session.query(
            BusinessTerm.term_type,
            func.count(BusinessTerm.term_id).label('count')
        ).group_by(BusinessTerm.term_type).all()
        
        type_summary = {term_type: count for term_type, count in type_breakdown}
        
        # Terms needing review (review date passed or no review date set for approved terms)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        terms_needing_review = BusinessTerm.query.filter(
            db.or_(
                and_(BusinessTerm.review_date.isnot(None), BusinessTerm.review_date < datetime.utcnow()),
                and_(BusinessTerm.status == 'Approved', BusinessTerm.review_date.is_(None))
            )
        ).count()
        
        # Most used terms
        most_used_terms = db.session.query(
            BusinessTerm,
            func.count(TermUsage.usage_id).label('usage_count')
        ).outerjoin(
            TermUsage, BusinessTerm.term_id == TermUsage.term_id
        ).group_by(BusinessTerm.term_id).order_by(
            func.count(TermUsage.usage_id).desc()
        ).limit(10).all()
        
        # Recent term activity (created in last 30 days)
        recent_terms = BusinessTerm.query.filter(
            BusinessTerm.created_at >= thirty_days_ago
        ).count()
        
        return jsonify({
            'summary': {
                'total_terms': total_terms,
                'approved_terms': approved_terms,
                'draft_terms': draft_terms,
                'total_usage_links': total_usage_links,
                'verified_usage_links': verified_usage_links,
                'terms_needing_review': terms_needing_review,
                'recent_terms': recent_terms,
                'approval_percentage': round((approved_terms / total_terms * 100) if total_terms > 0 else 0, 1),
                'verification_percentage': round((verified_usage_links / total_usage_links * 100) if total_usage_links > 0 else 0, 1)
            },
            'domain_breakdown': domain_stats,
            'type_breakdown': type_summary,
            'most_used_terms': [
                {
                    'term': term.to_dict(),
                    'usage_count': count
                }
                for term, count in most_used_terms
            ]
        })

    except Exception as e:
        current_app.logger.error(f"Failed to get glossary dashboard: {e}")
        return jsonify({'error': 'Failed to get glossary dashboard'}), 500


@business_glossary_bp.route('/search', methods=['GET'])
@token_required
def search_terms():
    """Advanced search for business terms"""
    query = request.args.get('q', '').strip()
    domain = request.args.get('domain')
    term_type = request.args.get('term_type')
    status = request.args.get('status', 'Approved')
    limit = min(request.args.get('limit', 10, type=int), 50)
    
    if not query:
        return jsonify({'terms': []})
    
    try:
        search_results = BusinessTerm.search_terms(
            query=query,
            domain=domain,
            term_type=term_type,
            status=status
        ).limit(limit).all()
        
        results = []
        for term in search_results:
            term_dict = term.to_dict()
            term_dict['usage_count'] = term.get_usage_count()
            results.append(term_dict)
        
        return jsonify({
            'terms': results,
            'query': query,
            'total_results': len(results)
        })

    except Exception as e:
        current_app.logger.error(f"Failed to search terms: {e}")
        return jsonify({'error': 'Failed to search terms'}), 500


@business_glossary_bp.route('/filters', methods=['GET'])
@token_required
def get_glossary_filters():
    """Get available filter options for business terms"""
    # Get unique domains
    domains = db.session.query(BusinessTerm.domain).distinct().all()
    
    # Get unique term types
    term_types = db.session.query(BusinessTerm.term_type).distinct().all()
    
    return jsonify({
        'domains': [domain[0] for domain in domains if domain[0]],
        'term_types': [term_type[0] for term_type in term_types if term_type[0]],
        'statuses': ['Draft', 'Approved', 'Deprecated'],
        'sensitivity_levels': ['Public', 'Internal', 'Confidential']
    })


@business_glossary_bp.route('/export', methods=['GET'])
@token_required
def export_glossary():
    """Export business glossary in JSON format"""
    try:
        terms = BusinessTerm.query.filter_by(status='Approved').order_by(BusinessTerm.term_name).all()
        
        export_data = {
            'exported_at': datetime.utcnow().isoformat(),
            'total_terms': len(terms),
            'terms': [term.to_dict(include_relationships=True) for term in terms]
        }
        
        return jsonify(export_data)

    except Exception as e:
        current_app.logger.error(f"Failed to export glossary: {e}")
        return jsonify({'error': 'Failed to export glossary'}), 500