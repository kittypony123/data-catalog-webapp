from flask import Blueprint, request, jsonify, current_app
from backend.models import db, DataField, FieldCompliance, ComplianceRequirement, DataAsset
from backend.utils.auth import token_required, admin_required, get_current_user_id
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_

field_compliance_bp = Blueprint('field_compliance', __name__)


@field_compliance_bp.route('/assets/<int:asset_id>/fields', methods=['POST'])
@token_required
def create_data_field(asset_id):
    """Create a new data field for an asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    required_fields = ['field_name']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'{field} is required'}), 400

    # Check for duplicate field name within asset
    existing_field = DataField.query.filter_by(
        asset_id=asset_id,
        field_name=data['field_name']
    ).first()
    
    if existing_field:
        return jsonify({'error': 'Field name already exists in this asset'}), 409

    try:
        field = DataField(
            asset_id=asset_id,
            field_name=data['field_name'],
            field_description=data.get('field_description'),
            data_type=data.get('data_type'),
            field_length=data.get('field_length'),
            is_nullable=data.get('is_nullable', True),
            is_primary_key=data.get('is_primary_key', False),
            is_foreign_key=data.get('is_foreign_key', False),
            data_classification=data.get('data_classification'),
            sensitivity_level=data.get('sensitivity_level', 'Medium'),
            contains_pii=data.get('contains_pii', False),
            contains_phi=data.get('contains_phi', False),
            contains_pci=data.get('contains_pci', False),
            business_name=data.get('business_name'),
            valid_values=data.get('valid_values'),
            validation_rules=data.get('validation_rules'),
            example_values=data.get('example_values'),
            source_field=data.get('source_field'),
            transformation_logic=data.get('transformation_logic'),
            created_by_user_id=get_current_user_id()
        )
        
        db.session.add(field)
        db.session.commit()
        
        current_app.logger.info(f"Data field created: {field.field_name} for asset {asset_id}")
        
        return jsonify({
            'message': 'Data field created successfully',
            'field': field.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create data field: {e}")
        return jsonify({'error': 'Failed to create data field'}), 500


@field_compliance_bp.route('/assets/<int:asset_id>/fields', methods=['GET'])
@token_required
def get_asset_fields(asset_id):
    """Get all data fields for an asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    
    # Parse query parameters
    include_compliance = request.args.get('include_compliance', 'false').lower() == 'true'
    sensitivity_filter = request.args.get('sensitivity')
    privacy_only = request.args.get('privacy_only', 'false').lower() == 'true'
    
    # Build query
    query = DataField.query.filter_by(asset_id=asset_id)
    
    # Apply filters
    if sensitivity_filter:
        query = query.filter(DataField.sensitivity_level == sensitivity_filter)
    
    if privacy_only:
        query = query.filter(
            or_(
                DataField.contains_pii == True,
                DataField.contains_phi == True,
                DataField.contains_pci == True
            )
        )
    
    fields = query.order_by(DataField.field_name).all()
    
    return jsonify({
        'fields': [field.to_dict(include_compliance=include_compliance) for field in fields],
        'total_fields': len(fields),
        'privacy_sensitive_count': len([f for f in fields if any([f.contains_pii, f.contains_phi, f.contains_pci])])
    })


@field_compliance_bp.route('/fields/<int:field_id>', methods=['GET'])
@token_required
def get_field_detail(field_id):
    """Get detailed information about a specific field"""
    field = DataField.query.get_or_404(field_id)
    
    # Get compliance details
    compliance_links = FieldCompliance.query.filter_by(field_id=field_id).all()
    
    field_data = field.to_dict(include_compliance=True)
    field_data['compliance_links'] = [link.to_dict() for link in compliance_links]
    field_data['privacy_flags'] = field.get_data_privacy_flags()
    
    return jsonify({
        'field': field_data
    })


