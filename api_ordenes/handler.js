const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');
const jwt = require('jsonwebtoken');
const SECRET_KEY = process.env.JWT_SECRET || 'mysecretkey';

// Validate JWT token
function validateJwt(token) {
    try {
        return jwt.verify(token, SECRET_KEY); // Verifies and decodes the token
    } catch (error) {
        throw new Error('Token inválido o expirado');
    }
}

function jwtRequired(handler) {
    return async (event) => {
        const authHeader = event.headers?.Authorization || event.headers?.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return {
                statusCode: 401,
                body: JSON.stringify({ error: 'Se requiere un token válido en el encabezado Authorization' }),
            };
        }

        const token = authHeader.split(' ')[1];
        try {
            const decoded = validateJwt(token);
            event.user = decoded; // Attach the decoded token to the event for further use
        } catch (error) {
            return {
                statusCode: 401,
                body: JSON.stringify({ error: error.message }),
            };
        }

        // Proceed to the actual handler
        return handler(event);
    };
}

// Configuración de DynamoDB
const dynamodb = new AWS.DynamoDB.DocumentClient();
const ORDERS_TABLE = process.env.DYNAMODB_TABLE_ORDENES;

// Crear una orden de compra
exports.createOrder = jwtRequired(async (event) => {
    let data;
    try {
        data = JSON.parse(event.body);
    } catch (error) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'El cuerpo de la solicitud no es JSON válido' }),
        };
    }

    const { tenant_id, email, products } = data;

    if (!tenant_id || !email || !products) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'Campos tenant_id, email y products son requeridos' }),
        };
    }

    const order_id = uuidv4();
    let total_price;

    try {
        total_price = products.reduce((sum, product) => sum + parseFloat(product.price), 0);
        if (isNaN(total_price)) {
            throw new Error('Precio inválido');
        }
    } catch (error) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'El precio de los productos debe ser un número válido' }),
        };
    }

    const item = {
        tenant_id,
        order_id,
        email,
        products,
        total_price,
        created_at: new Date().toISOString(),
    };

    const params = {
        TableName: ORDERS_TABLE,
        Item: item,
    };

    try {
        await dynamodb.put(params).promise();
        return {
            statusCode: 201,
            body: JSON.stringify({ message: 'Orden creada exitosamente', order_id }),
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al crear la orden', details: error.message }),
        };
    }
});

// Listar órdenes de un usuario por email
exports.listOrdersByUser = jwtRequired(async (event) => {
    const { tenant_id, email } = event.queryStringParameters || {};

    if (!tenant_id || !email) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'Campos tenant_id y email son requeridos' }),
        };
    }

    const params = {
        TableName: ORDERS_TABLE,
        IndexName: 'EmailIndex',
        KeyConditionExpression: 'tenant_id = :tenant_id AND email = :email',
        ExpressionAttributeValues: {
            ':tenant_id': tenant_id,
            ':email': email,
        },
    };

    try {
        const result = await dynamodb.query(params).promise();
        return {
            statusCode: 200,
            body: JSON.stringify(result.Items),
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al listar órdenes', details: error.message }),
        };
    }
});
