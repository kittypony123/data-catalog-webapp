from flask import Blueprint, jsonify, current_app
from backend.models import (
    db, DataAsset, User, Category, ReportType, Team, 
    ComplianceRequirement, AssetCompliance, BusinessTerm, TermUsage
)
from backend.utils.auth import token_required
from datetime import datetime, timedelta
from sqlalchemy import func, and_, or_

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/', methods=['GET'])
@token_required
def get_dashboard_overview():
    """Get comprehensive dashboard overview with statistics"""
    try:
        # Date ranges for trending
        today = datetime.utcnow()
        thirty_days_ago = today - timedelta(days=30)
        seven_days_ago = today - timedelta(days=7)
        ninety_days_ago = today - timedelta(days=90)
        
        # Overall data asset statistics
        total_assets = DataAsset.query.count()
        approved_assets = DataAsset.query.filter_by(approval_status='Approved').count()
        pending_assets = DataAsset.query.filter_by(approval_status='Pending').count()
        rejected_assets = DataAsset.query.filter_by(approval_status='Rejected').count()
        
        # Recent asset activity
        assets_last_30_days = DataAsset.query.filter(
            DataAsset.created_at >= thirty_days_ago
        ).count()
        
        assets_last_7_days = DataAsset.query.filter(
            DataAsset.created_at >= seven_days_ago
        ).count()
        
        # Data quality overview
        quality_stats = db.session.query(
            func.count(DataAsset.asset_id).label('total'),
            func.avg(DataAsset.data_quality_score).label('avg_quality'),
            func.count(db.case([(DataAsset.data_quality_score >= 0.8, 1)])).label('high_quality'),
            func.count(db.case([(DataAsset.data_quality_score < 0.5, 1)])).label('low_quality')
        ).filter(DataAsset.data_quality_score.isnot(None)).first()
        
        # Category distribution
        category_breakdown = db.session.query(
            Category.category_name,
            func.count(DataAsset.asset_id).label('asset_count')
        ).outerjoin(
            DataAsset, Category.category_id == DataAsset.category_id
        ).filter(Category.is_active == True).group_by(
            Category.category_id, Category.category_name
        ).order_by(func.count(DataAsset.asset_id).desc()).limit(10).all()
        
        # Report type distribution
        report_type_breakdown = db.session.query(
            ReportType.type_name,
            func.count(DataAsset.asset_id).label('asset_count')
        ).outerjoin(
            DataAsset, ReportType.report_type_id == DataAsset.report_type_id
        ).filter(ReportType.is_active == True).group_by(
            ReportType.report_type_id, ReportType.type_name
        ).order_by(func.count(DataAsset.asset_id).desc()).limit(10).all()
        
        # User and team statistics
        total_users = User.query.count()
        active_users = User.query.filter_by(is_active=True).count()
        total_teams = Team.query.count()
        
        # Recent user activity (users who created assets recently)
        active_contributors = db.session.query(
            func.count(func.distinct(DataAsset.submitted_by_user_id)).label('count')
        ).filter(DataAsset.created_at >= thirty_days_ago).scalar()
        
        # Compliance statistics (if compliance module is available)
        compliance_stats = None
        try:
            total_requirements = ComplianceRequirement.query.filter_by(status='Active').count()
            total_compliance_links = AssetCompliance.query.count()
            
            compliance_breakdown = db.session.query(
                AssetCompliance.compliance_status,
                func.count(AssetCompliance.compliance_link_id).label('count')
            ).group_by(AssetCompliance.compliance_status).all()
            
            compliance_summary = {status: count for status, count in compliance_breakdown}
            
            # Overdue compliance reviews
            overdue_reviews = AssetCompliance.query.filter(
                and_(
                    AssetCompliance.next_review_date.isnot(None),
                    AssetCompliance.next_review_date < today
                )
            ).count()
            
            # Risk distribution
            risk_breakdown = db.session.query(
                AssetCompliance.risk_level,
                func.count(AssetCompliance.compliance_link_id).label('count')
            ).group_by(AssetCompliance.risk_level).all()
            
            risk_summary = {risk: count for risk, count in risk_breakdown}
            
            compliance_stats = {
                'total_requirements': total_requirements,
                'total_compliance_links': total_compliance_links,
                'compliance_breakdown': compliance_summary,
                'risk_breakdown': risk_summary,
                'overdue_reviews': overdue_reviews,
                'compliance_percentage': round(
                    (compliance_summary.get('Compliant', 0) / total_compliance_links * 100) 
                    if total_compliance_links > 0 else 0, 1
                )
            }
        except Exception as e:
            current_app.logger.warning(f"Compliance statistics not available: {e}")
        
        # Business glossary statistics (if glossary module is available)
        glossary_stats = None
        try:
            total_terms = BusinessTerm.query.count()
            approved_terms = BusinessTerm.query.filter_by(status='Approved').count()
            total_term_usage = TermUsage.query.count()
            verified_usage = TermUsage.query.filter_by(verified=True).count()
            
            # Terms needing review
            terms_needing_review = BusinessTerm.query.filter(
                or_(
                    and_(BusinessTerm.review_date.isnot(None), BusinessTerm.review_date < today),
                    and_(BusinessTerm.status == 'Approved', BusinessTerm.review_date.is_(None))
                )
            ).count()
            
            glossary_stats = {
                'total_terms': total_terms,
                'approved_terms': approved_terms,
                'total_term_usage': total_term_usage,
                'verified_usage': verified_usage,
                'terms_needing_review': terms_needing_review,
                'approval_percentage': round((approved_terms / total_terms * 100) if total_terms > 0 else 0, 1),
                'verification_percentage': round((verified_usage / total_term_usage * 100) if total_term_usage > 0 else 0, 1)
            }
        except Exception as e:
            current_app.logger.warning(f"Glossary statistics not available: {e}")
        
        # Data sensitivity and access level distribution
        sensitivity_breakdown = db.session.query(
            DataAsset.access_level,
            func.count(DataAsset.asset_id).label('count')
        ).group_by(DataAsset.access_level).all()
        
        sensitivity_summary = {level: count for level, count in sensitivity_breakdown}
        
        # Assets by approval status over time (last 90 days, weekly buckets)
        approval_trend = []
        for i in range(13):  # 13 weeks
            week_start = today - timedelta(weeks=i+1)
            week_end = today - timedelta(weeks=i)
            
            week_stats = db.session.query(
                func.count(DataAsset.asset_id).label('total'),
                func.count(db.case([(DataAsset.approval_status == 'Approved', 1)])).label('approved'),
                func.count(db.case([(DataAsset.approval_status == 'Pending', 1)])).label('pending')
            ).filter(
                and_(DataAsset.created_at >= week_start, DataAsset.created_at < week_end)
            ).first()
            
            approval_trend.insert(0, {
                'week_start': week_start.strftime('%Y-%m-%d'),
                'week_end': week_end.strftime('%Y-%m-%d'),
                'total': week_stats.total or 0,
                'approved': week_stats.approved or 0,
                'pending': week_stats.pending or 0
            })
        
        # Top contributors (users who created most assets)
        top_contributors = db.session.query(
            User.display_name,
            User.email,
            func.count(DataAsset.asset_id).label('asset_count')
        ).join(
            DataAsset, User.user_id == DataAsset.submitted_by_user_id
        ).group_by(User.user_id, User.display_name, User.email).order_by(
            func.count(DataAsset.asset_id).desc()
        ).limit(10).all()
        
        # Most accessed assets (based on last_accessed field)
        popular_assets = db.session.query(DataAsset).filter(
            DataAsset.last_accessed.isnot(None)
        ).order_by(DataAsset.last_accessed.desc()).limit(10).all()
        
        # Build response
        dashboard_data = {
            'summary': {
                'total_assets': total_assets,
                'approved_assets': approved_assets,
                'pending_assets': pending_assets,
                'rejected_assets': rejected_assets,
                'approval_percentage': round((approved_assets / total_assets * 100) if total_assets > 0 else 0, 1),
                'assets_last_30_days': assets_last_30_days,
                'assets_last_7_days': assets_last_7_days,
                'total_users': total_users,
                'active_users': active_users,
                'total_teams': total_teams,
                'active_contributors': active_contributors,
                'avg_quality_score': round(quality_stats.avg_quality, 2) if quality_stats.avg_quality else None
            },
            'data_quality': {
                'total_assessed': quality_stats.total if quality_stats else 0,
                'high_quality': quality_stats.high_quality if quality_stats else 0,
                'low_quality': quality_stats.low_quality if quality_stats else 0,
                'avg_score': round(quality_stats.avg_quality, 2) if quality_stats and quality_stats.avg_quality else None
            },
            'category_breakdown': [
                {'category': cat, 'count': count} 
                for cat, count in category_breakdown
            ],
            'report_type_breakdown': [
                {'type': type_name, 'count': count} 
                for type_name, count in report_type_breakdown
            ],
            'sensitivity_breakdown': sensitivity_summary,
            'approval_trend': approval_trend,
            'top_contributors': [
                {
                    'name': name,
                    'email': email,
                    'asset_count': count
                }
                for name, email, count in top_contributors
            ],
            'popular_assets': [asset.to_dict() for asset in popular_assets],
            'compliance': compliance_stats,
            'glossary': glossary_stats
        }
        
        return jsonify(dashboard_data)
        
    except Exception as e:
        current_app.logger.error(f"Failed to get dashboard overview: {e}")
        return jsonify({'error': 'Failed to get dashboard overview'}), 500


