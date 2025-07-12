from . import db
from datetime import datetime
from sqlalchemy import Index


class DataAsset(db.Model):
    __tablename__ = "data_assets"

    asset_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text, nullable=True)
    source_system = db.Column(db.String(255), nullable=True)
    source_location = db.Column(db.Text, nullable=True)  # File path, URL, or connection string
    schema_info = db.Column(db.JSON, nullable=True)  # Column definitions, data types, etc.
    metadata = db.Column(db.JSON, nullable=True)  # Flexible metadata storage
    tags = db.Column(db.JSON, nullable=True)  # Array of tags for search
    
    # Foreign Keys
    report_type_id = db.Column(db.Integer, db.ForeignKey("report_types.report_type_id"), nullable=True)
    category_id = db.Column(db.Integer, db.ForeignKey("categories.category_id"), nullable=True)
    owner_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    submitted_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    approved_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    
    # Status and Workflow
    approval_status = db.Column(db.String(50), default="Pending", nullable=False)  # Pending, Approved, Rejected
    rejection_reason = db.Column(db.Text, nullable=True)
    data_quality_score = db.Column(db.Float, nullable=True)  # 0.0 - 1.0
    compliance_status = db.Column(db.String(50), default="Unknown", nullable=True)  # Compliant, Non-Compliant, Pending, Unknown
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    submission_date = db.Column(db.DateTime, default=datetime.utcnow)
    approval_date = db.Column(db.DateTime, nullable=True)
    last_accessed = db.Column(db.DateTime, nullable=True)
    
    # Access Control
    is_public = db.Column(db.Boolean, default=False)
    is_sensitive = db.Column(db.Boolean, default=False)
    access_level = db.Column(db.String(50), default="Internal")  # Public, Internal, Restricted, Confidential

    # Relationships
    upstream_relationships = db.relationship(
        "AssetRelationship", 
        foreign_keys="AssetRelationship.target_asset_id",
        backref="target_asset",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    downstream_relationships = db.relationship(
        "AssetRelationship",
        foreign_keys="AssetRelationship.source_asset_id", 
        backref="source_asset",
        lazy="dynamic",
        cascade="all, delete-orphan"
    )
    approval_history = db.relationship("ApprovalHistory", backref="asset", lazy="dynamic", cascade="all, delete-orphan")
    user_favorites = db.relationship("UserFavorite", backref="asset", lazy="dynamic", cascade="all, delete-orphan")

    # Indexes for performance
    __table_args__ = (
        Index('idx_asset_name', 'asset_name'),
        Index('idx_approval_status', 'approval_status'),
        Index('idx_created_at', 'created_at'),
        Index('idx_category_status', 'category_id', 'approval_status'),
        Index('idx_owner_status', 'owner_user_id', 'approval_status'),
    )

    def __repr__(self):
        return f"<DataAsset {self.asset_name}>"

    def to_dict(self, include_relationships=False):
        data = {
            'asset_id': self.asset_id,
            'asset_name': self.asset_name,
            'description': self.description,
            'source_system': self.source_system,
            'source_location': self.source_location,
            'schema_info': self.schema_info,
            'metadata': self.metadata,
            'tags': self.tags,
            'approval_status': self.approval_status,
            'rejection_reason': self.rejection_reason,
            'data_quality_score': self.data_quality_score,
            'compliance_status': self.compliance_status,
            'is_public': self.is_public,
            'is_sensitive': self.is_sensitive,
            'access_level': self.access_level,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'submission_date': self.submission_date.isoformat() if self.submission_date else None,
            'approval_date': self.approval_date.isoformat() if self.approval_date else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'category': self.category.to_dict() if self.category else None,
            'report_type': self.report_type.to_dict() if self.report_type else None,
            'owner': self.owner.to_dict() if self.owner else None,
            'submitter': self.submitter.to_dict() if self.submitter else None,
            'approver': self.approver.to_dict() if self.approver else None
        }
        
        if include_relationships:
            data['upstream_assets'] = [rel.to_dict() for rel in self.upstream_relationships]
            data['downstream_assets'] = [rel.to_dict() for rel in self.downstream_relationships]
            
        return data

    def get_all_relationships(self):
        """Get all upstream and downstream relationships"""
        upstream = list(self.upstream_relationships)
        downstream = list(self.downstream_relationships)
        return upstream + downstream

    def is_editable_by(self, user):
        """Check if asset can be edited by given user"""
        return (user.role.role_name == 'Admin' or 
                user.user_id == self.owner_user_id or 
                user.user_id == self.submitted_by_user_id)

    def update_last_accessed(self):
        """Update last accessed timestamp"""
        self.last_accessed = datetime.utcnow()
        db.session.commit()

    @classmethod
    def search(cls, query, filters=None):
        """Search assets with filters"""
        search_query = cls.query
        
        # Text search across multiple fields
        if query:
            search_query = search_query.filter(
                db.or_(
                    cls.asset_name.ilike(f'%{query}%'),
                    cls.description.ilike(f'%{query}%'),
                    cls.source_system.ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if filters:
            if filters.get('category_id'):
                search_query = search_query.filter(cls.category_id == filters['category_id'])
            if filters.get('report_type_id'):
                search_query = search_query.filter(cls.report_type_id == filters['report_type_id'])
            if filters.get('approval_status'):
                search_query = search_query.filter(cls.approval_status == filters['approval_status'])
            if filters.get('owner_user_id'):
                search_query = search_query.filter(cls.owner_user_id == filters['owner_user_id'])
            if filters.get('is_public') is not None:
                search_query = search_query.filter(cls.is_public == filters['is_public'])
        
        return search_query