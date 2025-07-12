from . import db
from datetime import datetime


class DataField(db.Model):
    """Model to represent individual data fields/columns within an asset"""
    __tablename__ = "data_fields"

    field_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=False)
    field_name = db.Column(db.String(255), nullable=False)
    field_description = db.Column(db.Text, nullable=True)
    data_type = db.Column(db.String(100), nullable=True)  # String, Integer, Date, etc.
    field_length = db.Column(db.Integer, nullable=True)
    is_nullable = db.Column(db.Boolean, default=True)
    is_primary_key = db.Column(db.Boolean, default=False)
    is_foreign_key = db.Column(db.Boolean, default=False)
    
    # Data classification
    data_classification = db.Column(db.String(50), nullable=True)  # Public, Internal, Confidential, Restricted
    sensitivity_level = db.Column(db.String(50), nullable=True)  # Low, Medium, High, Critical
    contains_pii = db.Column(db.Boolean, default=False)  # Personally Identifiable Information
    contains_phi = db.Column(db.Boolean, default=False)  # Protected Health Information
    contains_pci = db.Column(db.Boolean, default=False)  # Payment Card Industry data
    
    # Field metadata
    business_name = db.Column(db.String(255), nullable=True)  # Business-friendly name
    valid_values = db.Column(db.JSON, nullable=True)  # Array of valid values for enumerated fields
    validation_rules = db.Column(db.JSON, nullable=True)  # Validation rules and constraints
    example_values = db.Column(db.JSON, nullable=True)  # Sample values (anonymized)
    
    # Lineage and relationships
    source_field = db.Column(db.String(500), nullable=True)  # Original source field reference
    transformation_logic = db.Column(db.Text, nullable=True)  # How this field is derived
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    
    # Relationships
    asset = db.relationship("DataAsset", backref="data_fields")
    created_by = db.relationship("User", backref="created_fields")
    field_compliance = db.relationship("FieldCompliance", backref="data_field", lazy="dynamic", cascade="all, delete-orphan")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'field_name', name='unique_asset_field'),
        db.Index('idx_field_classification', 'data_classification'),
        db.Index('idx_field_sensitivity', 'sensitivity_level'),
        db.Index('idx_field_pii', 'contains_pii'),
    )

    def __repr__(self):
        return f"<DataField {self.field_name} in Asset:{self.asset_id}>"

    def to_dict(self, include_compliance=False):
        data = {
            'field_id': self.field_id,
            'asset_id': self.asset_id,
            'field_name': self.field_name,
            'field_description': self.field_description,
            'data_type': self.data_type,
            'field_length': self.field_length,
            'is_nullable': self.is_nullable,
            'is_primary_key': self.is_primary_key,
            'is_foreign_key': self.is_foreign_key,
            'data_classification': self.data_classification,
            'sensitivity_level': self.sensitivity_level,
            'contains_pii': self.contains_pii,
            'contains_phi': self.contains_phi,
            'contains_pci': self.contains_pci,
            'business_name': self.business_name,
            'valid_values': self.valid_values,
            'validation_rules': self.validation_rules,
            'example_values': self.example_values,
            'source_field': self.source_field,
            'transformation_logic': self.transformation_logic,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'created_by': self.created_by.to_dict() if self.created_by else None
        }
        
        if include_compliance:
            data['compliance_details'] = [comp.to_dict() for comp in self.field_compliance]
            data['compliance_summary'] = self.get_compliance_summary()
            data['risk_score'] = self.get_risk_score()
            
        return data

    def get_compliance_summary(self):
        """Get compliance summary for this field"""
        compliance_links = self.field_compliance.all()
        
        if not compliance_links:
            return {'total': 0, 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'not_applicable': 0}
        
        summary = {'total': len(compliance_links), 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'not_applicable': 0}
        
        for link in compliance_links:
            status_key = link.compliance_status.lower().replace('-', '_').replace(' ', '_')
            if status_key in summary:
                summary[status_key] += 1
        
        return summary

    def get_risk_score(self):
        """Calculate risk score for this field based on sensitivity and compliance"""
        base_score = 0
        
        # Data sensitivity risk (50% weight)
        sensitivity_scores = {
            'Low': 10,
            'Medium': 30,
            'High': 60,
            'Critical': 90
        }
        base_score += sensitivity_scores.get(self.sensitivity_level, 20) * 0.5
        
        # PII/PHI/PCI risk (30% weight)
        if self.contains_pii or self.contains_phi or self.contains_pci:
            base_score += 70 * 0.3
        
        # Compliance risk (20% weight)
        compliance_summary = self.get_compliance_summary()
        if compliance_summary['total'] > 0:
            non_compliant_ratio = compliance_summary['non_compliant'] / compliance_summary['total']
            base_score += non_compliant_ratio * 100 * 0.2
        
        return min(100, max(0, round(base_score, 1)))

    def get_data_privacy_flags(self):
        """Get all data privacy flags for this field"""
        flags = []
        if self.contains_pii:
            flags.append('PII')
        if self.contains_phi:
            flags.append('PHI')
        if self.contains_pci:
            flags.append('PCI')
        return flags

    @classmethod
    def get_fields_by_sensitivity(cls, sensitivity_level):
        """Get all fields with specific sensitivity level"""
        return cls.query.filter_by(sensitivity_level=sensitivity_level).all()

    @classmethod
    def get_privacy_sensitive_fields(cls, asset_id=None):
        """Get all fields containing PII, PHI, or PCI data"""
        query = cls.query.filter(
            db.or_(
                cls.contains_pii == True,
                cls.contains_phi == True,
                cls.contains_pci == True
            )
        )
        
        if asset_id:
            query = query.filter_by(asset_id=asset_id)
            
        return query.all()


