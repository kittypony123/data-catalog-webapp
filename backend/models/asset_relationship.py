from . import db
from datetime import datetime


class AssetRelationship(db.Model):
    __tablename__ = "asset_relationships"

    relationship_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    source_asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=False)
    target_asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=True)
    
    # Relationship details
    relationship_type = db.Column(db.String(50), nullable=False)  # lineage_upstream, lineage_downstream, related_generic
    relationship_description = db.Column(db.Text, nullable=True)
    
    # External references (for assets outside the catalog)
    external_system = db.Column(db.String(255), nullable=True)  # Power BI, SQL Server, etc.
    external_reference = db.Column(db.Text, nullable=True)  # URL, connection string, etc.
    external_name = db.Column(db.String(255), nullable=True)  # Name of external asset
    
    # Metadata
    confidence_score = db.Column(db.Float, nullable=True)  # 0.0 - 1.0 for automated discovery
    is_automated = db.Column(db.Boolean, default=False)  # True if discovered automatically
    created_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by = db.relationship("User", backref="created_relationships")

    def __repr__(self):
        if self.target_asset_id:
            return f"<AssetRelationship {self.source_asset_id} -> {self.target_asset_id} ({self.relationship_type})>"
        else:
            return f"<AssetRelationship {self.source_asset_id} -> {self.external_name} ({self.relationship_type})>"

    def to_dict(self):
        return {
            'relationship_id': self.relationship_id,
            'source_asset_id': self.source_asset_id,
            'target_asset_id': self.target_asset_id,
            'relationship_type': self.relationship_type,
            'relationship_description': self.relationship_description,
            'external_system': self.external_system,
            'external_reference': self.external_reference,
            'external_name': self.external_name,
            'confidence_score': self.confidence_score,
            'is_automated': self.is_automated,
            'created_by': self.created_by.to_dict() if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'target_asset': self.target_asset.to_dict() if self.target_asset else None,
            'source_asset': self.source_asset.to_dict() if self.source_asset else None
        }

    @classmethod
    def create_internal_relationship(cls, source_asset_id, target_asset_id, relationship_type, 
                                   description=None, created_by_user_id=None):
        """Create relationship between two internal assets"""
        relationship = cls(
            source_asset_id=source_asset_id,
            target_asset_id=target_asset_id,
            relationship_type=relationship_type,
            relationship_description=description,
            created_by_user_id=created_by_user_id
        )
        return relationship

    @classmethod
    def create_external_relationship(cls, source_asset_id, external_system, external_reference,
                                   external_name, relationship_type, description=None, 
                                   created_by_user_id=None):
        """Create relationship to external asset"""
        relationship = cls(
            source_asset_id=source_asset_id,
            relationship_type=relationship_type,
            relationship_description=description,
            external_system=external_system,
            external_reference=external_reference,
            external_name=external_name,
            created_by_user_id=created_by_user_id
        )
        return relationship

    def is_external(self):
        """Check if this is an external relationship"""
        return self.target_asset_id is None and self.external_reference is not None