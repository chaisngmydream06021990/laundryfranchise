/**
 * store.js - Logic for data persistence
 * Handles saving and retrieving delivery commitments from localStorage.
 */

const STORAGE_KEY = 'delivery_scheduler_data';

export const Store = {
    // Get all deliveries
    getDeliveries() {
        const data = localStorage.getItem(STORAGE_KEY);
        return data ? JSON.parse(data) : [];
    },

    // Add a new delivery
    addDelivery(delivery) {
        const deliveries = this.getDeliveries();
        const newDelivery = {
            id: crypto.randomUUID(), // Valid unique ID
            createdAt: new Date().toISOString(),
            status: 'pending', // pending, completed
            ...delivery
        };

        deliveries.push(newDelivery);
        this.save(deliveries);
        return newDelivery;
    },

    // Save entire array
    save(deliveries) {
        localStorage.setItem(STORAGE_KEY, JSON.stringify(deliveries));
    },

    // Clear all data (for debugging)
    clear() {
        localStorage.removeItem(STORAGE_KEY);
    },

    // Get stats for dashboard
    getStats() {
        const deliveries = this.getDeliveries();
        return {
            total: deliveries.length,
            pending: deliveries.filter(d => d.status === 'pending').length,
            delivered: deliveries.filter(d => d.status === 'delivered').length,
            urgent: deliveries.filter(d => d.status === 'pending' && d.priority === 'urgent').length
        };
    }
};
