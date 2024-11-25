const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');

// Configuración de DynamoDB
const dynamodb = new AWS.DynamoDB.DocumentClient();
const PRODUCTOS_TABLE = process.env.DYNAMODB_TABLE_PRODUCTOS;

// Helper function to convert DynamoDB Decimals to native types
const decimalToNative = (obj) => {
    if (Array.isArray(obj)) {
        return obj.map(decimalToNative);
    } else if (obj && typeof obj === 'object') {
        return Object.entries(obj).reduce((acc, [key, value]) => {
            acc[key] = decimalToNative(value);
            return acc;
        }, {});
    } else if (typeof obj === 'number' && !Number.isInteger(obj)) {
        return parseFloat(obj.toString());
    }
    return obj;
};

// Listar productos
exports.listProducts = async (event) => {
    const { tenant_id } = event.queryStringParameters || {};

    if (!tenant_id) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'tenant_id es requerido' }),
        };
    }

    const params = {
        TableName: PRODUCTOS_TABLE,
        KeyConditionExpression: 'tenant_id = :tenant_id',
        ExpressionAttributeValues: {
            ':tenant_id': tenant_id,
        },
    };

    try {
        const result = await dynamodb.query(params).promise();
        const items = decimalToNative(result.Items || []);
        return {
            statusCode: 200,
            body: JSON.stringify(items),
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al listar productos', details: error.message }),
        };
    }
};

// Agregar un nuevo producto
exports.addProduct = async (event) => {
    let data;
    try {
        data = JSON.parse(event.body);
    } catch (error) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'El cuerpo de la solicitud no es JSON válido' }),
        };
    }

    const { tenant_id, name, description, price } = data;

    if (!tenant_id || !name || !description || price === undefined) {
        return {
            statusCode: 400,
            body: JSON.stringify({
                error: 'Todos los campos (tenant_id, name, description, price) son requeridos',
            }),
        };
    }

    const product_id = uuidv4();
    const item = {
        tenant_id,
        product_id,
        name,
        description,
        price: parseFloat(price), // Parse price as a number for DynamoDB
    };

    const params = {
        TableName: PRODUCTOS_TABLE,
        Item: item,
    };

    try {
        await dynamodb.put(params).promise();
        return {
            statusCode: 201,
            body: JSON.stringify({
                message: 'Producto agregado exitosamente',
                product_id: product_id,
            }),
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al agregar el producto', details: error.message }),
        };
    }
};

// Eliminar producto
exports.deleteProduct = async (event) => {
    const pathParams = event.pathParameters || {};
    const queryParams = event.queryStringParameters || {};
    const { product_id } = pathParams;
    const { tenant_id } = queryParams;

    if (!product_id || !tenant_id) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'product_id y tenant_id son requeridos' }),
        };
    }

    const params = {
        TableName: PRODUCTOS_TABLE,
        Key: {
            tenant_id,
            product_id,
        },
    };

    try {
        await dynamodb.delete(params).promise();
        return {
            statusCode: 200,
            body: JSON.stringify({ message: 'Producto eliminado exitosamente' }),
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({ error: 'Error al eliminar el producto', details: error.message }),
        };
    }
};