@field_compliance_bp.route('/fields/<int:field_id>/compliance', methods=['POST'])
@token_required
def link_field_compliance(field_id):
    """Link a data field to a compliance requirement"""
    field = DataField.query.get_or_404(field_id)
    data = request.get_json()
    
    if not data or not data.get('compliance_id'):
        return jsonify({'error': 'Compliance ID is required'}), 400
    
    compliance_id = data['compliance_id']
    requirement = ComplianceRequirement.query.get_or_404(compliance_id)
    
    # Check if link already exists
    existing_link = FieldCompliance.query.filter_by(
        field_id=field_id,
        compliance_id=compliance_id
    ).first()
    
    if existing_link:
        return jsonify({'error': 'Field is already linked to this compliance requirement'}), 409

    try:
        field_compliance = FieldCompliance(
            field_id=field_id,
            compliance_id=compliance_id,
            compliance_status=data.get('compliance_status', 'Pending'),
            assessment_notes=data.get('assessment_notes'),
            risk_level=data.get('risk_level', 'Medium'),
            data_masking_required=data.get('data_masking_required', False),
            encryption_required=data.get('encryption_required', False),
            access_restrictions=data.get('access_restrictions'),
            retention_period=data.get('retention_period'),
            deletion_requirements=data.get('deletion_requirements'),
            validation_rules=data.get('validation_rules'),
            assessed_by_user_id=get_current_user_id()
        )
        
        # Set review date if provided
        if data.get('next_review_date'):
            field_compliance.next_review_date = datetime.fromisoformat(data['next_review_date'])
        
        db.session.add(field_compliance)
        db.session.commit()
        
        return jsonify({
            'message': 'Field linked to compliance requirement successfully',
            'field_compliance': field_compliance.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to link field compliance: {e}")
        return jsonify({'error': 'Failed to link field compliance'}), 500


@field_compliance_bp.route('/field-compliance/<int:field_compliance_id>', methods=['PUT'])
@token_required
def update_field_compliance(field_compliance_id):
    """Update field compliance status and details"""
    field_compliance = FieldCompliance.query.get_or_404(field_compliance_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Update compliance fields
        updateable_fields = [
            'compliance_status', 'assessment_notes', 'remediation_plan', 'risk_level',
            'data_masking_required', 'encryption_required', 'access_restrictions',
            'retention_period', 'deletion_requirements', 'evidence_location',
            'documentation_links', 'validation_rules'
        ]
        
        for field in updateable_fields:
            if field in data:
                setattr(field_compliance, field, data[field])
        
        # Handle date fields
        if 'next_review_date' in data:
            field_compliance.next_review_date = datetime.fromisoformat(data['next_review_date']) if data['next_review_date'] else None
        
        # Update assessment info
        field_compliance.assessment_date = datetime.utcnow()
        field_compliance.assessed_by_user_id = get_current_user_id()
        field_compliance.updated_at = datetime.utcnow()
        
        db.session.commit()
        
        return jsonify({
            'message': 'Field compliance updated successfully',
            'field_compliance': field_compliance.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update field compliance: {e}")
        return jsonify({'error': 'Failed to update field compliance'}), 500


@field_compliance_bp.route('/privacy-fields', methods=['GET'])
@token_required
def get_privacy_sensitive_fields():
    """Get all privacy-sensitive fields across all assets"""
    asset_id = request.args.get('asset_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Get privacy sensitive fields
    fields = DataField.get_privacy_sensitive_fields(asset_id=asset_id)
    
    # Manual pagination since we're using a custom query
    total = len(fields)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_fields = fields[start:end]
    
    field_data = []
    for field in paginated_fields:
        field_dict = field.to_dict(include_compliance=True)
        field_dict['asset_name'] = field.asset.asset_name
        field_dict['privacy_flags'] = field.get_data_privacy_flags()
        field_data.append(field_dict)
    
    return jsonify({
        'fields': field_data,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_next': end < total,
            'has_prev': page > 1
        }
    })


@field_compliance_bp.route('/overdue-field-reviews', methods=['GET'])
@token_required
def get_overdue_field_reviews():
    """Get fields with overdue compliance reviews"""
    asset_id = request.args.get('asset_id', type=int)
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    
    # Query overdue field reviews
    query = db.session.query(FieldCompliance, DataField, ComplianceRequirement)\
        .join(DataField, FieldCompliance.field_id == DataField.field_id)\
        .join(ComplianceRequirement, FieldCompliance.compliance_id == ComplianceRequirement.compliance_id)\
        .filter(
            and_(
                FieldCompliance.next_review_date.isnot(None),
                FieldCompliance.next_review_date < datetime.utcnow()
            )
        )
    
    if asset_id:
        query = query.filter(DataField.asset_id == asset_id)
        
    query = query.order_by(FieldCompliance.next_review_date.asc())
    
    # Paginate
    total = query.count()
    overdue_items = query.offset((page - 1) * per_page).limit(per_page).all()
    
    result_items = []
    for field_compliance, field, requirement in overdue_items:
        days_overdue = (datetime.utcnow() - field_compliance.next_review_date).days
        result_items.append({
            'field_compliance': field_compliance.to_dict(),
            'field': field.to_dict(),
            'requirement': requirement.to_dict(),
            'asset_name': field.asset.asset_name,
            'days_overdue': days_overdue
        })
    
    return jsonify({
        'overdue_field_reviews': result_items,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'pages': (total + per_page - 1) // per_page,
            'has_next': page * per_page < total,
            'has_prev': page > 1
        }
    })


@field_compliance_bp.route('/masking-requirements', methods=['GET'])
@token_required
def get_masking_requirements():
    """Get all fields that require data masking"""
    asset_id = request.args.get('asset_id', type=int)
    
    masking_fields = FieldCompliance.get_fields_requiring_masking(asset_id=asset_id)
    
    result = []
    for field_compliance in masking_fields:
        result.append({
            'field_compliance': field_compliance.to_dict(),
            'field': field_compliance.data_field.to_dict(),
            'asset_name': field_compliance.data_field.asset.asset_name,
            'requirement': field_compliance.compliance_requirement.to_dict()
        })
    
    return jsonify({
        'masking_requirements': result,
        'total_fields': len(result)
    })


@field_compliance_bp.route('/encryption-requirements', methods=['GET'])
@token_required
def get_encryption_requirements():
    """Get all fields that require encryption"""
    asset_id = request.args.get('asset_id', type=int)
    
    encryption_fields = FieldCompliance.get_fields_requiring_encryption(asset_id=asset_id)
    
    result = []
    for field_compliance in encryption_fields:
        result.append({
            'field_compliance': field_compliance.to_dict(),
            'field': field_compliance.data_field.to_dict(),
            'asset_name': field_compliance.data_field.asset.asset_name,
            'requirement': field_compliance.compliance_requirement.to_dict()
        })
    
    return jsonify({
        'encryption_requirements': result,
        'total_fields': len(result)
    })


@field_compliance_bp.route('/field-dashboard', methods=['GET'])
@token_required
def get_field_compliance_dashboard():
    """Get field-level compliance dashboard statistics"""
    try:
        asset_id = request.args.get('asset_id', type=int)
        
        # Base query filter
        base_filter = {}
        if asset_id:
            base_filter['asset_id'] = asset_id
            
        # Overall field statistics
        total_fields = DataField.query.filter_by(**base_filter).count() if asset_id else DataField.query.count()
        
        # Privacy sensitive fields
        privacy_fields = len(DataField.get_privacy_sensitive_fields(asset_id=asset_id))
        
        # Field compliance statistics
        field_compliance_query = FieldCompliance.query
        if asset_id:
            field_compliance_query = field_compliance_query.join(DataField).filter(DataField.asset_id == asset_id)
            
        total_field_compliance = field_compliance_query.count()
        
        # Compliance status breakdown
        status_breakdown = db.session.query(
            FieldCompliance.compliance_status,
            func.count(FieldCompliance.field_compliance_id).label('count')
        )
        
        if asset_id:
            status_breakdown = status_breakdown.join(DataField).filter(DataField.asset_id == asset_id)
            
        status_breakdown = status_breakdown.group_by(FieldCompliance.compliance_status).all()
        
        status_summary = {status: count for status, count in status_breakdown}
        
        # Sensitivity level breakdown
        sensitivity_breakdown = db.session.query(
            DataField.sensitivity_level,
            func.count(DataField.field_id).label('count')
        ).filter_by(**base_filter).group_by(DataField.sensitivity_level).all()
        
        sensitivity_summary = {level: count for level, count in sensitivity_breakdown}
        
        # Privacy data breakdown
        privacy_breakdown = {
            'pii_fields': DataField.query.filter_by(contains_pii=True, **base_filter).count(),
            'phi_fields': DataField.query.filter_by(contains_phi=True, **base_filter).count(),
            'pci_fields': DataField.query.filter_by(contains_pci=True, **base_filter).count()
        }
        
        # Masking and encryption requirements
        masking_required = len(FieldCompliance.get_fields_requiring_masking(asset_id=asset_id))
        encryption_required = len(FieldCompliance.get_fields_requiring_encryption(asset_id=asset_id))
        
        # Overdue field reviews
        overdue_field_reviews = len(FieldCompliance.get_overdue_field_reviews(asset_id=asset_id))
        
        return jsonify({
            'summary': {
                'total_fields': total_fields,
                'privacy_sensitive_fields': privacy_fields,
                'total_field_compliance': total_field_compliance,
                'masking_required': masking_required,
                'encryption_required': encryption_required,
                'overdue_field_reviews': overdue_field_reviews,
                'privacy_percentage': round((privacy_fields / total_fields * 100) if total_fields > 0 else 0, 1)
            },
            'compliance_status_breakdown': status_summary,
            'sensitivity_breakdown': sensitivity_summary,
            'privacy_breakdown': privacy_breakdown
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get field compliance dashboard: {e}")
        return jsonify({'error': 'Failed to get field compliance dashboard'}), 500


@field_compliance_bp.route('/bulk-import', methods=['POST'])
@token_required
def bulk_import_fields():
    """Bulk import data fields from schema information"""
    data = request.get_json()
    if not data or not data.get('asset_id'):
        return jsonify({'error': 'Asset ID is required'}), 400
    
    asset_id = data['asset_id']
    asset = DataAsset.query.get_or_404(asset_id)
    
    if not asset.schema_info:
        return jsonify({'error': 'Asset has no schema information to import'}), 400
    
    try:
        imported_fields = []
        schema_info = asset.schema_info
        
        # Handle different schema formats
        if isinstance(schema_info, dict) and 'columns' in schema_info:
            columns = schema_info['columns']
        elif isinstance(schema_info, list):
            columns = schema_info
        else:
            return jsonify({'error': 'Unsupported schema format'}), 400
        
        for column_info in columns:
            # Extract field information from schema
            if isinstance(column_info, dict):
                field_name = column_info.get('name') or column_info.get('column_name')
                data_type = column_info.get('type') or column_info.get('data_type')
                description = column_info.get('description') or column_info.get('comment')
                is_nullable = column_info.get('nullable', True)
                is_primary_key = column_info.get('primary_key', False)
            else:
                # Simple string format
                field_name = str(column_info)
                data_type = None
                description = None
                is_nullable = True
                is_primary_key = False
            
            if not field_name:
                continue
                
            # Check if field already exists
            existing_field = DataField.query.filter_by(
                asset_id=asset_id,
                field_name=field_name
            ).first()
            
            if existing_field:
                continue  # Skip existing fields
            
            # Auto-detect privacy sensitive data based on field names
            contains_pii = any(keyword in field_name.lower() for keyword in [
                'name', 'email', 'phone', 'address', 'ssn', 'social', 'passport', 'license'
            ])
            
            contains_phi = any(keyword in field_name.lower() for keyword in [
                'medical', 'health', 'diagnosis', 'treatment', 'patient', 'prescription'
            ])
            
            contains_pci = any(keyword in field_name.lower() for keyword in [
                'card', 'credit', 'payment', 'cvv', 'expiry', 'billing'
            ])
            
            # Set sensitivity level based on privacy flags
            if contains_phi or contains_pci:
                sensitivity_level = 'Critical'
            elif contains_pii:
                sensitivity_level = 'High'
            else:
                sensitivity_level = 'Medium'
            
            field = DataField(
                asset_id=asset_id,
                field_name=field_name,
                field_description=description,
                data_type=data_type,
                is_nullable=is_nullable,
                is_primary_key=is_primary_key,
                sensitivity_level=sensitivity_level,
                contains_pii=contains_pii,
                contains_phi=contains_phi,
                contains_pci=contains_pci,
                created_by_user_id=get_current_user_id()
            )
            
            db.session.add(field)
            imported_fields.append(field_name)
        
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully imported {len(imported_fields)} fields',
            'imported_fields': imported_fields
        })
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to bulk import fields: {e}")
        return jsonify({'error': 'Failed to bulk import fields'}), 500