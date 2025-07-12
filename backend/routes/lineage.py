from flask import Blueprint, request, jsonify, current_app
from backend.models import db, DataAsset, AssetRelationship, Category, ReportType
from backend.utils.auth import token_required
from sqlalchemy import or_, and_, func
from collections import deque, defaultdict

lineage_bp = Blueprint('lineage', __name__)


@lineage_bp.route('/asset/<int:asset_id>', methods=['GET'])
@token_required
def get_asset_lineage(asset_id):
    """Get complete lineage for a specific asset"""
    asset = DataAsset.query.get_or_404(asset_id)
    
    # Parameters for lineage traversal
    max_depth = request.args.get('max_depth', 3, type=int)
    include_external = request.args.get('include_external', 'true').lower() == 'true'
    direction = request.args.get('direction', 'both')  # upstream, downstream, both
    
    try:
        lineage_graph = build_lineage_graph(asset_id, max_depth, include_external, direction)
        
        return jsonify({
            'lineage': lineage_graph,
            'root_asset_id': asset_id,
            'parameters': {
                'max_depth': max_depth,
                'include_external': include_external,
                'direction': direction
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get lineage for asset {asset_id}: {e}")
        return jsonify({'error': 'Failed to retrieve lineage data'}), 500


@lineage_bp.route('/graph', methods=['GET'])
@token_required
def get_lineage_graph():
    """Get lineage graph for multiple assets or entire system"""
    asset_ids = request.args.getlist('asset_id', type=int)
    category_ids = request.args.getlist('category_id', type=int)
    include_external = request.args.get('include_external', 'true').lower() == 'true'
    max_nodes = request.args.get('max_nodes', 100, type=int)
    
    try:
        if asset_ids:
            # Build lineage for specific assets
            combined_graph = {
                'nodes': {},
                'edges': [],
                'stats': {
                    'total_nodes': 0,
                    'internal_nodes': 0,
                    'external_nodes': 0,
                    'total_edges': 0
                }
            }
            
            for asset_id in asset_ids:
                asset_graph = build_lineage_graph(asset_id, 2, include_external, 'both')
                merge_graphs(combined_graph, asset_graph)
                
                # Stop if we exceed max_nodes
                if len(combined_graph['nodes']) >= max_nodes:
                    break
            
            return jsonify({
                'lineage': combined_graph,
                'parameters': {
                    'asset_ids': asset_ids,
                    'include_external': include_external,
                    'max_nodes': max_nodes
                }
            })
        
        elif category_ids:
            # Build lineage for assets in specific categories
            assets = DataAsset.query.filter(
                and_(
                    DataAsset.category_id.in_(category_ids),
                    DataAsset.approval_status == 'Approved'
                )
            ).limit(max_nodes // 2).all()
            
            combined_graph = {
                'nodes': {},
                'edges': [],
                'stats': {
                    'total_nodes': 0,
                    'internal_nodes': 0,
                    'external_nodes': 0,
                    'total_edges': 0
                }
            }
            
            for asset in assets:
                asset_graph = build_lineage_graph(asset.asset_id, 1, include_external, 'both')
                merge_graphs(combined_graph, asset_graph)
                
                if len(combined_graph['nodes']) >= max_nodes:
                    break
            
            return jsonify({
                'lineage': combined_graph,
                'parameters': {
                    'category_ids': category_ids,
                    'include_external': include_external,
                    'max_nodes': max_nodes
                }
            })
        
        else:
            # Return overview of all relationships
            overview = get_lineage_overview()
            return jsonify({
                'overview': overview,
                'parameters': {
                    'include_external': include_external,
                    'max_nodes': max_nodes
                }
            })
            
    except Exception as e:
        current_app.logger.error(f"Failed to get lineage graph: {e}")
        return jsonify({'error': 'Failed to retrieve lineage graph'}), 500


@lineage_bp.route('/overview', methods=['GET'])
@token_required
def get_lineage_overview():
    """Get high-level lineage statistics and overview"""
    try:
        # Get relationship statistics
        relationship_stats = db.session.query(
            AssetRelationship.relationship_type,
            func.count(AssetRelationship.relationship_id).label('count')
        ).group_by(AssetRelationship.relationship_type).all()
        
        # Get assets with most relationships
        asset_relationship_counts = db.session.query(
            DataAsset.asset_id,
            DataAsset.asset_name,
            func.count(AssetRelationship.relationship_id).label('relationship_count')
        ).join(
            AssetRelationship,
            or_(
                AssetRelationship.source_asset_id == DataAsset.asset_id,
                AssetRelationship.target_asset_id == DataAsset.asset_id
            )
        ).filter(
            DataAsset.approval_status == 'Approved'
        ).group_by(
            DataAsset.asset_id, DataAsset.asset_name
        ).order_by(
            func.count(AssetRelationship.relationship_id).desc()
        ).limit(10).all()
        
        # Get external system connections
        external_systems = db.session.query(
            AssetRelationship.external_system,
            func.count(AssetRelationship.relationship_id).label('count')
        ).filter(
            AssetRelationship.external_system.isnot(None)
        ).group_by(AssetRelationship.external_system).all()
        
        # Calculate lineage depth statistics
        max_depth_stats = calculate_lineage_depth_stats()
        
        overview = {
            'relationship_types': {
                rel_type: count for rel_type, count in relationship_stats
            },
            'top_connected_assets': [
                {
                    'asset_id': asset_id,
                    'asset_name': asset_name,
                    'relationship_count': count
                }
                for asset_id, asset_name, count in asset_relationship_counts
            ],
            'external_systems': {
                system: count for system, count in external_systems
            },
            'depth_statistics': max_depth_stats,
            'total_assets': DataAsset.query.filter_by(approval_status='Approved').count(),
            'total_relationships': AssetRelationship.query.count(),
            'external_relationships': AssetRelationship.query.filter(
                AssetRelationship.external_system.isnot(None)
            ).count()
        }
        
        return jsonify({'overview': overview})
        
    except Exception as e:
        current_app.logger.error(f"Failed to get lineage overview: {e}")
        return jsonify({'error': 'Failed to retrieve lineage overview'}), 500


@lineage_bp.route('/paths', methods=['GET'])
@token_required
def find_lineage_paths():
    """Find all paths between two assets"""
    source_id = request.args.get('source_id', type=int)
    target_id = request.args.get('target_id', type=int)
    max_depth = request.args.get('max_depth', 5, type=int)
    
    if not source_id or not target_id:
        return jsonify({'error': 'Both source_id and target_id are required'}), 400
    
    try:
        paths = find_all_paths(source_id, target_id, max_depth)
        
        return jsonify({
            'paths': paths,
            'source_asset_id': source_id,
            'target_asset_id': target_id,
            'total_paths': len(paths)
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to find paths between {source_id} and {target_id}: {e}")
        return jsonify({'error': 'Failed to find lineage paths'}), 500


@lineage_bp.route('/impact', methods=['GET'])
@token_required
def get_impact_analysis():
    """Get impact analysis for an asset - what would be affected if this asset changes"""
    asset_id = request.args.get('asset_id', type=int)
    max_depth = request.args.get('max_depth', 3, type=int)
    
    if not asset_id:
        return jsonify({'error': 'asset_id is required'}), 400
    
    try:
        # Get all downstream assets (what depends on this asset)
        impact_graph = build_lineage_graph(asset_id, max_depth, True, 'downstream')
        
        # Calculate impact metrics
        impact_metrics = calculate_impact_metrics(impact_graph, asset_id)
        
        return jsonify({
            'impact_analysis': {
                'graph': impact_graph,
                'metrics': impact_metrics,
                'root_asset_id': asset_id
            }
        })
        
    except Exception as e:
        current_app.logger.error(f"Failed to get impact analysis for asset {asset_id}: {e}")
        return jsonify({'error': 'Failed to perform impact analysis'}), 500


def build_lineage_graph(root_asset_id, max_depth=3, include_external=True, direction='both'):
    """Build a complete lineage graph for an asset"""
    nodes = {}
    edges = []
    visited = set()
    
    # BFS to traverse relationships
    queue = deque([(root_asset_id, 0, None)])  # (asset_id, depth, parent_relationship)
    
    while queue:
        current_asset_id, depth, parent_rel = queue.popleft()
        
        if depth > max_depth or current_asset_id in visited:
            continue
            
        visited.add(current_asset_id)
        
        # Get asset information
        asset = DataAsset.query.get(current_asset_id)
        if not asset:
            continue
            
        # Add asset as node
        nodes[current_asset_id] = {
            'id': current_asset_id,
            'type': 'internal',
            'name': asset.asset_name,
            'description': asset.description,
            'category': asset.category.category_name if asset.category else None,
            'category_color': get_category_color(asset.category_id) if asset.category_id else '#6b7280',
            'report_type': asset.report_type.type_name if asset.report_type else None,
            'approval_status': asset.approval_status,
            'is_sensitive': asset.is_sensitive,
            'access_level': asset.access_level,
            'depth': depth,
            'is_root': (current_asset_id == root_asset_id)
        }
        
        # Get relationships based on direction
        relationships = []
        
        if direction in ['upstream', 'both']:
            # Upstream relationships (where current asset is target)
            upstream_rels = AssetRelationship.query.filter_by(target_asset_id=current_asset_id).all()
            relationships.extend(upstream_rels)
        
        if direction in ['downstream', 'both']:
            # Downstream relationships (where current asset is source)
            downstream_rels = AssetRelationship.query.filter_by(source_asset_id=current_asset_id).all()
            relationships.extend(downstream_rels)
        
        # Process relationships
        for rel in relationships:
            # Determine source and target
            if rel.source_asset_id == current_asset_id:
                # Downstream relationship
                other_asset_id = rel.target_asset_id
                edge_direction = 'outgoing'
            else:
                # Upstream relationship
                other_asset_id = rel.source_asset_id
                edge_direction = 'incoming'
            
            # Handle external relationships
            if rel.is_external() and include_external:
                external_id = f"external_{rel.relationship_id}"
                nodes[external_id] = {
                    'id': external_id,
                    'type': 'external',
                    'name': rel.external_name,
                    'description': f"External system: {rel.external_system}",
                    'external_system': rel.external_system,
                    'external_reference': rel.external_reference,
                    'depth': depth + 1,
                    'is_root': False
                }
                
                edges.append({
                    'id': f"edge_{rel.relationship_id}",
                    'source': rel.source_asset_id,
                    'target': external_id,
                    'relationship_type': rel.relationship_type,
                    'description': rel.relationship_description,
                    'is_external': True,
                    'confidence_score': rel.confidence_score,
                    'is_automated': rel.is_automated
                })
            
            # Handle internal relationships
            elif other_asset_id and depth < max_depth:
                queue.append((other_asset_id, depth + 1, rel))
                
                edges.append({
                    'id': f"edge_{rel.relationship_id}",
                    'source': rel.source_asset_id,
                    'target': rel.target_asset_id,
                    'relationship_type': rel.relationship_type,
                    'description': rel.relationship_description,
                    'is_external': False,
                    'confidence_score': rel.confidence_score,
                    'is_automated': rel.is_automated
                })
    
    # Calculate statistics
    internal_nodes = sum(1 for node in nodes.values() if node['type'] == 'internal')
    external_nodes = sum(1 for node in nodes.values() if node['type'] == 'external')
    
    return {
        'nodes': nodes,
        'edges': edges,
        'stats': {
            'total_nodes': len(nodes),
            'internal_nodes': internal_nodes,
            'external_nodes': external_nodes,
            'total_edges': len(edges),
            'max_depth': max_depth
        }
    }


def merge_graphs(target_graph, source_graph):
    """Merge two lineage graphs"""
    # Merge nodes
    for node_id, node_data in source_graph['nodes'].items():
        if node_id not in target_graph['nodes']:
            target_graph['nodes'][node_id] = node_data
    
    # Merge edges (avoid duplicates)
    existing_edge_ids = {edge['id'] for edge in target_graph['edges']}
    for edge in source_graph['edges']:
        if edge['id'] not in existing_edge_ids:
            target_graph['edges'].append(edge)
    
    # Update stats
    target_graph['stats']['total_nodes'] = len(target_graph['nodes'])
    target_graph['stats']['internal_nodes'] = sum(1 for node in target_graph['nodes'].values() if node['type'] == 'internal')
    target_graph['stats']['external_nodes'] = sum(1 for node in target_graph['nodes'].values() if node['type'] == 'external')
    target_graph['stats']['total_edges'] = len(target_graph['edges'])


def get_category_color(category_id):
    """Get color for category visualization"""
    colors = [
        '#4f46e5', '#7c3aed', '#db2777', '#dc2626', 
        '#ea580c', '#d97706', '#ca8a04', '#65a30d',
        '#16a34a', '#059669', '#0891b2', '#0284c7',
        '#2563eb', '#6366f1', '#8b5cf6', '#a855f7'
    ]
    return colors[category_id % len(colors)] if category_id else '#6b7280'


def find_all_paths(source_id, target_id, max_depth):
    """Find all paths between two assets using DFS"""
    paths = []
    visited = set()
    
    def dfs(current_id, path, depth):
        if depth > max_depth:
            return
        
        if current_id == target_id and len(path) > 1:
            paths.append(path.copy())
            return
        
        if current_id in visited:
            return
        
        visited.add(current_id)
        
        # Get downstream relationships
        relationships = AssetRelationship.query.filter_by(source_asset_id=current_id).all()
        
        for rel in relationships:
            if rel.target_asset_id and rel.target_asset_id not in path:
                path.append(rel.target_asset_id)
                dfs(rel.target_asset_id, path, depth + 1)
                path.pop()
        
        visited.remove(current_id)
    
    dfs(source_id, [source_id], 0)
    return paths


def calculate_lineage_depth_stats():
    """Calculate statistics about lineage depth in the system"""
    # This is a simplified version - could be more sophisticated
    total_assets = DataAsset.query.filter_by(approval_status='Approved').count()
    assets_with_relationships = db.session.query(
        func.count(func.distinct(DataAsset.asset_id))
    ).join(
        AssetRelationship,
        or_(
            AssetRelationship.source_asset_id == DataAsset.asset_id,
            AssetRelationship.target_asset_id == DataAsset.asset_id
        )
    ).filter(DataAsset.approval_status == 'Approved').scalar()
    
    return {
        'total_assets': total_assets,
        'connected_assets': assets_with_relationships,
        'disconnected_assets': total_assets - assets_with_relationships,
        'connectivity_percentage': round((assets_with_relationships / total_assets * 100) if total_assets > 0 else 0, 1)
    }


def calculate_impact_metrics(impact_graph, root_asset_id):
    """Calculate impact analysis metrics"""
    nodes = impact_graph['nodes']
    edges = impact_graph['edges']
    
    # Count affected assets by depth
    depth_counts = defaultdict(int)
    for node in nodes.values():
        if node['id'] != root_asset_id:
            depth_counts[node.get('depth', 0)] += 1
    
    # Count by category
    category_counts = defaultdict(int)
    for node in nodes.values():
        if node['id'] != root_asset_id and node['type'] == 'internal':
            category = node.get('category', 'Uncategorized')
            category_counts[category] += 1
    
    # Count by access level
    access_level_counts = defaultdict(int)
    for node in nodes.values():
        if node['id'] != root_asset_id and node['type'] == 'internal':
            access_level = node.get('access_level', 'Unknown')
            access_level_counts[access_level] += 1
    
    # Critical path analysis (longest path)
    max_depth = max((node.get('depth', 0) for node in nodes.values()), default=0)
    
    return {
        'total_affected_assets': len(nodes) - 1,  # Exclude root asset
        'affected_by_depth': dict(depth_counts),
        'affected_by_category': dict(category_counts),
        'affected_by_access_level': dict(access_level_counts),
        'maximum_impact_depth': max_depth,
        'external_systems_affected': len([n for n in nodes.values() if n['type'] == 'external']),
        'total_relationships': len(edges)
    }