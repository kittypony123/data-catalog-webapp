from . import db
from datetime import datetime


class ReportType(db.Model):
    __tablename__ = "report_types"

    report_type_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    type_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    template_schema = db.Column(db.JSON, nullable=True)  # JSON schema for template
    required_fields = db.Column(db.JSON, nullable=True)  # List of required metadata fields
    color_code = db.Column(db.String(7), nullable=True)  # Hex color for UI
    icon = db.Column(db.String(50), nullable=True)  # Icon name for UI
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    data_assets = db.relationship("DataAsset", backref="report_type", lazy="dynamic")

    def __repr__(self):
        return f"<ReportType {self.type_name}>"

    def to_dict(self):
        return {
            'report_type_id': self.report_type_id,
            'type_name': self.type_name,
            'description': self.description,
            'template_schema': self.template_schema,
            'required_fields': self.required_fields,
            'color_code': self.color_code,
            'icon': self.icon,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'asset_count': self.data_assets.filter_by(approval_status='Approved').count()
        }

    def validate_asset_data(self, asset_data):
        """Validate asset data against report type requirements"""
        if not self.required_fields:
            return True, []
        
        missing_fields = []
        for field in self.required_fields:
            if field not in asset_data or not asset_data[field]:
                missing_fields.append(field)
        
        return len(missing_fields) == 0, missing_fields