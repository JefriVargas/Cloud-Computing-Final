import json
import os
import uuid
import datetime
import boto3

# Configuración de DynamoDB
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table(os.environ['DYNAMODB_TABLE_PELICULAS'])

# Listar todas las películas para un tenant específico
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
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al listar las películas", "details": str(e)})
        }

# Obtener detalles de una película específica para un tenant
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
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al obtener detalles de la película", "details": str(e)})
        }

# Agregar una nueva película
def add_movie(event, context):
    data = json.loads(event['body'])
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
        return {
            "statusCode": 500,
            "body": json.dumps({"error": "Error al agregar la película", "details": str(e)})
        }
