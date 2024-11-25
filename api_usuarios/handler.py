import json
import os
import datetime
import bcrypt
import jwt
import boto3

# Configuración de DynamoDB y JWT
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE_USUARIOS'])
SECRET_KEY = os.environ.get('JWT_SECRET', 'mysecretkey')

# Crear usuario
def create_user(event, context):
    data = json.loads(event['body'])
    if 'email' not in data or 'password' not in data or 'tenant_id' not in data or 'nombre' not in data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Email, password, tenant_id, and nombre are required"})
        }

    tenant_id = data['tenant_id']
    email = data['email']
    password = data['password']
    nombre = data['nombre']

    # Verificar si el email ya existe en el tenant usando la clave de partición y ordenamiento
    try:
        existing_user = table.get_item(
            Key={
                'tenant_id': tenant_id,
                'email': email
            }
        )
        if 'Item' in existing_user:
            return {
                "statusCode": 409,
                "body": json.dumps({"error": "El email ya está registrado para este tenant"})
            }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al verificar el email en DynamoDB", "details": str(e)})
        }

    # Hash de la contraseña
    password_hash = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    item = {
        'tenant_id': tenant_id,
        'email': email,
        'nombre': nombre,
        'password_hash': password_hash,
        'created_at': str(datetime.datetime.now())
    }

    # Guardar en DynamoDB
    try:
        table.put_item(Item=item)
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Usuario creado exitosamente", "email": email})
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al guardar en DynamoDB", "details": str(e)})
        }

# Iniciar sesión (Login)
def login_user(event, context):
    data = json.loads(event['body'])
    if 'email' not in data or 'password' not in data or 'tenant_id' not in data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "Email, password, and tenant_id are required"})
        }

    tenant_id = data['tenant_id']
    email = data['email']
    password = data['password']

    # Obtener el usuario de DynamoDB
    try:
        response = table.get_item(
            Key={
                'tenant_id': tenant_id,
                'email': email
            }
        )
    except Exception as e:
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al obtener el usuario", "details": str(e)})
        }

    # Validar usuario y contraseña
    if 'Item' not in response or not bcrypt.checkpw(password.encode('utf-8'), response['Item']['password_hash'].encode('utf-8')):
        return {
            "statusCode": 401,
            "body": json.dumps({"error": "Credenciales incorrectas"})
        }

    # Generar token JWT
    token = jwt.encode({
        'email': response['Item']['email'],
        'tenant_id': tenant_id,
        'exp': datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    }, SECRET_KEY, algorithm='HS256')

    return {
        "statusCode": 200,
        "body": json.dumps({"message": "Login exitoso", "token": token})
    }
