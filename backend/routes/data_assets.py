from flask import Blueprint, request, jsonify, current_app
from backend.models import db, DataAsset, Category, ReportType, AssetRelationship, ApprovalHistory
from backend.utils.auth import token_required, admin_required, asset_owner_or_admin_required, get_current_user_id
from datetime import datetime

assets_bp = Blueprint('assets', __name__)


@assets_bp.route('/', methods=['POST'])
@token_required
def create_asset():
    """Create a new data asset"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required_fields = ['asset_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Validate foreign keys
    if data.get('category_id'):
        category = Category.query.get(data['category_id'])
        if not category or not category.is_active:
            return jsonify({'error': 'Invalid category'}), 400

    if data.get('report_type_id'):
        report_type = ReportType.query.get(data['report_type_id'])
        if not report_type or not report_type.is_active:
            return jsonify({'error': 'Invalid report type'}), 400
        
        # Validate required fields for report type
        is_valid, missing_fields = report_type.validate_asset_data(data)
        if not is_valid:
            return jsonify({
                'error': 'Missing required fields for this report type',
                'missing_fields': missing_fields
            }), 400

    # Create asset
    asset = DataAsset(
        asset_name=data['asset_name'],
        description=data.get('description'),
        source_system=data.get('source_system'),
        source_location=data.get('source_location'),
        schema_info=data.get('schema_info'),
        metadata=data.get('metadata'),
        tags=data.get('tags'),
        report_type_id=data.get('report_type_id'),
        category_id=data.get('category_id'),
        owner_user_id=data.get('owner_user_id', get_current_user_id()),
        submitted_by_user_id=get_current_user_id(),
        is_public=data.get('is_public', False),
        is_sensitive=data.get('is_sensitive', False),
        access_level=data.get('access_level', 'Internal')
    )

    try:
        db.session.add(asset)
        db.session.flush()  # Get asset ID before commit

        # Log creation
        ApprovalHistory.log_action(
            asset_id=asset.asset_id,
            action='submitted',
            new_status='Pending',
            performed_by_user_id=get_current_user_id(),
            comments=f"Asset '{asset.asset_name}' submitted for approval"
        )

        db.session.commit()
        current_app.logger.info(f"Asset created: {asset.asset_name} by {get_current_user_id()}")
        
        return jsonify({
            'message': 'Asset created successfully',
            'asset': asset.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create asset: {e}")
        return jsonify({'error': 'Failed to create asset'}), 500


@assets_bp.route('/', methods=['GET'])
@token_required
def get_assets():
    """Get list of assets with filtering"""
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status = request.args.get('status', 'Approved')
    category_id = request.args.get('category_id', type=int)
    report_type_id = request.args.get('report_type_id', type=int)
    owner_id = request.args.get('owner_id')
    search = request.args.get('search', '').strip()
    
    # Build query
    query = DataAsset.query
    
    # Filter by approval status
    if status:
        query = query.filter(DataAsset.approval_status == status)
    
    # Apply filters
    filters = {}
    if category_id:
        filters['category_id'] = category_id
    if report_type_id:
        filters['report_type_id'] = report_type_id
    if owner_id:
        filters['owner_user_id'] = owner_id
    
    # Apply search and filters
    if search or filters:
        query = DataAsset.search(search, filters)
    
    # Order by creation date (newest first)
    query = query.order_by(DataAsset.created_at.desc())
    
    # Paginate
    pagination = query.paginate(
        page=page, 
        per_page=per_page, 
        error_out=False
    )
    
    assets = [asset.to_dict() for asset in pagination.items]
    
    return jsonify({
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


@assets_bp.route('/<int:asset_id>', methods=['GET'])
@token_required
def get_asset(asset_id):
    """Get specific asset with comprehensive details including compliance"""
    asset = DataAsset.query.get_or_404(asset_id)
    
    # Update last accessed
    asset.update_last_accessed()
    
    # Get comprehensive asset data with compliance
    asset_data = asset.to_dict(include_relationships=True, include_compliance=True)
    
    # Get approval history
    history = [h.to_dict() for h in asset.approval_history.order_by(ApprovalHistory.performed_at.desc()).limit(10)]
    
    # Get compliance details if available
    compliance_details = None
    try:
        from backend.models import AssetCompliance, ComplianceRequirement
        
        # Get all compliance links for this asset
        compliance_links = db.session.query(AssetCompliance, ComplianceRequirement)\
            .join(ComplianceRequirement, AssetCompliance.compliance_id == ComplianceRequirement.compliance_id)\
            .filter(AssetCompliance.asset_id == asset_id)\
            .order_by(AssetCompliance.assessment_date.desc().nullslast())\
            .all()
        
        compliance_details = []
        for link, requirement in compliance_links:
            link_data = link.to_dict()
            link_data['requirement_details'] = requirement.to_dict()
            link_data['is_overdue'] = link.is_overdue()
            link_data['days_until_review'] = link.days_until_review()
            compliance_details.append(link_data)
            
        # Calculate overall compliance metrics
        asset_data['compliance_metrics'] = {
            'overall_status': asset.get_overall_compliance_status(),
            'risk_score': asset.get_risk_score(),
            'total_requirements': len(compliance_details),
            'compliant_count': len([c for c in compliance_details if c['compliance_status'] == 'Compliant']),
            'overdue_count': len([c for c in compliance_details if c['is_overdue']]),
            'critical_risks': len([c for c in compliance_details if c['risk_level'] == 'Critical'])
        }
        
    except ImportError:
        # Compliance module not available
        compliance_details = []
        asset_data['compliance_metrics'] = None
    
    # Get business glossary terms if available
    glossary_terms = None
    try:
        from backend.models import TermUsage, BusinessTerm
        
        term_usages = db.session.query(TermUsage, BusinessTerm)\
            .join(BusinessTerm, TermUsage.term_id == BusinessTerm.term_id)\
            .filter(TermUsage.asset_id == asset_id)\
            .all()
        
        glossary_terms = []
        for usage, term in term_usages:
            term_data = usage.to_dict()
            term_data['term_details'] = term.to_dict()
            glossary_terms.append(term_data)
            
    except ImportError:
        # Glossary module not available
        glossary_terms = []
    
    # Get data lineage (upstream and downstream assets)
    lineage_data = {
        'upstream': [],
        'downstream': []
    }
    
    # Upstream relationships (where this asset is the target)
    upstream_rels = asset.upstream_relationships.all()
    for rel in upstream_rels:
        upstream_asset = rel.source_asset
        lineage_data['upstream'].append({
            'asset': upstream_asset.to_dict(),
            'relationship': rel.to_dict()
        })
    
    # Downstream relationships (where this asset is the source)
    downstream_rels = asset.downstream_relationships.all()
    for rel in downstream_rels:
        downstream_asset = rel.target_asset
        lineage_data['downstream'].append({
            'asset': downstream_asset.to_dict(),
            'relationship': rel.to_dict()
        })
    
    # Get related assets (same category or similar tags)
    related_assets = []
    if asset.category_id:
        similar_assets = DataAsset.query.filter(
            DataAsset.category_id == asset.category_id,
            DataAsset.asset_id != asset_id,
            DataAsset.approval_status == 'Approved'
        ).limit(5).all()
        related_assets = [a.to_dict() for a in similar_assets]
    
    return jsonify({
        'asset': asset_data,
        'compliance': compliance_details,
        'glossary_terms': glossary_terms,
        'lineage': lineage_data,
        'related_assets': related_assets,
        'approval_history': history
    })


@assets_bp.route('/<int:asset_id>', methods=['PUT'])
@asset_owner_or_admin_required
def update_asset(asset_id):
    """Update an existing asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Track changes for audit
    changes = {}
    
    # Update basic fields
    updateable_fields = [
        'asset_name', 'description', 'source_system', 'source_location',
        'schema_info', 'metadata', 'tags', 'is_public', 'is_sensitive', 'access_level'
    ]
    
    for field in updateable_fields:
        if field in data:
            old_value = getattr(asset, field)
            new_value = data[field]
            if old_value != new_value:
                changes[field] = {'old': old_value, 'new': new_value}
                setattr(asset, field, new_value)
    
    # Update foreign keys with validation
    if 'category_id' in data:
        if data['category_id'] != asset.category_id:
            if data['category_id']:
                category = Category.query.get(data['category_id'])
                if not category or not category.is_active:
                    return jsonify({'error': 'Invalid category'}), 400
            changes['category_id'] = {'old': asset.category_id, 'new': data['category_id']}
            asset.category_id = data['category_id']
    
    if 'report_type_id' in data:
        if data['report_type_id'] != asset.report_type_id:
            if data['report_type_id']:
                report_type = ReportType.query.get(data['report_type_id'])
                if not report_type or not report_type.is_active:
                    return jsonify({'error': 'Invalid report type'}), 400
            changes['report_type_id'] = {'old': asset.report_type_id, 'new': data['report_type_id']}
            asset.report_type_id = data['report_type_id']
    
    if 'owner_user_id' in data and data['owner_user_id'] != asset.owner_user_id:
        changes['owner_user_id'] = {'old': asset.owner_user_id, 'new': data['owner_user_id']}
        asset.owner_user_id = data['owner_user_id']
    
    # If significant changes, reset approval status
    significant_fields = ['asset_name', 'description', 'source_system', 'schema_info']
    has_significant_changes = any(field in changes for field in significant_fields)
    
    if has_significant_changes and asset.approval_status == 'Approved':
        changes['approval_status'] = {'old': 'Approved', 'new': 'Pending'}
        asset.approval_status = 'Pending'
    
    try:
        asset.updated_at = datetime.utcnow()
        
        # Log update
        if changes:
            ApprovalHistory.log_action(
                asset_id=asset.asset_id,
                action='updated',
                new_status=asset.approval_status,
                performed_by_user_id=get_current_user_id(),
                changes_summary=changes,
                comments=f"Asset updated with {len(changes)} field(s) changed"
            )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Asset updated successfully',
            'asset': asset.to_dict(),
            'changes': changes
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update asset {asset_id}: {e}")
        return jsonify({'error': 'Failed to update asset'}), 500


