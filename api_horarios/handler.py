import json
import os
import uuid
import boto3
from datetime import datetime
from decimal import Decimal

# Configuración de DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE_HORARIOS'])

# Función de utilidad para convertir Decimal a tipos nativos de Python
def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

# Listar todos los horarios disponibles para un tenant
def list_schedules(event, context):
    tenant_id = event.get('queryStringParameters', {}).get('tenant_id')
    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El tenant_id es requerido"})
        }

    try:
        response = table.query(
            KeyConditionExpression=boto3.dynamodb.conditions.Key('tenant_id').eq(tenant_id)
        )
        schedules = response.get('Items', [])
        schedules = decimal_to_native(schedules)  # Convertir Decimals a nativos
        return {
            "statusCode": 200,
            "body": json.dumps(schedules)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al listar los horarios", "details": str(e)})
        }

# Crear un nuevo horario
def create_schedule(event, context):
    data = json.loads(event['body'])
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
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al crear el horario", "details": str(e)})
        }

# Actualizar asientos disponibles después de una reserv
# Actualizar asientos disponibles después de una reserva
def update_schedule_seats(event, context):
    schedule_id = event['pathParameters']['schedule_id']
    tenant_id = event.get('queryStringParameters', {}).get('tenant_id')
    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El tenant_id es requerido"})
        }

    data = json.loads(event['body'])
    if 'reserved_seats' not in data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "reserved_seats es requerido"})
        }

    try:
        # Obtener el horario
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

        # Actualizar asientos disponibles
        table.update_item(
            Key={
                'tenant_id': tenant_id,
                'schedule_id': schedule_id
            },
            UpdateExpression="SET available_seats = :new_seats",
            ExpressionAttributeValues={
                ':new_seats': Decimal(new_available_seats)  # Aseguramos que sea Decimal para DynamoDB
            }
        )

        # Convertir valores a nativos antes de retornar la respuesta
        updated_schedule = {
            "tenant_id": tenant_id,
            "schedule_id": schedule_id,
            "available_seats": int(new_available_seats)  # Convertir a entero para JSON
        }

        return {
            "statusCode": 200,
            "body": json.dumps(updated_schedule)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al actualizar asientos", "details": str(e)})
        }



# Listar todos los horarios disponibles para un tenant, opcionalmente filtrando por movie_id
def list_schedules(event, context):
    tenant_id = event.get('queryStringParameters', {}).get('tenant_id')
    movie_id = event.get('queryStringParameters', {}).get('movie_id')
    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El tenant_id es requerido"})
        }

    try:
        # Crear la expresión de clave con el tenant_id y, si existe, filtrar por movie_id
        key_condition = boto3.dynamodb.conditions.Key('tenant_id').eq(tenant_id)
        if movie_id:
            key_condition = key_condition & boto3.dynamodb.conditions.Key('movie_id').eq(movie_id)

        response = table.query(
            IndexName='MovieIndex',  # Asegúrate de tener un índice secundario en movie_id si es necesario
            KeyConditionExpression=key_condition
        )

        schedules = response.get('Items', [])
        schedules = decimal_to_native(schedules)
        return {
            "statusCode": 200,
            "body": json.dumps(schedules)
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al listar los horarios", "details": str(e)})
        }

