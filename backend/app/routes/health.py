from flask import Blueprint, jsonify
from app.data.providers.registry import build_providers

health_bp = Blueprint('health', __name__)


@health_bp.route('/api/health', methods=['GET'])
def health_check():
    providers = build_providers()
    availability = {p.name: p.is_available() for p in providers}
    primary = next((p.name for p in providers if p.is_available()), "generated")

    return jsonify({
        "status": "ok",
        "version": "2.0.0",
        "providers": availability,
        "data_source": primary,
        # kept for backwards compatibility with older frontend builds
        "db_connected": availability.get("mongodb", False),
    })
