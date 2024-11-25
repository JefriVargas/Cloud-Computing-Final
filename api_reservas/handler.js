const AWS = require('aws-sdk');
const { v4: uuidv4 } = require('uuid');

// Configuración de DynamoDB
const dynamodb = new AWS.DynamoDB.DocumentClient();
const RESERVAS_TABLE = process.env.DYNAMODB_TABLE_RESERVAS;
const HORARIOS_TABLE = process.env.DYNAMODB_TABLE_HORARIOS;

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

// Listar reservas por email
exports.listReservationsByEmail = async (event) => {
    const { tenant_id, email } = event.queryStringParameters || {};

    if (!tenant_id || !email) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'Email y tenant_id son requeridos' }),
        };
    }

    const params = {
        TableName: RESERVAS_TABLE,
        IndexName: 'EmailIndex',
        KeyConditionExpression: 'tenant_id = :tenant_id AND email = :email',
        ExpressionAttributeValues: {
            ':tenant_id': tenant_id,
            ':email': email,
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
            body: JSON.stringify({ error: 'Error listing reservations', details: error.message }),
        };
    }
};

// Crear una reserva
exports.createReservation = async (event) => {
    let data;
    try {
        data = JSON.parse(event.body);
    } catch (error) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: 'El cuerpo de la solicitud no es JSON válido' }),
        };
    }

    const { tenant_id, email, seats, schedule_id, function_date, movie_title } = data;

    if (!tenant_id || !email || seats === undefined || !schedule_id) {
        return {
            statusCode: 400,
            body: JSON.stringify({
                error: 'Todos los campos (tenant_id, email, seats, schedule_id) son requeridos',
            }),
        };
    }

    if (typeof seats !== 'number' || seats <= 0) {
        return {
            statusCode: 400,
            body: JSON.stringify({ error: "El campo 'seats' debe ser un número entero positivo" }),
        };
    }

    let finalFunctionDate = function_date;
    let finalMovieTitle = movie_title;

    // Obtener detalles adicionales de la función si faltan
    if (!function_date || !movie_title) {
        const scheduleParams = {
            TableName: HORARIOS_TABLE,
            Key: {
                tenant_id: tenant_id,
                schedule_id: schedule_id,
            },
        };

        try {
            const result = await dynamodb.get(scheduleParams).promise();
            const scheduleData = result.Item;

            if (!scheduleData) {
                return {
                    statusCode: 404,
                    body: JSON.stringify({ error: 'Función no encontrada' }),
                };
            }

            finalFunctionDate = finalFunctionDate || scheduleData.function_date;
            finalMovieTitle = finalMovieTitle || scheduleData.movie_title;

            if (!finalFunctionDate || !finalMovieTitle) {
                return {
                    statusCode: 500,
                    body: JSON.stringify({
                        error: 'Detalles incompletos en la función (function_date o movie_title faltan)',
                    }),
                };
            }
        } catch (error) {
            return {
                statusCode: 500,
                body: JSON.stringify({
                    error: 'Error al obtener detalles de la función',
                    details: error.message,
                }),
            };
        }
    }

    // Crear la reserva
    const reservation_id = uuidv4();
    const item = {
        tenant_id,
        reservation_id,
        email,
        seats,
        schedule_id,
        function_date: finalFunctionDate,
        movie_title: finalMovieTitle,
        created_at: new Date().toISOString(),
    };

    const reservationParams = {
        TableName: RESERVAS_TABLE,
        Item: item,
    };

    try {
        await dynamodb.put(reservationParams).promise();
        return {
            statusCode: 201,
            body: JSON.stringify({
                message: 'Reserva creada exitosamente',
                reservation_id: reservation_id,
            }),
        };
    } catch (error) {
        return {
            statusCode: 500,
            body: JSON.stringify({
                error: 'Error al crear la reserva',
                details: error.message,
            }),
        };
    }
};