@assets_bp.route('/<int:asset_id>', methods=['DELETE'])
@asset_owner_or_admin_required
def delete_asset(asset_id):
    """Delete an asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    
    try:
        # Log deletion before removing
        ApprovalHistory.log_action(
            asset_id=asset.asset_id,
            action='deleted',
            new_status='Deleted',
            performed_by_user_id=get_current_user_id(),
            comments=f"Asset '{asset.asset_name}' deleted"
        )
        
        db.session.delete(asset)
        db.session.commit()
        
        return jsonify({'message': 'Asset deleted successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete asset {asset_id}: {e}")
        return jsonify({'error': 'Failed to delete asset'}), 500


@assets_bp.route('/<int:asset_id>/approve', methods=['POST'])
@admin_required
def approve_asset(asset_id):
    """Approve a pending asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    
    if asset.approval_status != 'Pending':
        return jsonify({'error': 'Asset is not pending approval'}), 400
    
    data = request.get_json() or {}
    
    try:
        asset.approval_status = 'Approved'
        asset.approved_by_user_id = get_current_user_id()
        asset.approval_date = datetime.utcnow()
        
        ApprovalHistory.log_action(
            asset_id=asset.asset_id,
            action='approved',
            previous_status='Pending',
            new_status='Approved',
            performed_by_user_id=get_current_user_id(),
            comments=data.get('comments', f"Asset '{asset.asset_name}' approved")
        )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Asset approved successfully',
            'asset': asset.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to approve asset {asset_id}: {e}")
        return jsonify({'error': 'Failed to approve asset'}), 500


