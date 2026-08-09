from flask import Blueprint, request, jsonify
from database.db import get_db

anamaya_bp = Blueprint('anamaya', __name__)


@anamaya_bp.route('/leads', methods=['POST'])
def recibir_lead():
    """Recibe leads de clientes interesados en masajes AnaMaya desde n8n."""
    data = request.get_json(silent=True) or request.form

    nombre   = (data.get('nombre')   or '').strip()
    telefono = (data.get('telefono') or '').strip()
    ciudad   = (data.get('ciudad')   or '').strip()
    origen   = (data.get('origen')   or 'Meta Ads').strip()

    if not nombre or not telefono or not ciudad:
        return jsonify({'error': 'Faltan campos requeridos: nombre, telefono, ciudad'}), 400

    ciudades_validas = {'Anapoima', 'Mosquera'}
    if ciudad not in ciudades_validas:
        return jsonify({'error': f'Ciudad no válida. Usar: {", ".join(ciudades_validas)}'}), 400

    db = get_db()
    db.execute(
        'INSERT INTO leads_anamaya (nombre, telefono, ciudad, origen) VALUES (?, ?, ?, ?)',
        (nombre, telefono, ciudad, origen)
    )
    db.commit()

    return jsonify({'ok': True, 'mensaje': 'Lead guardado correctamente'}), 201
