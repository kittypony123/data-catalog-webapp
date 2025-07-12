from . import db
from datetime import datetime


class Category(db.Model):
    __tablename__ = "categories"

    category_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    category_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    color_code = db.Column(db.String(7), nullable=True)  # Hex color for UI
    icon = db.Column(db.String(50), nullable=True)  # Icon name for UI
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    data_assets = db.relationship("DataAsset", backref="category", lazy="dynamic")

    def __repr__(self):
        return f"<Category {self.category_name}>"

    def to_dict(self):
        return {
            'category_id': self.category_id,
            'category_name': self.category_name,
            'description': self.description,
            'color_code': self.color_code,
            'icon': self.icon,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'asset_count': self.data_assets.filter_by(approval_status='Approved').count()
        }