class FieldCompliance(db.Model):
    """Model to track compliance requirements for individual data fields"""
    __tablename__ = "field_compliance"

    field_compliance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    field_id = db.Column(db.Integer, db.ForeignKey("data_fields.field_id"), nullable=False)
    compliance_id = db.Column(db.Integer, db.ForeignKey("compliance_requirements.compliance_id"), nullable=False)
    
    # Compliance status
    compliance_status = db.Column(db.String(50), default="Pending")  # Compliant, Non-Compliant, Pending, Not Applicable
    assessment_date = db.Column(db.DateTime, nullable=True)
    next_review_date = db.Column(db.DateTime, nullable=True)
    
    # Field-specific compliance details
    assessed_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    assessment_notes = db.Column(db.Text, nullable=True)
    remediation_plan = db.Column(db.Text, nullable=True)
    risk_level = db.Column(db.String(50), default="Medium")  # Critical, High, Medium, Low
    
    # Field-specific compliance attributes
    data_masking_required = db.Column(db.Boolean, default=False)
    encryption_required = db.Column(db.Boolean, default=False)
    access_restrictions = db.Column(db.JSON, nullable=True)  # Array of access control rules
    retention_period = db.Column(db.String(100), nullable=True)  # e.g., "7 years", "indefinite"
    deletion_requirements = db.Column(db.Text, nullable=True)
    
    # Evidence and documentation
    evidence_location = db.Column(db.Text, nullable=True)
    documentation_links = db.Column(db.JSON, nullable=True)
    validation_rules = db.Column(db.JSON, nullable=True)  # Compliance validation rules
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    compliance_requirement = db.relationship("ComplianceRequirement", backref="field_compliance_links")
    assessed_by = db.relationship("User", backref="field_compliance_assessments")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('field_id', 'compliance_id', name='unique_field_compliance'),
        db.Index('idx_field_compliance_status', 'compliance_status'),
        db.Index('idx_field_review_date', 'next_review_date'),
    )

    def __repr__(self):
        return f"<FieldCompliance Field:{self.field_id} Compliance:{self.compliance_id} Status:{self.compliance_status}>"

    def to_dict(self):
        return {
            'field_compliance_id': self.field_compliance_id,
            'field_id': self.field_id,
            'compliance_id': self.compliance_id,
            'compliance_status': self.compliance_status,
            'assessment_date': self.assessment_date.isoformat() if self.assessment_date else None,
            'next_review_date': self.next_review_date.isoformat() if self.next_review_date else None,
            'assessed_by': self.assessed_by.to_dict() if self.assessed_by else None,
            'assessment_notes': self.assessment_notes,
            'remediation_plan': self.remediation_plan,
            'risk_level': self.risk_level,
            'data_masking_required': self.data_masking_required,
            'encryption_required': self.encryption_required,
            'access_restrictions': self.access_restrictions,
            'retention_period': self.retention_period,
            'deletion_requirements': self.deletion_requirements,
            'evidence_location': self.evidence_location,
            'documentation_links': self.documentation_links,
            'validation_rules': self.validation_rules,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'data_field': self.data_field.to_dict() if self.data_field else None,
            'compliance_requirement': self.compliance_requirement.to_dict() if self.compliance_requirement else None
        }

    def is_overdue(self):
        """Check if field compliance review is overdue"""
        if not self.next_review_date:
            return False
        return datetime.utcnow() > self.next_review_date

    def days_until_review(self):
        """Get days until next review"""
        if not self.next_review_date:
            return None
        delta = self.next_review_date - datetime.utcnow()
        return delta.days

    @classmethod
    def get_overdue_field_reviews(cls, asset_id=None):
        """Get all overdue field compliance reviews"""
        query = cls.query.filter(
            db.and_(
                cls.next_review_date.isnot(None),
                cls.next_review_date < datetime.utcnow()
            )
        )
        
        if asset_id:
            query = query.join(DataField).filter(DataField.asset_id == asset_id)
            
        return query.all()

    @classmethod
    def get_fields_requiring_masking(cls, asset_id=None):
        """Get all fields that require data masking"""
        query = cls.query.filter_by(data_masking_required=True)
        
        if asset_id:
            query = query.join(DataField).filter(DataField.asset_id == asset_id)
            
        return query.all()

    @classmethod
    def get_fields_requiring_encryption(cls, asset_id=None):
        """Get all fields that require encryption"""
        query = cls.query.filter_by(encryption_required=True)
        
        if asset_id:
            query = query.join(DataField).filter(DataField.asset_id == asset_id)
            
        return query.all()