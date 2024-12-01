import json
import os
import uuid
import datetime
import boto3
import jwt
from functools import wraps

# JWT Configuration
SECRET_KEY = os.environ.get('JWT_SECRET', 'mysecretkey')

# DynamoDB Configuration
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE_PELICULAS'])

# Validate JWT Token
def validate_jwt(token):
    try:
        decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return decoded
    except jwt.ExpiredSignatureError:
        raise ValueError("El token ha expirado")
    except jwt.InvalidTokenError:
        raise ValueError("Token inválido")

# JWT Required Decorator
def jwt_required(func):
    @wraps(func)
    def wrapper(event, context, *args, **kwargs):
        headers = event.get('headers', {})
        print(f"Headers received: {headers}")  # Debug headers
        auth_header = headers.get('Authorization') or headers.get('authorization')
        if not auth_header or not auth_header.startswith("Bearer "):
            return {
                "statusCode": 401,
                "body": json.dumps({"error": "Se requiere un token válido en el encabezado Authorization"})
            }
        token = auth_header.split(" ")[1]  # Extract token after "Bearer"
        try:
            decoded = validate_jwt(token)
            print(f"Decoded JWT: {decoded}")  # Debug token decoding
            event['user'] = decoded  # Add decoded JWT data to the event
        except ValueError as e:
            print(f"JWT Validation Error: {str(e)}")  # Log the error
            return {
                "statusCode": 401,
                "body": json.dumps({"error": str(e)})
            }
        except Exception as e:
            print(f"Unexpected Error: {str(e)}")  # Log unexpected errors
            return {
                "statusCode": 500,
                "body": json.dumps({"error": "Error interno del servidor"})
            }
        return func(event, context, *args, **kwargs)
    return wrapper

# List Movies for a Tenant
@jwt_required
def list_movies(event, context):
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
        movies = response.get('Items', [])
        return {
            "statusCode": 200,
            "body": json.dumps(movies)
        }
    except Exception as e:
        print(f"Error Listing Movies: {str(e)}")  # Log the error
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al listar las películas", "details": str(e)})
        }

# Get Details of a Specific Movie
@jwt_required
def get_movie_details(event, context):
    movie_id = event['pathParameters']['movie_id']
    tenant_id = event.get('queryStringParameters', {}).get('tenant_id')

    if not tenant_id:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El tenant_id es requerido"})
        }

    try:
        response = table.get_item(
            Key={
                'tenant_id': tenant_id,
                'movie_id': movie_id
            }
        )
        if 'Item' in response:
            return {
                "statusCode": 200,
                "body": json.dumps(response['Item'])
            }
        else:
            return {
                "statusCode": 404,
                "body": json.dumps({"error": "Película no encontrada"})
            }
    except Exception as e:
        print(f"Error Getting Movie Details: {str(e)}")  # Log the error
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al obtener detalles de la película", "details": str(e)})
        }

# Add a New Movie
@jwt_required
def add_movie(event, context):
    try:
        data = json.loads(event['body'])
    except json.JSONDecodeError:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "El cuerpo de la solicitud no es JSON válido"})
        }

    if 'titulo' not in data or 'genero' not in data or 'release_date' not in data or 'tenant_id' not in data:
        return {
            "statusCode": 400,
            "body": json.dumps({"error": "titulo, genero, release_date y tenant_id son requeridos"})
        }

    tenant_id = data['tenant_id']
    movie_id = str(uuid.uuid4())
    item = {
        'tenant_id': tenant_id,
        'movie_id': movie_id,
        'titulo': data['titulo'],
        'genero': data['genero'],
        'release_date': data['release_date'],
        'descripcion': data.get('descripcion', ''),
        'created_at': str(datetime.datetime.now())
    }

    try:
        table.put_item(Item=item)
        return {
            "statusCode": 201,
            "body": json.dumps({"message": "Película agregada exitosamente", "movie_id": movie_id})
        }
    except Exception as e:
        print(f"Error Adding Movie: {str(e)}")  # Log the error
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al agregar la película", "details": str(e)})
        }
