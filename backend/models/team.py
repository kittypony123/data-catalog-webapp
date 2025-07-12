from . import db
from datetime import datetime


class Team(db.Model):
    __tablename__ = "teams"

    team_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_name = db.Column(db.String(100), nullable=False, unique=True)
    description = db.Column(db.Text, nullable=True)
    created_by_user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    created_by = db.relationship("User", backref="created_teams")
    members = db.relationship("TeamMember", backref="team", lazy="dynamic", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Team {self.team_name}>"

    def to_dict(self, include_members=False):
        data = {
            'team_id': self.team_id,
            'team_name': self.team_name,
            'description': self.description,
            'created_by': self.created_by.to_dict() if self.created_by else None,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'member_count': self.members.count()
        }
        
        if include_members:
            data['members'] = [member.to_dict() for member in self.members]
            
        return data

    def add_member(self, user_id, role='Member'):
        """Add a member to the team"""
        existing = TeamMember.query.filter_by(team_id=self.team_id, user_id=user_id).first()
        if existing:
            return existing
        
        member = TeamMember(team_id=self.team_id, user_id=user_id, role=role)
        db.session.add(member)
        return member

    def remove_member(self, user_id):
        """Remove a member from the team"""
        member = TeamMember.query.filter_by(team_id=self.team_id, user_id=user_id).first()
        if member:
            db.session.delete(member)
            return True
        return False

    def get_member_role(self, user_id):
        """Get the role of a user in the team"""
        member = TeamMember.query.filter_by(team_id=self.team_id, user_id=user_id).first()
        return member.role if member else None

    def is_member(self, user_id):
        """Check if a user is a member of the team"""
        return TeamMember.query.filter_by(team_id=self.team_id, user_id=user_id).first() is not None


class TeamMember(db.Model):
    __tablename__ = "team_members"

    member_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    team_id = db.Column(db.Integer, db.ForeignKey("teams.team_id"), nullable=False)
    user_id = db.Column(db.String(255), db.ForeignKey("users.user_id"), nullable=False)
    role = db.Column(db.String(50), default="Member")  # Owner, Admin, Member, Viewer
    joined_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Composite unique constraint
    __table_args__ = (
        db.UniqueConstraint('team_id', 'user_id', name='unique_team_user_membership'),
    )

    def __repr__(self):
        return f"<TeamMember Team:{self.team_id} User:{self.user_id} Role:{self.role}>"

    def to_dict(self):
        return {
            'member_id': self.member_id,
            'team_id': self.team_id,
            'user': self.user.to_dict() if self.user else None,
            'role': self.role,
            'joined_at': self.joined_at.isoformat() if self.joined_at else None
        }

    @classmethod
    def get_user_teams(cls, user_id):
        """Get all teams a user belongs to"""
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def get_team_members(cls, team_id):
        """Get all members of a team"""
        return cls.query.filter_by(team_id=team_id).all()