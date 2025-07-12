from . import db
from datetime import datetime
from sqlalchemy import Index


class BusinessTerm(db.Model):
    __tablename__ = "business_terms"

    term_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    term_name = db.Column(db.String(255), nullable=False, unique=True)
    definition = db.Column(db.Text, nullable=False)
    context = db.Column(db.Text, nullable=True)  # Context where this term is used
    domain = db.Column(db.String(100), nullable=True)  # Business domain (Finance, Operations, etc.)
    synonyms = db.Column(db.JSON, nullable=True)  # Array of alternative terms
    related_terms = db.Column(db.JSON, nullable=True)  # Array of related term IDs
    examples = db.Column(db.JSON, nullable=True)  # Array of usage examples
    
    # Classification
    term_type = db.Column(db.String(50), default="Standard")  # Standard, Technical, Regulatory, Business
    sensitivity_level = db.Column(db.String(50), default="Public")  # Public, Internal, Confidential
    
    # Lifecycle management
    status = db.Column(db.String(50), default="Draft")  # Draft, Approved, Deprecated
    version = db.Column(db.String(20), default="1.0")
    approval_date = db.Column(db.DateTime, nullable=True)
    review_date = db.Column(db.DateTime, nullable=True)
    
    # Authority and governance
    business_owner = db.Column(db.String(255), nullable=True)  # Business owner name/role
    technical_owner = db.Column(db.String(255), nullable=True)  # Technical owner name/role
    authoritative_source = db.Column(db.String(255), nullable=True)  # Source system/document
    
    # Metadata
    created_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    approved_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    created_by = db.relationship("User", foreign_keys=[created_by_user_id], backref="created_terms")
    approved_by = db.relationship("User", foreign_keys=[approved_by_user_id], backref="approved_terms")
    
    # Indexes for search performance
    __table_args__ = (
        Index('idx_term_name', 'term_name'),
        Index('idx_domain_status', 'domain', 'status'),
        Index('idx_term_type', 'term_type'),
    )

    def __repr__(self):
        return f"<BusinessTerm {self.term_name}>"

    def to_dict(self, include_relationships=False):
        data = {
            'term_id': self.term_id,
            'term_name': self.term_name,
            'definition': self.definition,
            'context': self.context,
            'domain': self.domain,
            'synonyms': self.synonyms or [],
            'related_terms': self.related_terms or [],
            'examples': self.examples or [],
            'term_type': self.term_type,
            'sensitivity_level': self.sensitivity_level,
            'status': self.status,
            'version': self.version,
            'approval_date': self.approval_date.isoformat() if self.approval_date else None,
            'review_date': self.review_date.isoformat() if self.review_date else None,
            'business_owner': self.business_owner,
            'technical_owner': self.technical_owner,
            'authoritative_source': self.authoritative_source,
            'created_by': self.created_by.to_dict() if self.created_by else None,
            'approved_by': self.approved_by.to_dict() if self.approved_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
        
        if include_relationships:
            # Get related terms details
            if self.related_terms:
                related_term_objects = BusinessTerm.query.filter(
                    BusinessTerm.term_id.in_(self.related_terms)
                ).all()
                data['related_terms_details'] = [
                    {'term_id': t.term_id, 'term_name': t.term_name, 'definition': t.definition}
                    for t in related_term_objects
                ]
        
        return data

    @classmethod
    def search_terms(cls, query, domain=None, term_type=None, status="Approved"):
        """Search business terms with filters"""
        search_query = cls.query
        
        # Text search across term name, definition, and context
        if query:
            search_query = search_query.filter(
                db.or_(
                    cls.term_name.ilike(f'%{query}%'),
                    cls.definition.ilike(f'%{query}%'),
                    cls.context.ilike(f'%{query}%')
                )
            )
        
        # Apply filters
        if domain:
            search_query = search_query.filter(cls.domain == domain)
        if term_type:
            search_query = search_query.filter(cls.term_type == term_type)
        if status:
            search_query = search_query.filter(cls.status == status)
        
        return search_query.order_by(cls.term_name)

    def add_related_term(self, term_id):
        """Add a related term (bidirectional relationship)"""
        if not self.related_terms:
            self.related_terms = []
        
        if term_id not in self.related_terms:
            self.related_terms = self.related_terms + [term_id]
            
            # Add reverse relationship
            related_term = BusinessTerm.query.get(term_id)
            if related_term:
                if not related_term.related_terms:
                    related_term.related_terms = []
                if self.term_id not in related_term.related_terms:
                    related_term.related_terms = related_term.related_terms + [self.term_id]

    def remove_related_term(self, term_id):
        """Remove a related term (bidirectional)"""
        if self.related_terms and term_id in self.related_terms:
            self.related_terms = [t for t in self.related_terms if t != term_id]
            
            # Remove reverse relationship
            related_term = BusinessTerm.query.get(term_id)
            if related_term and related_term.related_terms and self.term_id in related_term.related_terms:
                related_term.related_terms = [t for t in related_term.related_terms if t != self.term_id]

    def get_usage_count(self):
        """Get count of data assets that reference this term"""
        # This would require implementing term linkage to data assets
        # For now, return 0 as placeholder
        return 0

    @classmethod
    def get_domain_statistics(cls):
        """Get statistics grouped by domain"""
        from sqlalchemy import func
        
        stats = db.session.query(
            cls.domain,
            func.count(cls.term_id).label('term_count'),
            func.count(db.case([(cls.status == 'Approved', 1)])).label('approved_count'),
            func.count(db.case([(cls.status == 'Draft', 1)])).label('draft_count')
        ).group_by(cls.domain).all()
        
        return [
            {
                'domain': stat.domain or 'Unspecified',
                'total_terms': stat.term_count,
                'approved_terms': stat.approved_count,
                'draft_terms': stat.draft_count
            }
            for stat in stats
        ]

    def needs_review(self):
        """Check if term needs review based on review date"""
        if not self.review_date:
            return False
        return datetime.utcnow() > self.review_date

    def days_since_last_update(self):
        """Get days since last update"""
        if not self.updated_at:
            return 0
        delta = datetime.utcnow() - self.updated_at
        return delta.days


class TermUsage(db.Model):
    """Track usage of business terms in data assets"""
    __tablename__ = "term_usage"

    usage_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    term_id = db.Column(db.Integer, db.ForeignKey("business_terms.term_id"), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=False)
    usage_context = db.Column(db.Text, nullable=True)  # Where/how the term is used
    confidence_score = db.Column(db.Float, nullable=True)  # 0.0-1.0 for automatic detection
    verified = db.Column(db.Boolean, default=False)  # Manual verification flag
    
    # Metadata
    created_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    term = db.relationship("BusinessTerm", backref="usages")
    asset = db.relationship("DataAsset", backref="term_usages")
    created_by = db.relationship("User", backref="created_term_usages")
    
    # Unique constraint
    __table_args__ = (
        db.UniqueConstraint('term_id', 'asset_id', name='unique_term_asset_usage'),
    )

    def __repr__(self):
        return f"<TermUsage Term:{self.term_id} Asset:{self.asset_id}>"

    def to_dict(self):
        return {
            'usage_id': self.usage_id,
            'term_id': self.term_id,
            'asset_id': self.asset_id,
            'usage_context': self.usage_context,
            'confidence_score': self.confidence_score,
            'verified': self.verified,
            'created_by': self.created_by.to_dict() if self.created_by else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'term': {
                'term_id': self.term.term_id,
                'term_name': self.term.term_name,
                'definition': self.term.definition
            } if self.term else None,
            'asset': {
                'asset_id': self.asset.asset_id,
                'asset_name': self.asset.asset_name
            } if self.asset else None
        }

    @classmethod
    def get_term_usage_statistics(cls, term_id):
        """Get usage statistics for a specific term"""
        total_usage = cls.query.filter_by(term_id=term_id).count()
        verified_usage = cls.query.filter_by(term_id=term_id, verified=True).count()
        
        return {
            'total_usage': total_usage,
            'verified_usage': verified_usage,
            'verification_rate': round((verified_usage / total_usage) * 100, 1) if total_usage > 0 else 0
        }