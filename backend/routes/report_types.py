from flask import Blueprint, request, jsonify, current_app
from backend.models import db, ReportType
from backend.utils.auth import token_required, admin_required
from datetime import datetime

report_types_bp = Blueprint('report_types', __name__)


@report_types_bp.route('/', methods=['POST'])
@admin_required
def create_report_type():
    """Create a new report type"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    if not data.get('type_name'):
        return jsonify({'error': 'Type name is required'}), 400

    # Check for duplicate names
    existing = ReportType.query.filter_by(type_name=data['type_name']).first()
    if existing:
        return jsonify({'error': 'Report type with this name already exists'}), 409

    try:
        report_type = ReportType(
            type_name=data['type_name'],
            description=data.get('description'),
            template_schema=data.get('template_schema'),
            required_fields=data.get('required_fields'),
            color_code=data.get('color_code'),
            icon=data.get('icon'),
            is_active=data.get('is_active', True)
        )
        
        db.session.add(report_type)
        db.session.commit()
        
        current_app.logger.info(f"Report type created: {report_type.type_name}")
        
        return jsonify({
            'message': 'Report type created successfully',
            'report_type': report_type.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create report type: {e}")
        return jsonify({'error': 'Failed to create report type'}), 500


@report_types_bp.route('/', methods=['GET'])
@token_required
def get_report_types():
    """Get all report types"""
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    query = ReportType.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
    
    report_types = query.order_by(ReportType.type_name).all()
    
    return jsonify({
        'report_types': [rt.to_dict() for rt in report_types]
    })


@report_types_bp.route('/<int:report_type_id>', methods=['GET'])
@token_required
def get_report_type(report_type_id):
    """Get specific report type"""
    report_type = ReportType.query.get_or_404(report_type_id)
    
    return jsonify({
        'report_type': report_type.to_dict()
    })


@report_types_bp.route('/<int:report_type_id>', methods=['PUT'])
@admin_required
def update_report_type(report_type_id):
    """Update an existing report type"""
    report_type = ReportType.query.get_or_404(report_type_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Check for duplicate names (excluding current report type)
        if 'type_name' in data and data['type_name'] != report_type.type_name:
            existing = ReportType.query.filter(
                ReportType.report_type_id != report_type_id,
                ReportType.type_name == data['type_name']
            ).first()
            
            if existing:
                return jsonify({'error': 'Report type with this name already exists'}), 409
            
            report_type.type_name = data['type_name']
        
        # Update other fields
        updateable_fields = [
            'description', 'template_schema', 'required_fields', 
            'color_code', 'icon', 'is_active'
        ]
        for field in updateable_fields:
            if field in data:
                setattr(report_type, field, data[field])
        
        report_type.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Report type updated successfully',
            'report_type': report_type.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update report type {report_type_id}: {e}")
        return jsonify({'error': 'Failed to update report type'}), 500


@report_types_bp.route('/<int:report_type_id>', methods=['DELETE'])
@admin_required
def delete_report_type(report_type_id):
    """Delete a report type (soft delete by marking inactive)"""
    report_type = ReportType.query.get_or_404(report_type_id)
    
    # Check if report type is in use
    if report_type.data_assets.count() > 0:
        return jsonify({
            'error': 'Cannot delete report type that is in use by data assets',
            'asset_count': report_type.data_assets.count()
        }), 400
    
    try:
        # Soft delete by marking as inactive
        report_type.is_active = False
        report_type.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Report type deleted successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete report type {report_type_id}: {e}")
        return jsonify({'error': 'Failed to delete report type'}), 500


@report_types_bp.route('/<int:report_type_id>/assets', methods=['GET'])
@token_required
def get_report_type_assets(report_type_id):
    """Get all assets of a specific report type"""
    report_type = ReportType.query.get_or_404(report_type_id)
    
    # Parse query parameters
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    status = request.args.get('status', 'Approved')
    
    # Query assets of this report type
    query = report_type.data_assets
    if status:
        query = query.filter_by(approval_status=status)
    
    pagination = query.order_by(report_type.data_assets.model.created_at.desc())\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    assets = [asset.to_dict() for asset in pagination.items]
    
    return jsonify({
        'report_type': report_type.to_dict(),
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


@report_types_bp.route('/<int:report_type_id>/validate', methods=['POST'])
@token_required
def validate_asset_data(report_type_id):
    """Validate asset data against report type requirements"""
    report_type = ReportType.query.get_or_404(report_type_id)
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    is_valid, missing_fields = report_type.validate_asset_data(data)
    
    return jsonify({
        'is_valid': is_valid,
        'missing_fields': missing_fields,
        'required_fields': report_type.required_fields or [],
        'template_schema': report_type.template_schema
    })


@report_types_bp.route('/stats', methods=['GET'])
@token_required
def get_report_type_stats():
    """Get statistics for all report types"""
    report_types = ReportType.query.filter_by(is_active=True).all()
    
    stats = []
    for rt in report_types:
        approved_count = rt.data_assets.filter_by(approval_status='Approved').count()
        pending_count = rt.data_assets.filter_by(approval_status='Pending').count()
        total_count = rt.data_assets.count()
        
        stats.append({
            'report_type': rt.to_dict(),
            'asset_counts': {
                'approved': approved_count,
                'pending': pending_count,
                'total': total_count
            }
        })
    
    return jsonify({
        'report_type_stats': stats,
        'total_report_types': len(stats)
    })