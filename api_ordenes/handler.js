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

// Middleware for JWT validation
function jwtRequired(handler) {
    return async (event) => {
        const authHeader = event.headers?.Authorization || event.headers?.authorization;
        if (!authHeader || !authHeader.startsWith('Bearer ')) {
            return {
                statusCode: 401,
                body: JSON.stringify({ error: 'Se requiere un token válido en el encabezado Authorization' }),
            };
        }

        const token = authHeader.split(' ')[1]; // Extract token after "Bearer"
        try {
            const decoded = validateJwt(token);
            event.user = decoded; // Attach decoded token payload to event for further use
        } catch (error) {
            return {
                statusCode: 401,
                body: JSON.stringify({ error: error.message }),
            };
        }

        // Call the original handler if token is valid
        return handler(event);
    };
}

// Configure DynamoDB
const dynamodb = new AWS.DynamoDB.DocumentClient();
const ORDERS_TABLE = process.env.DYNAMODB_TABLE_ORDENES;

// Create a new order
exports.createOrder = jwtRequired(async (event) => {
    let data;

    // Parse the request body
    try {
        data = JSON.parse(event.body);
    } catch (error) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'El cuerpo de la solicitud no es JSON válido' }),
        };
    }

    const { tenant_id, email, products } = data;

    // Validate required fields
    if (!tenant_id || !email || !products || !Array.isArray(products)) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'Campos tenant_id, email y products (array) son requeridos' }),
        };
    }

    const order_id = uuidv4();
    let total_price;

    // Calculate total price
    try {
        total_price = products.reduce((sum, product) => sum + parseFloat(product.price || 0), 0);
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

    // Insert order into DynamoDB
    try {
        await dynamodb.put(params).promise();
        return {
            statusCode: 201,
            body: JSON.stringify({ message: 'Orden creada exitosamente', order_id }),
        };
    } catch (error) {
        console.error('Error creating order:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al crear la orden', details: error.message }),
        };
    }
});

// List orders for a specific user
exports.listOrdersByUser = jwtRequired(async (event) => {
    const { tenant_id, email } = event.queryStringParameters || {};

    // Validate required query parameters
    if (!tenant_id || !email) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'Campos tenant_id y email son requeridos' }),
        };
    }

    const params = {
        TableName: ORDERS_TABLE,
        IndexName: 'EmailIndex', // Ensure EmailIndex is correctly set up in DynamoDB
        KeyConditionExpression: 'tenant_id = :tenant_id AND email = :email',
        ExpressionAttributeValues: {
            ':tenant_id': tenant_id,
            ':email': email,
        },
    };

    // Query DynamoDB for user's orders
    try {
        const result = await dynamodb.query(params).promise();
        const orders = result.Items || [];
        return {
            statusCode: 200,
            body: JSON.stringify(orders),
        };
    } catch (error) {
        console.error('Error listing orders:', error);
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al listar órdenes', details: error.message }),
        };
    }
});
