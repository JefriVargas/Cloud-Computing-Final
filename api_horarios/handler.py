import json
import os
import uuid
import boto3
from datetime import datetime
from decimal import Decimal
import jwt
from functools import wraps

# Load the secret key
SECRET_KEY = os.environ.get('JWT_SECRET', 'mysecretkey')

# Validate JWT token
def validate_jwt(token):
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        raise ValueError("El token ha expirado")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido")

# Middleware to validate JWT
def jwt_required(func):
    @wraps(func)
    def wrapper(event, context, *args, **kwargs):
        headers = event.get('headers', {})
        print("Headers received:", headers)  # Debug log

        # Check both lowercase and uppercase for the Authorization header
        auth_header = headers.get('Authorization') or headers.get('authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            print("Missing or malformed Authorization header")  # Debug log
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Se requiere un token válido en el encabezado Authorization"})
            }

        token = auth_header.split(" ")[1]  # Extract the token part after "Bearer"
        try:
            decoded = validate_jwt(token)
            print("Token decoded successfully:", decoded)  # Debug log
            event['user'] = decoded  # Attach decoded JWT data to the event
        except ValueError as e:
            print("JWT validation error:", str(e))  # Debug log
            return {
                "statusCode": 401,
                "body": json.dumps({"error": str(e)})
            }
        return func(event, context, *args, **kwargs)
    return wrapper

# DynamoDB Configuration
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE_HORARIOS'])

# Utility function to convert Decimal to native Python types
def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

# List all schedules for a tenant
@jwt_required
def list_schedules(event, context):
    tenant_id = event.get('queryStringParameters', {}).get('tenant_id')
    movie_id = event.get('queryStringParameters', {}).get('movie_id')

    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El tenant_id es requerido"})
        }

    try:
        # Create a key condition expression
        key_condition = boto3.dynamodb.conditions.Key('tenant_id').eq(tenant_id)
        if movie_id:
            key_condition &= boto3.dynamodb.conditions.Key('movie_id').eq(movie_id)

        response = table.query(
            IndexName='MovieIndex',  # Ensure this index exists
            KeyConditionExpression=key_condition
        )
        schedules = response.get('Items', [])
        schedules = decimal_to_native(schedules)  # Convert Decimals to native Python types
        return {
            "statusCode": 200,
            "body": json.dumps(schedules)
        }
    except Exception as e:
        print(f"Error listing schedules: {e}")  # Debug log
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al listar los horarios", "details": str(e)})
        }

# Create a new schedule
@jwt_required
def create_schedule(event, context):
    try:
        data = json.loads(event['body'])
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El cuerpo de la solicitud no es JSON válido"})
        }

    if 'tenant_id' not in data or 'movie_id' not in data or 'function_date' not in data or 'available_seats' not in data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "tenant_id, movie_id, function_date y available_seats son requeridos"})
        }

    tenant_id = data['tenant_id']
    schedule_id = str(uuid.uuid4())
    item = {
        'tenant_id': tenant_id,
        'schedule_id': schedule_id,
        'movie_id': data['movie_id'],
        'function_date': data['function_date'],
        'available_seats': int(data['available_seats']),
        'created_at': str(datetime.now())
    }

    try:
        table.put_item(Item=item)
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Horario creado exitosamente", "schedule_id": schedule_id})
        }
    except Exception as e:
        print(f"Error creating schedule: {e}")  # Debug log
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al crear el horario", "details": str(e)})
        }

# Update available seats after a reservation
@jwt_required
def update_schedule_seats(event, context):
    schedule_id = event['pathParameters'].get('schedule_id')
    tenant_id = event.get('queryStringParameters', {}).get('tenant_id')

    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El tenant_id es requerido"})
        }

    try:
        data = json.loads(event['body'])
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El cuerpo de la solicitud no es JSON válido"})
        }

    if 'reserved_seats' not in data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "reserved_seats es requerido"})
        }

    try:
        response = table.get_item(
            Key={
                'tenant_id': tenant_id,
                'schedule_id': schedule_id
            }
        )
        if 'Item' not in response:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Horario no encontrado"})
            }

        schedule = response['Item']
        new_available_seats = schedule['available_seats'] - data['reserved_seats']

        if new_available_seats < 0:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "No hay suficientes asientos disponibles"})
            }

        table.update_item(
            Key={
                'tenant_id': tenant_id,
                'schedule_id': schedule_id
            },
            UpdateExpression="SET available_seats = :new_seats",
            ExpressionAttributeValues={
                ':new_seats': Decimal(new_available_seats)  # Ensure Decimal for DynamoDB
            }
        )

        updated_schedule = {
            "tenant_id": tenant_id,
            "schedule_id": schedule_id,
            "available_seats": int(new_available_seats)  # Convert to int for JSON response
        }

        return {
            "statusCode": 200,
            "body": json.dumps(updated_schedule)
        }
    except Exception as e:
        print(f"Error updating schedule seats: {e}")  # Debug log
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al actualizar asientos", "details": str(e)})
        }
