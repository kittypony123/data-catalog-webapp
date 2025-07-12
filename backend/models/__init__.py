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
from .compliance_requirement import ComplianceRequirement, AssetCompliance
from .business_glossary import BusinessTerm, TermUsage
from .field_compliance import DataField, FieldCompliance

__all__ = [
    'db',
    'User', 'Role',
    'Category', 'ReportType', 
    'DataAsset', 'AssetRelationship',
    'ApprovalHistory', 'UserFavorite',
    'Team', 'TeamMember',
    'ComplianceRequirement', 'AssetCompliance',
    'BusinessTerm', 'TermUsage',
    'DataField', 'FieldCompliance'
]