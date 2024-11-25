import os
import json
import boto3
from uuid import uuid4
from datetime import datetime
from boto3.dynamodb.conditions import Key
import decimal

dynamodb = boto3.resource('dynamodb')
ORDERS_TABLE = os.environ['DYNAMODB_TABLE_ORDENES']

# Helper function to convert Decimal to native types
def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

# Crear una orden de compra
def create_order(event, context):
    try:
        data = json.loads(event['body'])
    except json.JSONDecodeError:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'El cuerpo de la solicitud no es JSON válido'})
        }

    tenant_id = data.get('tenant_id')
    email = data.get('email')
    products = data.get('products')

    if not tenant_id or not email or not products:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Campos tenant_id, email y products son requeridos'})
        }

    order_id = str(uuid4())
    try:
        total_price = sum(decimal.Decimal(str(product['price'])) for product in products)
    except (decimal.InvalidOperation, ValueError):
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'El precio de los productos debe ser un número válido'})
        }

    item = {
        'tenant_id': tenant_id,
        'order_id': order_id,
        'email': email,
        'products': products,
        'total_price': total_price,
        'created_at': datetime.utcnow().isoformat()
    }

    table = dynamodb.Table(ORDERS_TABLE)
    try:
        table.put_item(Item=item)
        return {
            'statusCode': 201,
            'body': json.dumps({'message': 'Orden creada exitosamente', 'order_id': order_id})
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Error al crear la orden', 'details': str(e)})
        }

# Listar órdenes de un usuario por email
def list_orders_by_user(event, context):
    tenant_id = event['queryStringParameters'].get('tenant_id')
    email = event['queryStringParameters'].get('email')

    if not tenant_id or not email:
        return {
            'statusCode': 400,
            'body': json.dumps({'error': 'Campos tenant_id y email son requeridos'})
        }

    table = dynamodb.Table(ORDERS_TABLE)
    try:
        response = table.query(
            IndexName='EmailIndex',
            KeyConditionExpression=Key('tenant_id').eq(tenant_id) & Key('email').eq(email)
        )
        items = decimal_to_native(response.get('Items', []))
        return {
            'statusCode': 200,
            'body': json.dumps(items)
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({'error': 'Error al listar órdenes', 'details': str(e)})
        }
