from flask import Blueprint, request, jsonify, current_app
from backend.models import db, ComplianceRequirement, AssetCompliance, DataAsset
from backend.utils.auth import token_required, admin_required, get_current_user_id
from datetime import datetime, timedelta
from sqlalchemy import func, and_

compliance_bp = Blueprint('compliance', __name__)


@compliance_bp.route('/requirements', methods=['POST'])
@admin_required
def create_compliance_requirement():
    """Create a new compliance requirement"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required_fields = ['requirement_name', 'regulatory_body', 'requirement_type']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    try:
        requirement = ComplianceRequirement(
            requirement_name=data['requirement_name'],
            description=data.get('description'),
            regulatory_body=data['regulatory_body'],
            regulation_reference=data.get('regulation_reference'),
            requirement_type=data['requirement_type'],
            severity_level=data.get('severity_level', 'Medium'),
            review_frequency=data.get('review_frequency'),
            implementation_guidance=data.get('implementation_guidance'),
            effective_date=datetime.fromisoformat(data['effective_date']) if data.get('effective_date') else None,
            expiry_date=datetime.fromisoformat(data['expiry_date']) if data.get('expiry_date') else None,
            status=data.get('status', 'Active'),
            created_by_user_id=get_current_user_id()
        )
        
        db.session.add(requirement)
        db.session.commit()
        
        current_app.logger.info(f"Compliance requirement created: {requirement.requirement_name}")
        
        return jsonify({
            'message': 'Compliance requirement created successfully',
            'requirement': requirement.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create compliance requirement: {e}")
        return jsonify({'error': 'Failed to create compliance requirement'}), 500


@compliance_bp.route('/requirements', methods=['GET'])
@token_required
def get_compliance_requirements():
    """Get all compliance requirements with filtering"""
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    regulatory_body = request.args.get('regulatory_body')
    requirement_type = request.args.get('requirement_type')
    severity_level = request.args.get('severity_level')
    status = request.args.get('status', 'Active')
    search = request.args.get('search', '').strip()
    
    # Build query
    query = ComplianceRequirement.query
    
    # Apply filters
    if regulatory_body:
        query = query.filter(ComplianceRequirement.regulatory_body == regulatory_body)
    if requirement_type:
        query = query.filter(ComplianceRequirement.requirement_type == requirement_type)
    if severity_level:
        query = query.filter(ComplianceRequirement.severity_level == severity_level)
    if status:
        query = query.filter(ComplianceRequirement.status == status)
    
    # Text search
    if search:
        query = query.filter(
            db.or_(
                ComplianceRequirement.requirement_name.ilike(f'%{search}%'),
                ComplianceRequirement.description.ilike(f'%{search}%'),
                ComplianceRequirement.regulatory_body.ilike(f'%{search}%')
            )
        )
    
    # Order by creation date
    query = query.order_by(ComplianceRequirement.created_at.desc())
    
    # Paginate
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    requirements = []
    for req in pagination.items:
        req_dict = req.to_dict()
        req_dict['compliance_summary'] = req.get_compliance_summary()
        requirements.append(req_dict)
    
    return jsonify({
        'requirements': requirements,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@compliance_bp.route('/requirements/<int:requirement_id>', methods=['GET'])
@token_required
def get_compliance_requirement(requirement_id):
    """Get specific compliance requirement with linked assets"""
    requirement = ComplianceRequirement.query.get_or_404(requirement_id)
    
    # Get linked assets
    linked_assets = db.session.query(AssetCompliance, DataAsset)\
        .join(DataAsset, AssetCompliance.asset_id == DataAsset.asset_id)\
        .filter(AssetCompliance.compliance_id == requirement_id)\
        .all()
    
    req_dict = requirement.to_dict()
    req_dict['compliance_summary'] = requirement.get_compliance_summary()
    req_dict['linked_assets'] = [
        {
            'compliance_link': link.to_dict(),
            'asset': asset.to_dict()
        }
        for link, asset in linked_assets
    ]
    
    return jsonify({
        'requirement': req_dict
    })


@compliance_bp.route('/requirements/<int:requirement_id>', methods=['PUT'])
@admin_required
def update_compliance_requirement(requirement_id):
    """Update compliance requirement"""
    requirement = ComplianceRequirement.query.get_or_404(requirement_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Update fields
        updateable_fields = [
            'requirement_name', 'description', 'regulatory_body', 'regulation_reference',
            'requirement_type', 'severity_level', 'review_frequency', 'implementation_guidance',
            'status'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(requirement, field, data[field])
        
        # Handle date fields
        if 'effective_date' in data:
            requirement.effective_date = datetime.fromisoformat(data['effective_date']) if data['effective_date'] else None
        if 'expiry_date' in data:
            requirement.expiry_date = datetime.fromisoformat(data['expiry_date']) if data['expiry_date'] else None
        
        requirement.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Compliance requirement updated successfully',
            'requirement': requirement.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update compliance requirement {requirement_id}: {e}")
        return jsonify({'error': 'Failed to update compliance requirement'}), 500


@compliance_bp.route('/assets/<int:asset_id>/compliance', methods=['POST'])
@token_required
def link_asset_compliance(asset_id):
    """Link an asset to a compliance requirement"""
    asset = DataAsset.query.get_or_404(asset_id)
    data = request.get_json()
    
    if not data or not data.get('compliance_id'):
        return jsonify({'error': 'Compliance ID is required'}), 400
    
    compliance_id = data['compliance_id']
    requirement = ComplianceRequirement.query.get_or_404(compliance_id)
    
    # Check if link already exists
    existing_link = AssetCompliance.query.filter_by(
        asset_id=asset_id,
        compliance_id=compliance_id
    ).first()
    
    if existing_link:
        return jsonify({'error': 'Asset is already linked to this compliance requirement'}), 409
    
    try:
        compliance_link = AssetCompliance(
            asset_id=asset_id,
            compliance_id=compliance_id,
            compliance_status=data.get('compliance_status', 'Pending'),
            assessment_notes=data.get('assessment_notes'),
            risk_level=data.get('risk_level', 'Medium'),
            assessed_by_user_id=get_current_user_id()
        )
        
        # Set review date if provided
        if data.get('next_review_date'):
            compliance_link.next_review_date = datetime.fromisoformat(data['next_review_date'])
        
        db.session.add(compliance_link)
        db.session.commit()
        
        return jsonify({
            'message': 'Asset linked to compliance requirement successfully',
            'compliance_link': compliance_link.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to link asset compliance: {e}")
        return jsonify({'error': 'Failed to link asset compliance'}), 500


@compliance_bp.route('/assets/<int:asset_id>/compliance/<int:compliance_id>', methods=['PUT'])
@token_required
def update_asset_compliance(asset_id, compliance_id):
    """Update asset compliance status"""
    compliance_link = AssetCompliance.query.filter_by(
        asset_id=asset_id,
        compliance_id=compliance_id
    ).first_or_404()
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Update compliance fields
        updateable_fields = [
            'compliance_status', 'assessment_notes', 'remediation_plan',
            'risk_level', 'evidence_location', 'documentation_links'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(compliance_link, field, data[field])
        
        # Handle date fields
        if 'next_review_date' in data:
            compliance_link.next_review_date = datetime.fromisoformat(data['next_review_date']) if data['next_review_date'] else None
        
        # Update assessment info
        compliance_link.assessment_date = datetime.utcnow()
        compliance_link.assessed_by_user_id = get_current_user_id()
        compliance_link.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Asset compliance updated successfully',
            'compliance_link': compliance_link.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update asset compliance: {e}")
        return jsonify({'error': 'Failed to update asset compliance'}), 500


@compliance_bp.route('/dashboard', methods=['GET'])
@token_required
def get_compliance_dashboard():
    """Get compliance dashboard statistics"""
    try:
        # Overall compliance statistics
        total_requirements = ComplianceRequirement.query.filter_by(status='Active').count()
        total_asset_links = AssetCompliance.query.count()
        
        # Compliance status breakdown
        status_breakdown = db.session.query(
            AssetCompliance.compliance_status,
            func.count(AssetCompliance.compliance_link_id).label('count')
        ).group_by(AssetCompliance.compliance_status).all()
        
        status_summary = {status: count for status, count in status_breakdown}
        
        # Risk level distribution
        risk_breakdown = db.session.query(
            AssetCompliance.risk_level,
            func.count(AssetCompliance.compliance_link_id).label('count')
        ).group_by(AssetCompliance.risk_level).all()
        
        risk_summary = {risk: count for risk, count in risk_breakdown}
        
        # Requirements by regulatory body
        regulatory_breakdown = db.session.query(
            ComplianceRequirement.regulatory_body,
            func.count(ComplianceRequirement.compliance_id).label('count')
        ).filter_by(status='Active').group_by(ComplianceRequirement.regulatory_body).all()
        
        regulatory_summary = {body: count for body, count in regulatory_breakdown}
        
        # Overdue reviews
        overdue_reviews = AssetCompliance.query.filter(
            and_(
                AssetCompliance.next_review_date.isnot(None),
                AssetCompliance.next_review_date < datetime.utcnow()
            )
        ).count()
        
        # Recent assessments (last 30 days)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        recent_assessments = AssetCompliance.query.filter(
            AssetCompliance.assessment_date >= thirty_days_ago
        ).count()
        
        # Top non-compliant assets
        non_compliant_assets = db.session.query(
            DataAsset,
            func.count(AssetCompliance.compliance_link_id).label('non_compliant_count')
        ).join(
            AssetCompliance, DataAsset.asset_id == AssetCompliance.asset_id
        ).filter(
            AssetCompliance.compliance_status == 'Non-Compliant'
        ).group_by(DataAsset.asset_id).order_by(
            func.count(AssetCompliance.compliance_link_id).desc()
        ).limit(10).all()
        
        return jsonify({
            'summary': {
                'total_requirements': total_requirements,
                'total_asset_links': total_asset_links,
                'overdue_reviews': overdue_reviews,
                'recent_assessments': recent_assessments,
                'compliance_percentage': round(
                    (status_summary.get('Compliant', 0) / total_asset_links * 100) if total_asset_links > 0 else 0, 1
                )
            },
            'status_breakdown': status_summary,
            'risk_breakdown': risk_summary,
            'regulatory_breakdown': regulatory_summary,
            'top_non_compliant_assets': [
                {
                    'asset': asset.to_dict(),
                    'non_compliant_count': count
                }
                for asset, count in non_compliant_assets
            ]
        })

    except Exception as e:
        current_app.logger.error(f"Failed to get compliance dashboard: {e}")
        return jsonify({'error': 'Failed to get compliance dashboard'}), 500


@compliance_bp.route('/overdue-reviews', methods=['GET'])
@token_required
def get_overdue_reviews():
    """Get assets with overdue compliance reviews"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Query overdue reviews
    query = db.session.query(AssetCompliance, DataAsset, ComplianceRequirement)\
        .join(DataAsset, AssetCompliance.asset_id == DataAsset.asset_id)\
        .join(ComplianceRequirement, AssetCompliance.compliance_id == ComplianceRequirement.compliance_id)\
        .filter(
            and_(
                AssetCompliance.next_review_date.isnot(None),
                AssetCompliance.next_review_date < datetime.utcnow()
            )
        ).order_by(AssetCompliance.next_review_date.asc())
    
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    
    overdue_items = []
    for compliance_link, asset, requirement in pagination.items:
        days_overdue = (datetime.utcnow() - compliance_link.next_review_date).days
        overdue_items.append({
            'compliance_link': compliance_link.to_dict(),
            'asset': asset.to_dict(),
            'requirement': requirement.to_dict(),
            'days_overdue': days_overdue
        })
    
    return jsonify({
        'overdue_reviews': overdue_items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@compliance_bp.route('/requirements/filters', methods=['GET'])
@token_required
def get_compliance_filters():
    """Get available filter options for compliance requirements"""
    # Get unique regulatory bodies
    regulatory_bodies = db.session.query(ComplianceRequirement.regulatory_body)\
        .filter_by(status='Active').distinct().all()
    
    # Get unique requirement types
    requirement_types = db.session.query(ComplianceRequirement.requirement_type)\
        .filter_by(status='Active').distinct().all()
    
    # Get unique severity levels
    severity_levels = db.session.query(ComplianceRequirement.severity_level)\
        .filter_by(status='Active').distinct().all()
    
    return jsonify({
        'regulatory_bodies': [body[0] for body in regulatory_bodies if body[0]],
        'requirement_types': [req_type[0] for req_type in requirement_types if req_type[0]],
        'severity_levels': [level[0] for level in severity_levels if level[0]],
        'compliance_statuses': ['Compliant', 'Non-Compliant', 'Pending', 'Not Applicable'],
        'risk_levels': ['Critical', 'High', 'Medium', 'Low']
    })