from flask import Blueprint, request, jsonify, current_app
from backend.models import db, Team, TeamMember
from backend.utils.auth import token_required, admin_required, get_current_user_id, get_current_user
from datetime import datetime

teams_bp = Blueprint('teams', __name__)


@teams_bp.route('/', methods=['POST'])
@token_required
def create_team():
    """Create a new team"""
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    # Validate required fields
    if not data.get('team_name'):
        return jsonify({'error': 'Team name is required'}), 400

    # Check for duplicate names
    existing = Team.query.filter_by(team_name=data['team_name']).first()
    if existing:
        return jsonify({'error': 'Team with this name already exists'}), 409

    try:
        team = Team(
            team_name=data['team_name'],
            description=data.get('description'),
            created_by_user_id=get_current_user_id()
        )
        
        db.session.add(team)
        db.session.flush()  # Get team ID
        
        # Add creator as team owner
        team.add_member(get_current_user_id(), role='Owner')
        
        db.session.commit()
        
        current_app.logger.info(f"Team created: {team.team_name} by {get_current_user_id()}")
        
        return jsonify({
            'message': 'Team created successfully',
            'team': team.to_dict(include_members=True)
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to create team: {e}")
        return jsonify({'error': 'Failed to create team'}), 500


@teams_bp.route('/', methods=['GET'])
@token_required
def get_teams():
    """Get teams (user sees their teams, admin sees all)"""
    current_user = get_current_user()
    page = request.args.get('page', 1, type=int)
    per_page = min(request.args.get('per_page', 20, type=int), 100)
    include_inactive = request.args.get('include_inactive', 'false').lower() == 'true'
    
    if current_user.role.role_name == 'Admin':
        # Admin sees all teams
        query = Team.query
        if not include_inactive:
            query = query.filter_by(is_active=True)
    else:
        # Regular users see only their teams
        user_team_ids = [tm.team_id for tm in TeamMember.get_user_teams(current_user.user_id)]
        query = Team.query.filter(Team.team_id.in_(user_team_ids))
        if not include_inactive:
            query = query.filter_by(is_active=True)
    
    pagination = query.order_by(Team.team_name)\
        .paginate(page=page, per_page=per_page, error_out=False)
    
    teams = [team.to_dict() for team in pagination.items]
    
    return jsonify({
        'teams': teams,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': pagination.total,
            'pages': pagination.pages,
            'has_next': pagination.has_next,
            'has_prev': pagination.has_prev
        }
    })


@teams_bp.route('/<int:team_id>', methods=['GET'])
@token_required
def get_team(team_id):
    """Get specific team details"""
    team = Team.query.get_or_404(team_id)
    current_user = get_current_user()
    
    # Check access - team members or admin
    if (current_user.role.role_name != 'Admin' and 
        not team.is_member(current_user.user_id)):
        return jsonify({'error': 'Access denied'}), 403
    
    return jsonify({
        'team': team.to_dict(include_members=True)
    })


@teams_bp.route('/<int:team_id>', methods=['PUT'])
@token_required
def update_team(team_id):
    """Update team details"""
    team = Team.query.get_or_404(team_id)
    current_user = get_current_user()
    
    # Check permissions - team owner/admin or system admin
    member_role = team.get_member_role(current_user.user_id)
    if (current_user.role.role_name != 'Admin' and 
        member_role not in ['Owner', 'Admin']):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    data = request.get_json()
    if not data:
        return jsonify({'error': 'No data provided'}), 400

    try:
        # Check for duplicate names (excluding current team)
        if 'team_name' in data and data['team_name'] != team.team_name:
            existing = Team.query.filter(
                Team.team_id != team_id,
                Team.team_name == data['team_name']
            ).first()
            
            if existing:
                return jsonify({'error': 'Team with this name already exists'}), 409
            
            team.team_name = data['team_name']
        
        # Update description
        if 'description' in data:
            team.description = data['description']
        
        # Update active status (system admin only)
        if 'is_active' in data and current_user.role.role_name == 'Admin':
            team.is_active = data['is_active']
        
        team.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'message': 'Team updated successfully',
            'team': team.to_dict(include_members=True)
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update team {team_id}: {e}")
        return jsonify({'error': 'Failed to update team'}), 500


@teams_bp.route('/<int:team_id>', methods=['DELETE'])
@token_required
def delete_team(team_id):
    """Delete team (soft delete)"""
    team = Team.query.get_or_404(team_id)
    current_user = get_current_user()
    
    # Check permissions - team owner or system admin
    member_role = team.get_member_role(current_user.user_id)
    if (current_user.role.role_name != 'Admin' and 
        member_role != 'Owner'):
        return jsonify({'error': 'Only team owners can delete teams'}), 403
    
    try:
        # Soft delete
        team.is_active = False
        team.updated_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'message': 'Team deleted successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to delete team {team_id}: {e}")
        return jsonify({'error': 'Failed to delete team'}), 500


@teams_bp.route('/<int:team_id>/members', methods=['POST'])
@token_required
def add_team_member(team_id):
    """Add member to team"""
    team = Team.query.get_or_404(team_id)
    current_user = get_current_user()
    
    # Check permissions - team admin/owner or system admin
    member_role = team.get_member_role(current_user.user_id)
    if (current_user.role.role_name != 'Admin' and 
        member_role not in ['Owner', 'Admin']):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    data = request.get_json()
    if not data or not data.get('user_id'):
        return jsonify({'error': 'User ID is required'}), 400
    
    try:
        member = team.add_member(
            user_id=data['user_id'],
            role=data.get('role', 'Member')
        )
        
        if not member:
            return jsonify({'error': 'User is already a team member'}), 409
        
        db.session.commit()
        
        return jsonify({
            'message': 'Member added successfully',
            'member': member.to_dict()
        }), 201

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to add team member: {e}")
        return jsonify({'error': 'Failed to add team member'}), 500


@teams_bp.route('/<int:team_id>/members/<user_id>', methods=['DELETE'])
@token_required
def remove_team_member(team_id, user_id):
    """Remove member from team"""
    team = Team.query.get_or_404(team_id)
    current_user = get_current_user()
    
    # Check permissions - team admin/owner, system admin, or self-removal
    member_role = team.get_member_role(current_user.user_id)
    target_role = team.get_member_role(user_id)
    
    if (current_user.role.role_name != 'Admin' and 
        member_role not in ['Owner', 'Admin'] and 
        current_user.user_id != user_id):
        return jsonify({'error': 'Insufficient permissions'}), 403
    
    # Cannot remove team owner (except by system admin)
    if (target_role == 'Owner' and 
        current_user.role.role_name != 'Admin'):
        return jsonify({'error': 'Cannot remove team owner'}), 403
    
    try:
        removed = team.remove_member(user_id)
        
        if not removed:
            return jsonify({'error': 'User is not a team member'}), 404
        
        db.session.commit()
        
        return jsonify({'message': 'Member removed successfully'})

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to remove team member: {e}")
        return jsonify({'error': 'Failed to remove team member'}), 500


@teams_bp.route('/<int:team_id>/members/<user_id>/role', methods=['PUT'])
@token_required
def update_member_role(team_id, user_id):
    """Update member's role in team"""
    team = Team.query.get_or_404(team_id)
    current_user = get_current_user()
    
    # Check permissions - team owner or system admin
    member_role = team.get_member_role(current_user.user_id)
    if (current_user.role.role_name != 'Admin' and 
        member_role != 'Owner'):
        return jsonify({'error': 'Only team owners can change member roles'}), 403
    
    data = request.get_json()
    if not data or not data.get('role'):
        return jsonify({'error': 'Role is required'}), 400
    
    # Validate role
    valid_roles = ['Owner', 'Admin', 'Member', 'Viewer']
    if data['role'] not in valid_roles:
        return jsonify({'error': f'Invalid role. Must be one of: {", ".join(valid_roles)}'}), 400
    
    member = TeamMember.query.filter_by(team_id=team_id, user_id=user_id).first()
    if not member:
        return jsonify({'error': 'User is not a team member'}), 404
    
    try:
        member.role = data['role']
        db.session.commit()
        
        return jsonify({
            'message': 'Member role updated successfully',
            'member': member.to_dict()
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Failed to update member role: {e}")
        return jsonify({'error': 'Failed to update member role'}), 500


@teams_bp.route('/my-teams', methods=['GET'])
@token_required
def get_my_teams():
    """Get current user's teams"""
    user_id = get_current_user_id()
    team_memberships = TeamMember.get_user_teams(user_id)
    
    teams = []
    for membership in team_memberships:
        if membership.team.is_active:
            team_dict = membership.team.to_dict()
            team_dict['my_role'] = membership.role
            team_dict['joined_at'] = membership.joined_at.isoformat() if membership.joined_at else None
            teams.append(team_dict)
    
    return jsonify({
        'teams': teams,
        'total_teams': len(teams)
    })