@assets_bp.route('/<int:asset_id>/reject', methods=['POST'])
@admin_required
def reject_asset(asset_id):
    """Reject a pending asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    
    if asset.approval_status != 'Pending':
        return jsonify({'error': 'Asset is not pending approval'}), 400
    
    data = request.get_json()
    if not data or not data.get('reason'):
        return jsonify({'error': 'Rejection reason is required'}), 400
    
    try:
        asset.approval_status = 'Rejected'
        asset.rejection_reason = data['reason']
        asset.approved_by_user_id = get_current_user_id()
        asset.approval_date = datetime.utcnow()
        
        ApprovalHistory.log_action(
            asset_id=asset.asset_id,
            action='rejected',
            previous_status='Pending',
            new_status='Rejected',
            performed_by_user_id=get_current_user_id(),
            rejection_reason=data['reason'],
            comments=data.get('comments', f"Asset '{asset.asset_name}' rejected")
        )
        
        db.session.commit()
        
        return jsonify({
            'message': 'Asset rejected successfully',
            'asset': asset.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to reject asset {asset_id}: {e}")
        return jsonify({'error': 'Failed to reject asset'}), 500


@assets_bp.route('/pending', methods=['GET'])
@admin_required
def get_pending_assets():
    """Get all pending assets for admin review"""
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    pagination = DataAsset.query.filter_by(approval_status='Pending')\
        .order_by(DataAsset.submission_date.asc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    assets = [asset.to_dict() for asset in pagination.items]
    
    return jsonify({
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


@assets_bp.route('/<int:asset_id>/relationships', methods=['GET'])
@token_required
def get_asset_relationships(asset_id):
    """Get all relationships for an asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    relationships = asset.get_all_relationships()
    
    return jsonify({
        'relationships': [rel.to_dict() for rel in relationships]
    })


@assets_bp.route('/<int:asset_id>/relationships', methods=['POST'])
@asset_owner_or_admin_required
def create_asset_relationship(asset_id):
    """Create a new relationship for an asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    required_fields = ['relationship_type']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400
    
    try:
        if data.get('target_asset_id'):
            # Internal relationship
            target_asset = DataAsset.query.get(data['target_asset_id'])
            if not target_asset:
                return jsonify({'error': 'Target asset not found'}), 404
            
            relationship = AssetRelationship.create_internal_relationship(
                source_asset_id=asset_id,
                target_asset_id=data['target_asset_id'],
                relationship_type=data['relationship_type'],
                description=data.get('relationship_description'),
                created_by_user_id=get_current_user_id()
            )
        else:
            # External relationship
            if not all([data.get('external_system'), data.get('external_reference'), data.get('external_name')]):
                return jsonify({'error': 'External system, reference, and name are required for external relationships'}), 400
            
            relationship = AssetRelationship.create_external_relationship(
                source_asset_id=asset_id,
                external_system=data['external_system'],
                external_reference=data['external_reference'],
                external_name=data['external_name'],
                relationship_type=data['relationship_type'],
                description=data.get('relationship_description'),
                created_by_user_id=get_current_user_id()
            )
        
        db.session.add(relationship)
        db.session.commit()
        
        return jsonify({
            'message': 'Relationship created successfully',
            'relationship': relationship.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create relationship: {e}")
        return jsonify({'error': 'Failed to create relationship'}), 500