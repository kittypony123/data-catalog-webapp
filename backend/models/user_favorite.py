from . import db
from datetime import datetime


class UserFavorite(db.Model):
    __tablename__ = "user_favorites"

    favorite_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=False)
    notes = db.Column(db.Text, nullable=True)  # Personal notes about the asset
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('user_id', 'asset_id', name='unique_user_asset_favorite'),
    )

    def __repr__(self):
        return f"<UserFavorite User:{self.user_id} Asset:{self.asset_id}>"

    def to_dict(self):
        return {
            'favorite_id': self.favorite_id,
            'user_id': self.user_id,
            'asset_id': self.asset_id,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'asset': self.asset.to_dict() if self.asset else None
        }

    @classmethod
    def add_favorite(cls, user_id, asset_id, notes=None):
        """Add an asset to user's favorites"""
        # Check if already exists
        existing = cls.query.filter_by(user_id=user_id, asset_id=asset_id).first()
        if existing:
            return existing
        
        favorite = cls(
            user_id=user_id,
            asset_id=asset_id,
            notes=notes
        )
        db.session.add(favorite)
        return favorite

    @classmethod
    def remove_favorite(cls, user_id, asset_id):
        """Remove an asset from user's favorites"""
        favorite = cls.query.filter_by(user_id=user_id, asset_id=asset_id).first()
        if favorite:
            db.session.delete(favorite)
            return True
        return False

    @classmethod
    def get_user_favorites(cls, user_id):
        """Get all favorites for a user"""
        return cls.query.filter_by(user_id=user_id).order_by(cls.created_at.desc()).all()

    @classmethod
    def is_favorite(cls, user_id, asset_id):
        """Check if an asset is in user's favorites"""
        return cls.query.filter_by(user_id=user_id, asset_id=asset_id).first() is not None