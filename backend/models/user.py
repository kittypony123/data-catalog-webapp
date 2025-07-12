from . import db
from datetime import datetime


class Role(db.Model):
    __tablename__ = "roles"

    role_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    role_name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    # Relationships
    users = db.relationship("User", backref="role", lazy="dynamic")

    def __repr__(self):
        return f"<Role {self.role_name}>"

    def to_dict(self):
        return {
            'role_id': self.role_id,
            'role_name': self.role_name,
            'description': self.description,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class User(db.Model):
    __tablename__ = "users"

    user_id = db.Column(db.String(255), primary_key=True)  # Entra ID Object ID
    display_name = db.Column(db.String(255), nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    role_id = db.Column(db.Integer, db.ForeignKey('roles.role_id'), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    owned_assets = db.relationship("DataAsset", foreign_keys="DataAsset.owner_user_id", backref="owner", lazy="dynamic")
    submitted_assets = db.relationship("DataAsset", foreign_keys="DataAsset.submitted_by_user_id", backref="submitter", lazy="dynamic")
    approved_assets = db.relationship("DataAsset", foreign_keys="DataAsset.approved_by_user_id", backref="approver", lazy="dynamic")
    favorites = db.relationship("UserFavorite", backref="user", lazy="dynamic", cascade="all, delete-orphan")
    team_memberships = db.relationship("TeamMember", backref="user", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User {self.display_name}>"

    def to_dict(self, include_sensitive=False):
        data = {
            'user_id': self.user_id,
            'display_name': self.display_name,
            'role': self.role.to_dict() if self.role else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None
        }
        
        if include_sensitive:
            data['email'] = self.email
            
        return data

    def has_permission(self, permission):
        """Check if user has specific permission based on role"""
        role_permissions = {
            'Admin': ['create', 'read', 'update', 'delete', 'approve', 'manage_users'],
            'Data Owner': ['create', 'read', 'update', 'delete'],
            'Contributor': ['create', 'read', 'update']
        }
        
        user_permissions = role_permissions.get(self.role.role_name, [])
        return permission in user_permissions

    def can_edit_asset(self, asset):
        """Check if user can edit a specific asset"""
        return (self.role.role_name == 'Admin' or 
                self.user_id == asset.owner_user_id or 
                self.user_id == asset.submitted_by_user_id)