@dashboard_bp.route('/activity', methods=['GET'])
@token_required
def get_activity_feed():
    """Get recent activity feed"""
    try:
        limit = min(int(request.args.get('limit', 20)), 100)
        days = min(int(request.args.get('days', 30)), 90)
        
        cutoff_date = datetime.utcnow() - timedelta(days=days)
        
        # Recent asset creations
        recent_assets = db.session.query(
            DataAsset.asset_name,
            DataAsset.created_at,
            User.display_name.label('user_name'),
            DataAsset.approval_status
        ).join(
            User, DataAsset.submitted_by_user_id == User.user_id
        ).filter(
            DataAsset.created_at >= cutoff_date
        ).order_by(DataAsset.created_at.desc()).limit(limit).all()
        
        activity_items = []
        
        for asset_name, created_at, user_name, status in recent_assets:
            activity_items.append({
                'type': 'asset_created',
                'timestamp': created_at.isoformat(),
                'description': f"{user_name} created asset '{asset_name}'",
                'status': status,
                'asset_name': asset_name,
                'user_name': user_name
            })
        
        # Sort by timestamp and limit
        activity_items.sort(key=lambda x: x['timestamp'], reverse=True)
        activity_items = activity_items[:limit]
        
        return jsonify({
            'activity': activity_items,
            'total_items': len(activity_items)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get activity feed: {e}")
        return jsonify({'error': 'Failed to get activity feed'}), 500


@dashboard_bp.route('/alerts', methods=['GET'])
@token_required
def get_dashboard_alerts():
    """Get dashboard alerts for items requiring attention"""
    try:
        alerts = []
        
        # Pending approvals
        pending_count = DataAsset.query.filter_by(approval_status='Pending').count()
        if pending_count > 0:
            alerts.append({
                'type': 'pending_approvals',
                'severity': 'warning',
                'title': f"{pending_count} asset(s) pending approval",
                'description': f"There are {pending_count} data assets waiting for approval",
                'count': pending_count,
                'action_url': '/assets?status=Pending'
            })
        
        # Assets with low quality scores
        low_quality_count = DataAsset.query.filter(
            DataAsset.data_quality_score < 0.5
        ).count()
        if low_quality_count > 0:
            alerts.append({
                'type': 'low_quality',
                'severity': 'warning',
                'title': f"{low_quality_count} asset(s) with low quality scores",
                'description': f"There are {low_quality_count} assets with quality scores below 50%",
                'count': low_quality_count,
                'action_url': '/assets?quality=low'
            })
        
        # Check for compliance alerts if available
        try:
            overdue_reviews = AssetCompliance.query.filter(
                and_(
                    AssetCompliance.next_review_date.isnot(None),
                    AssetCompliance.next_review_date < datetime.utcnow()
                )
            ).count()
            
            if overdue_reviews > 0:
                alerts.append({
                    'type': 'overdue_compliance',
                    'severity': 'high',
                    'title': f"{overdue_reviews} overdue compliance review(s)",
                    'description': f"There are {overdue_reviews} compliance reviews that are overdue",
                    'count': overdue_reviews,
                    'action_url': '/compliance/overdue-reviews'
                })
            
            # Non-compliant assets
            non_compliant_count = AssetCompliance.query.filter_by(
                compliance_status='Non-Compliant'
            ).count()
            
            if non_compliant_count > 0:
                alerts.append({
                    'type': 'non_compliant',
                    'severity': 'high',
                    'title': f"{non_compliant_count} non-compliant asset(s)",
                    'description': f"There are {non_compliant_count} assets marked as non-compliant",
                    'count': non_compliant_count,
                    'action_url': '/compliance?status=Non-Compliant'
                })
                
        except Exception:
            pass  # Compliance module not available
        
        # Check for glossary alerts if available
        try:
            terms_needing_review = BusinessTerm.query.filter(
                or_(
                    and_(BusinessTerm.review_date.isnot(None), BusinessTerm.review_date < datetime.utcnow()),
                    and_(BusinessTerm.status == 'Approved', BusinessTerm.review_date.is_(None))
                )
            ).count()
            
            if terms_needing_review > 0:
                alerts.append({
                    'type': 'terms_review',
                    'severity': 'info',
                    'title': f"{terms_needing_review} term(s) need review",
                    'description': f"There are {terms_needing_review} business terms that need review",
                    'count': terms_needing_review,
                    'action_url': '/glossary?needs_review=true'
                })
                
        except Exception:
            pass  # Glossary module not available
        
        return jsonify({
            'alerts': alerts,
            'total_alerts': len(alerts)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get dashboard alerts: {e}")
        return jsonify({'error': 'Failed to get dashboard alerts'}), 500