import os
import uuid
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime
import json
import decimal  # Import the decimal module

dynamodb = boto3.resource('dynamodb')
reservas_table = dynamodb.Table(os.environ['DYNAMODB_TABLE_RESERVAS'])

# Helper function to convert Decimal to native types
def decimal_to_native(obj):
    if isinstance(obj, list):
        return [decimal_to_native(i) for i in obj]
    elif isinstance(obj, dict):
        return {k: decimal_to_native(v) for k, v in obj.items()}
    elif isinstance(obj, decimal.Decimal):
        return int(obj) if obj % 1 == 0 else float(obj)
    return obj

# List reservations by email function
def list_reservations_by_email(event, context):
    params = event.get('queryStringParameters', {})
    email = params.get('email')
    tenant_id = params.get('tenant_id')

    if not email or not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Email y tenant_id son requeridos"})
        }

    try:
        response = reservas_table.query(
            IndexName='EmailIndex',
            KeyConditionExpression=Key('tenant_id').eq(tenant_id) & Key('email').eq(email)
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
            "body": json.dumps({"error": "Error listing reservations", "details": str(e)})
        }

# Create a reservation
def create_reservation(event, context):
    try:
        data = json.loads(event.get('body', '{}'))
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El cuerpo de la solicitud no es JSON válido"})
        }

    tenant_id = data.get('tenant_id')
    email = data.get('email')
    seats = data.get('seats')
    schedule_id = data.get('schedule_id')
    function_date = data.get('function_date')
    movie_title = data.get('movie_title')

    if not tenant_id or not email or seats is None or not schedule_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Todos los campos (tenant_id, email, seats, schedule_id) son requeridos"})
        }

    if not isinstance(seats, int) or seats <= 0:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El campo 'seats' debe ser un número entero positivo"})
        }

    # Obtener detalles adicionales de la función solo si faltan
    if function_date is None or movie_title is None:
        horarios_table = dynamodb.Table(os.environ['DYNAMODB_TABLE_HORARIOS'])
        try:
            horario_response = horarios_table.get_item(
                Key={'tenant_id': tenant_id, 'schedule_id': schedule_id}
            )
            horario_data = horario_response.get('Item')
            if not horario_data:
                return {
                    "statusCode": 404,
                    "body": json.dumps({"error": "Función no encontrada"})
                }

            # Solo actualiza si no están definidos en los datos
            function_date = function_date or horario_data.get('function_date')
            movie_title = movie_title or horario_data.get('movie_title')

            if function_date is None or movie_title is None:
                return {
                    "statusCode": 500,
                    "body": json.dumps({"error": "Detalles incompletos en la función (function_date o movie_title faltan)"})
                }

        except Exception as e:
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Error al obtener detalles de la función", "details": str(e)})
            }

    # Crear la reserva
    reservation_id = str(uuid.uuid4())
    item = {
        'tenant_id': tenant_id,
        'reservation_id': reservation_id,
        'email': email,
        'seats': seats,
        'schedule_id': schedule_id,
        'function_date': function_date,
        'movie_title': movie_title,
        'created_at': datetime.utcnow().isoformat()
    }

    try:
        reservas_table.put_item(Item=item)
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Reserva creada exitosamente", "reservation_id": reservation_id})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al crear la reserva", "details": str(e)})
        }
