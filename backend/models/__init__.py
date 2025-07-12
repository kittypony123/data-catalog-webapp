from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

# Import all models so they are registered with SQLAlchemy
from .user import User, Role
from .category import Category
from .report_type import ReportType
from .data_asset import DataAsset
from .asset_relationship import AssetRelationship
from .approval_history import ApprovalHistory
from .user_favorite import UserFavorite
from .team import Team, TeamMember

__all__ = [
    'db',
    'User', 'Role',
    'Category', 'ReportType', 
    'DataAsset', 'AssetRelationship',
    'ApprovalHistory', 'UserFavorite',
    'Team', 'TeamMember'
]