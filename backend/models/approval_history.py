from . import db
from datetime import datetime


class ApprovalHistory(db.Model):
    __tablename__ = "approval_history"

    history_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    asset_id = db.Column(db.Integer, db.ForeignKey("data_assets.asset_id"), nullable=False)
    action = db.Column(db.String(50), nullable=False)  # submitted, approved, rejected, updated
    previous_status = db.Column(db.String(50), nullable=True)
    new_status = db.Column(db.String(50), nullable=False)
    comments = db.Column(db.Text, nullable=True)
    rejection_reason = db.Column(db.Text, nullable=True)
    
    # User information
    performed_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    performed_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Metadata changes (for tracking what was modified)
    changes_summary = db.Column(db.JSON, nullable=True)  # What fields were changed

    # Relationships
    performed_by = db.relationship("User", backref="approval_actions")

    def __repr__(self):
        return f"<ApprovalHistory {self.action} on Asset {self.asset_id}>"

    def to_dict(self):
        return {
            'history_id': self.history_id,
            'asset_id': self.asset_id,
            'action': self.action,
            'previous_status': self.previous_status,
            'new_status': self.new_status,
            'comments': self.comments,
            'rejection_reason': self.rejection_reason,
            'changes_summary': self.changes_summary,
            'performed_by': self.performed_by.to_dict() if self.performed_by else None,
            'performed_at': self.performed_at.isoformat() if self.performed_at else None
        }

    @classmethod
    def log_action(cls, asset_id, action, new_status, performed_by_user_id, 
                   previous_status=None, comments=None, rejection_reason=None, 
                   changes_summary=None):
        """Log an approval action"""
        history = cls(
            asset_id=asset_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            comments=comments,
            rejection_reason=rejection_reason,
            performed_by_user_id=performed_by_user_id,
            changes_summary=changes_summary
        )
        db.session.add(history)
        return history

    @classmethod
    def get_asset_history(cls, asset_id):
        """Get all history for a specific asset"""
        return cls.query.filter_by(asset_id=asset_id).order_by(cls.performed_at.desc()).all()

    @classmethod
    def get_user_actions(cls, user_id):
        """Get all actions performed by a specific user"""
        return cls.query.filter_by(performed_by_user_id=user_id).order_by(cls.performed_at.desc()).all()