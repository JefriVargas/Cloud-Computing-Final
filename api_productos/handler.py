import os
import uuid
import boto3
import json
import decimal
from boto3.dynamodb.conditions import Key

dynamodb = boto3.resource('dynamodb')
productos_table = dynamodb.Table(os.environ['DYNAMODB_TABLE_PRODUCTOS'])

# Helper function to convert Decimal to native types
def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

# Listar productos
def list_products(event, context):
    params = event.get('queryStringParameters', {})
    tenant_id = params.get('tenant_id')

    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "tenant_id es requerido"})
        }

    try:
        response = productos_table.query(
            KeyConditionExpression=Key('tenant_id').eq(tenant_id)
        )
        
        # Convert DynamoDB Decimals to native data types
        items = decimal_to_native(response.get('Items', []))
        
        return {
            "statusCode": 200,
            "body": json.dumps(items)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al listar productos", "details": str(e)})
        }

# Agregar un nuevo producto
def add_product(event, context):
    try:
        data = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El cuerpo de la solicitud no es JSON válido"})
        }

    tenant_id = data.get('tenant_id')
    name = data.get('name')
    description = data.get('description')
    price = data.get('price')

    if not tenant_id or not name or not description or not price:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Todos los campos (tenant_id, name, description, price) son requeridos"})
        }

    product_id = str(uuid.uuid4())
    item = {
        'tenant_id': tenant_id,
        'product_id': product_id,
        'name': name,
        'description': description,
        'price': decimal.Decimal(str(price))  # Convert price to Decimal for DynamoDB
    }

    try:
        productos_table.put_item(Item=item)
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Producto agregado exitosamente", "product_id": product_id})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al agregar el producto", "details": str(e)})
        }

# Eliminar producto
def delete_product(event, context):
    path_params = event.get('pathParameters', {})
    query_params = event.get('queryStringParameters', {})
    product_id = path_params.get('product_id')
    tenant_id = query_params.get('tenant_id')

    if not product_id or not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "product_id y tenant_id son requeridos"})
        }

    try:
        productos_table.delete_item(
            Key={
                'tenant_id': tenant_id,
                'product_id': product_id
            }
        )
        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Producto eliminado exitosamente"})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al eliminar el producto", "details": str(e)})
        }
