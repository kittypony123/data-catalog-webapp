from . import db
from datetime import datetime


class ComplianceRequirement(db.Model):
    __tablename__ = "compliance_requirements"

    compliance_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    requirement_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    regulatory_body = db.Column(db.String(255), nullable=False)  # e.g., GDPR, CCPA, PCI-DSS
    regulation_reference = db.Column(db.String(255), nullable=True)  # Article/Section reference
    requirement_type = db.Column(db.String(100), nullable=False)  # Data Protection, Financial, Security, etc.
    severity_level = db.Column(db.String(50), default="Medium")  # Critical, High, Medium, Low
    review_frequency = db.Column(db.String(50), nullable=True)  # Annual, Quarterly, Monthly
    implementation_guidance = db.Column(db.Text, nullable=True)
    
    # Compliance details
    effective_date = db.Column(db.Date, nullable=True)
    expiry_date = db.Column(db.Date, nullable=True)
    status = db.Column(db.String(50), default="Active")  # Active, Deprecated, Draft
    
    # Metadata
    created_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by = db.relationship("User", backref="created_compliance_requirements")
    asset_compliance = db.relationship("AssetCompliance", backref="compliance_requirement", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<ComplianceRequirement {self.requirement_name}>"

    def to_dict(self):
        return {
            'compliance_id': self.compliance_id,
            'requirement_name': self.requirement_name,
            'description': self.description,
            'regulatory_body': self.regulatory_body,
            'regulation_reference': self.regulation_reference,
            'requirement_type': self.requirement_type,
            'severity_level': self.severity_level,
            'review_frequency': self.review_frequency,
            'implementation_guidance': self.implementation_guidance,
            'effective_date': self.effective_date.isoformat() if self.effective_date else None,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'status': self.status,
            'created_by': self.created_by.to_dict() if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'linked_assets_count': self.asset_compliance.count()
        }

    def get_compliance_summary(self):
        """Get summary of compliance status across linked assets"""
        total_assets = self.asset_compliance.count()
        if total_assets == 0:
            return {'total': 0, 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'percentage': 0}
        
        compliant = self.asset_compliance.filter_by(compliance_status='Compliant').count()
        non_compliant = self.asset_compliance.filter_by(compliance_status='Non-Compliant').count()
        pending = self.asset_compliance.filter_by(compliance_status='Pending').count()
        
        return {
            'total': total_assets,
            'compliant': compliant,
            'non_compliant': non_compliant,
            'pending': pending,
            'percentage': round((compliant / total_assets) * 100, 1) if total_assets > 0 else 0
        }


class AssetCompliance(db.Model):
    __tablename__ = "asset_compliance"

    compliance_link_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=False)
    compliance_id = db.Column(db.Integer, db.ForeignKey("compliance_requirements.compliance_id"), nullable=False)
    
    # Compliance status
    compliance_status = db.Column(db.String(50), default="Pending")  # Compliant, Non-Compliant, Pending, Not Applicable
    assessment_date = db.Column(db.DateTime, nullable=True)
    next_review_date = db.Column(db.DateTime, nullable=True)
    
    # Assessment details
    assessed_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    assessment_notes = db.Column(db.Text, nullable=True)
    remediation_plan = db.Column(db.Text, nullable=True)
    risk_level = db.Column(db.String(50), default="Medium")  # Critical, High, Medium, Low
    
    # Evidence and documentation
    evidence_location = db.Column(db.Text, nullable=True)  # Path to evidence files
    documentation_links = db.Column(db.JSON, nullable=True)  # Array of URLs/references
    
    # Metadata
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    asset = db.relationship("DataAsset", backref="compliance_links")
    assessed_by = db.relationship("User", backref="compliance_assessments")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('asset_id', 'compliance_id', name='unique_asset_compliance'),
    )

    def __repr__(self):
        return f"<AssetCompliance Asset:{self.asset_id} Compliance:{self.compliance_id} Status:{self.compliance_status}>"

    def to_dict(self):
        return {
            'compliance_link_id': self.compliance_link_id,
            'asset_id': self.asset_id,
            'compliance_id': self.compliance_id,
            'compliance_status': self.compliance_status,
            'assessment_date': self.assessment_date.isoformat() if self.assessment_date else None,
            'next_review_date': self.next_review_date.isoformat() if self.next_review_date else None,
            'assessed_by': self.assessed_by.to_dict() if self.assessed_by else None,
            'assessment_notes': self.assessment_notes,
            'remediation_plan': self.remediation_plan,
            'risk_level': self.risk_level,
            'evidence_location': self.evidence_location,
            'documentation_links': self.documentation_links,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'asset': self.asset.to_dict() if self.asset else None,
            'compliance_requirement': self.compliance_requirement.to_dict() if self.compliance_requirement else None
        }

    @classmethod
    def get_compliance_summary_by_asset(cls, asset_id):
        """Get compliance summary for a specific asset"""
        compliance_links = cls.query.filter_by(asset_id=asset_id).all()
        
        if not compliance_links:
            return {'total': 0, 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'not_applicable': 0}
        
        summary = {'total': len(compliance_links), 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'not_applicable': 0}
        
        for link in compliance_links:
            status_key = link.compliance_status.lower().replace('-', '_').replace(' ', '_')
            if status_key in summary:
                summary[status_key] += 1
        
        return summary

    @classmethod
    def get_compliance_summary_by_requirement(cls, compliance_id):
        """Get compliance summary for a specific requirement"""
        compliance_links = cls.query.filter_by(compliance_id=compliance_id).all()
        
        if not compliance_links:
            return {'total': 0, 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'not_applicable': 0}
        
        summary = {'total': len(compliance_links), 'compliant': 0, 'non_compliant': 0, 'pending': 0, 'not_applicable': 0}
        
        for link in compliance_links:
            status_key = link.compliance_status.lower().replace('-', '_').replace(' ', '_')
            if status_key in summary:
                summary[status_key] += 1
        
        return summary

    def is_overdue(self):
        """Check if compliance review is overdue"""
        if not self.next_review_date:
            return False
        return datetime.utcnow() > self.next_review_date

    def days_until_review(self):
        """Get days until next review"""
        if not self.next_review_date:
            return None
        delta = self.next_review_date - datetime.utcnow()
        return delta.days