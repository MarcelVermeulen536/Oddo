import os
import xmlrpc.client
from flask import Flask, render_template, request, redirect, url_for, flash
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

app = Flask(__name__)
app.secret_key = 'super_secret_key_pour_le_labo'

# Configuration Odoo
URL = os.getenv('ODOO_URL')
DB = os.getenv('ODOO_DB')
USERNAME = os.getenv('ODOO_USERNAME')
PASSWORD = os.getenv('ODOO_PASSWORD')


# Connexion API (Helpers)
def get_odoo_connection():
    common = xmlrpc.client.ServerProxy('{}/xmlrpc/2/common'.format(URL))
    uid = common.authenticate(DB, USERNAME, PASSWORD, {})
    models = xmlrpc.client.ServerProxy('{}/xmlrpc/2/object'.format(URL))
    return uid, models


@app.route('/')
def index():
    """Lister les produits disponibles"""
    try:
        uid, models = get_odoo_connection()
        # On cherche les produits qui peuvent être vendus
        ids = models.execute_kw(DB, uid, PASSWORD,
                                'product.product', 'search',
                                [[['sale_ok', '=', True]]],
                                {'limit': 10})  # Limité à 10 pour l'exemple

        products = models.execute_kw(DB, uid, PASSWORD,
                                     'product.product', 'read',
                                     [ids],
                                     {'fields': ['name', 'list_price', 'id']})

        return render_template('index.html', products=products)
    except Exception as e:
        return f"Erreur de connexion à Odoo: {e}"


@app.route('/create_order', methods=['POST'])
def create_order():
    """Créer une commande dans Odoo"""
    product_id = int(request.form.get('product_id'))
    quantity = int(request.form.get('quantity'))

    try:
        uid, models = get_odoo_connection()

        # 1. Trouver un client (Partner)
        # Pour le labo, on prend le premier client trouvé ou on utilise l'utilisateur actuel
        partner_ids = models.execute_kw(DB, uid, PASSWORD, 'res.partner', 'search', [[['customer_rank', '>', 0]]],
                                        {'limit': 1})
        partner_id = partner_ids[0] if partner_ids else uid  # Fallback sur l'admin si pas de client

        # 2. Créer l'entête de la commande (Sale Order)
        order_id = models.execute_kw(DB, uid, PASSWORD, 'sale.order', 'create', [{
            'partner_id': partner_id,
            'state': 'draft',  # Devis
        }])

        # 3. Ajouter la ligne de commande (Order Line)
        models.execute_kw(DB, uid, PASSWORD, 'sale.order.line', 'create', [{
            'order_id': order_id,
            'product_id': product_id,
            'product_uom_qty': quantity,
        }])

        # Récupérer le nom de la commande (ex: S00042) pour l'affichage
        order_name = models.execute_kw(DB, uid, PASSWORD, 'sale.order', 'read', [order_id], {'fields': ['name']})[0][
            'name']

        flash(f"Commande créée avec succès ! Référence : {order_name}", "success")
        return redirect(url_for('track_order_page', ref=order_name))

    except Exception as e:
        flash(f"Erreur lors de la commande : {e}", "danger")
        return redirect(url_for('index'))


@app.route('/track')
def track_order_page():
    """Page de recherche et d'affichage du statut"""
    reference = request.args.get('ref', '')
    order_info = None

    if reference:
        try:
            uid, models = get_odoo_connection()
            # Recherche par référence (ex: S00012)
            order_ids = models.execute_kw(DB, uid, PASSWORD, 'sale.order', 'search', [[['name', '=', reference]]])

            if order_ids:
                order_info = models.execute_kw(DB, uid, PASSWORD, 'sale.order', 'read', [order_ids[0]],
                                               {'fields': ['name', 'state', 'amount_total', 'date_order']})[0]
            else:
                flash("Commande introuvable.", "warning")

        except Exception as e:
            flash(f"Erreur API: {e}", "danger")

    return render_template('track.html', order=order_info, reference=reference)


if __name__ == '__main__':
    app.run(debug=True, port=5000)