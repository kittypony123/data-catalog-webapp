from flask import Blueprint, request, jsonify, current_app
from werkzeug.utils import secure_filename
from backend.models import db, DataAsset
from backend.utils.auth import token_required, get_current_user_id
from backend.utils.excel_processor import ExcelDataProcessor
import os
from datetime import datetime

upload_bp = Blueprint('upload', __name__)


@upload_bp.route('/analyze', methods=['POST'])
@token_required
def analyze_file():
    """Analyze uploaded file and return metadata"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file extension
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    if file_ext not in current_app.config['ALLOWED_EXTENSIONS']:
        return jsonify({
            'error': f'File type not allowed. Supported formats: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}'
        }), 400
    
    try:
        # Save file temporarily
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        temp_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(upload_dir, temp_filename)
        
        file.save(file_path)
        
        # Analyze file
        processor = ExcelDataProcessor()
        
        # Validate file first
        is_valid, issues = processor.validate_file_for_import(file_path)
        if not is_valid:
            os.remove(file_path)  # Clean up
            return jsonify({
                'error': 'File validation failed',
                'issues': issues
            }), 400
        
        # Perform analysis
        analysis = processor.analyze_file(file_path)
        
        # Generate suggested asset metadata
        suggested_metadata = processor.generate_asset_metadata(analysis, filename.rsplit('.', 1)[0])
        
        # Clean up temporary file
        os.remove(file_path)
        
        return jsonify({
            'analysis': analysis,
            'suggested_metadata': suggested_metadata,
            'original_filename': filename
        })
    
    except Exception as e:
        # Clean up on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        current_app.logger.error(f"File analysis failed: {e}")
        return jsonify({'error': f'File analysis failed: {str(e)}'}), 500


@upload_bp.route('/import', methods=['POST'])
@token_required
def import_file_as_asset():
    """Import analyzed file as a data asset"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400
    
    # Re-upload and analyze file
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    try:
        # Save file permanently
        upload_dir = current_app.config['UPLOAD_FOLDER']
        os.makedirs(upload_dir, exist_ok=True)
        
        filename = secure_filename(file.filename)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        permanent_filename = f"{timestamp}_{filename}"
        file_path = os.path.join(upload_dir, permanent_filename)
        
        file.save(file_path)
        
        # Re-analyze to ensure consistency
        processor = ExcelDataProcessor()
        analysis = processor.analyze_file(file_path)
        
        # Create asset with provided metadata
        asset_data = data.get('asset_data', {})
        
        # Use analyzed data to fill in missing fields
        if not asset_data.get('asset_name'):
            asset_data['asset_name'] = filename.rsplit('.', 1)[0]
        
        if not asset_data.get('description'):
            asset_data['description'] = f"Data asset imported from {filename}"
        
        # Generate schema info from analysis
        schema_info = {
            'sheets': []
        }
        
        for sheet in analysis['sheets']:
            if 'error' in sheet:
                continue
            
            sheet_schema = {
                'name': sheet['name'],
                'columns': [
                    {
                        'name': col['name'],
                        'data_type': col['data_type'],
                        'nullable': col['null_count'] > 0,
                        'unique': col['is_unique'],
                        'contains_pii': col['contains_pii']
                    } for col in sheet['columns']
                ]
            }
            schema_info['sheets'].append(sheet_schema)
        
        # Calculate data quality score
        quality_scores = [sheet.get('data_quality', {}).get('completeness', 0) 
                         for sheet in analysis['sheets'] if 'error' not in sheet]
        data_quality_score = sum(quality_scores) / len(quality_scores) / 100 if quality_scores else 0
        
        # Check for PII
        contains_pii = any(col.get('contains_pii', False) for sheet in analysis['sheets'] 
                          for col in sheet.get('columns', []))
        
        # Create the asset
        asset = DataAsset(
            asset_name=asset_data['asset_name'],
            description=asset_data.get('description'),
            source_system='File Import',
            source_location=file_path,
            schema_info=schema_info,
            metadata={
                'file_analysis': analysis,
                'import_date': datetime.utcnow().isoformat(),
                'original_filename': filename,
                'row_count': analysis['total_rows'],
                'column_count': analysis['total_columns'],
                'sheet_count': len([s for s in analysis['sheets'] if 'error' not in s])
            },
            tags=asset_data.get('tags', []),
            report_type_id=asset_data.get('report_type_id'),
            category_id=asset_data.get('category_id'),
            owner_user_id=asset_data.get('owner_user_id', get_current_user_id()),
            submitted_by_user_id=get_current_user_id(),
            data_quality_score=round(data_quality_score, 3),
            is_sensitive=contains_pii or asset_data.get('is_sensitive', False),
            is_public=asset_data.get('is_public', False),
            access_level='Restricted' if contains_pii else asset_data.get('access_level', 'Internal')
        )
        
        db.session.add(asset)
        db.session.commit()
        
        current_app.logger.info(f"File imported as asset: {asset.asset_name} from {filename}")
        
        return jsonify({
            'message': 'File imported successfully as data asset',
            'asset': asset.to_dict(),
            'file_path': file_path
        }), 201
    
    except Exception as e:
        db.session.rollback()
        # Clean up file on error
        if 'file_path' in locals() and os.path.exists(file_path):
            os.remove(file_path)
        
        current_app.logger.error(f"File import failed: {e}")
        return jsonify({'error': f'File import failed: {str(e)}'}), 500


@upload_bp.route('/validate', methods=['POST'])
@token_required
def validate_file():
    """Validate file without full analysis"""
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    # Check file extension
    filename = secure_filename(file.filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    validation_result = {
        'filename': filename,
        'file_extension': file_ext,
        'is_valid': True,
        'issues': []
    }
    
    # Extension check
    if file_ext not in current_app.config['ALLOWED_EXTENSIONS']:
        validation_result['is_valid'] = False
        validation_result['issues'].append(
            f'File type not allowed. Supported formats: {", ".join(current_app.config["ALLOWED_EXTENSIONS"])}'
        )
    
    # Size check (if we can get it from the request)
    try:
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        max_size = current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024)
        if file_size > max_size:
            validation_result['is_valid'] = False
            validation_result['issues'].append(
                f'File too large: {file_size / 1024 / 1024:.1f}MB (max: {max_size / 1024 / 1024}MB)'
            )
        
        validation_result['file_size'] = file_size
        validation_result['file_size_mb'] = round(file_size / 1024 / 1024, 2)
    
    except:
        validation_result['issues'].append('Could not determine file size')
    
    return jsonify(validation_result)


@upload_bp.route('/formats', methods=['GET'])
@token_required
def get_supported_formats():
    """Get list of supported file formats"""
    return jsonify({
        'supported_formats': list(current_app.config['ALLOWED_EXTENSIONS']),
        'max_file_size_mb': current_app.config.get('MAX_CONTENT_LENGTH', 16 * 1024 * 1024) / 1024 / 1024,
        'upload_folder': current_app.config['UPLOAD_FOLDER']
    })