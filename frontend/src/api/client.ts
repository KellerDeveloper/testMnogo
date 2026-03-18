import axios from 'axios';

// В dev без явного VITE_* используем прокси Vite (см. vite.config.ts), чтобы и REST, и WebSocket шли через один хост
const orderBase = import.meta.env.VITE_ORDER_API ?? (import.meta.env.DEV ? '/api/order' : 'http://localhost:8000');
const courierBase = import.meta.env.VITE_COURIER_API ?? (import.meta.env.DEV ? '/api/courier' : 'http://localhost:8001');
const geoBase = import.meta.env.VITE_GEO_API ?? 'http://localhost:8002';
const configBase = import.meta.env.VITE_CONFIG_API ?? 'http://localhost:8003';
const logBase = import.meta.env.VITE_LOG_API ?? (import.meta.env.DEV ? '/api/log' : 'http://localhost:8004');
const notificationBase = import.meta.env.VITE_NOTIFICATION_API ?? 'http://localhost:8005';
const gateway3plBase = import.meta.env.VITE_GATEWAY3PL_API ?? 'http://localhost:8006';

export const orderApi = axios.create({ baseURL: orderBase });
export const courierApi = axios.create({ baseURL: courierBase });
export const geoApi = axios.create({ baseURL: geoBase });
export const configApi = axios.create({ baseURL: configBase });
export const logApi = axios.create({ baseURL: logBase });
export const notificationApi = axios.create({ baseURL: notificationBase });
export const gateway3plApi = axios.create({ baseURL: gateway3plBase });

