/**
 * app.js - Main Controller
 */
import { Store } from './store.js';
import { MapManager } from './map.js';
import { UI } from './ui.js';

class App {
    constructor() {
        this.map = new MapManager('map-container');
        this.initEventListeners();
        this.refresh();
    }

    initEventListeners() {
        // Modal Controls
        const addBtn = document.getElementById('add-btn');
        const closeBtns = document.querySelectorAll('.close-modal');
        const modalId = 'delivery-modal';

        addBtn.addEventListener('click', () => UI.toggleModal(modalId, true));
        closeBtns.forEach(btn => btn.addEventListener('click', () => UI.toggleModal(modalId, false)));

        // Form Submission
        const form = document.getElementById('delivery-form');
        form.addEventListener('submit', (e) => {
            e.preventDefault();
            this.handleNewDelivery(new FormData(form));
            form.reset();
            UI.toggleModal(modalId, false);
        });
    }

    handleNewDelivery(formData) {
        const delivery = {
            pickup: formData.get('pickup'),
            dropoff: formData.get('dropoff'),
            deadline: formData.get('deadline'),
            priority: formData.get('priority'),
            notes: formData.get('notes')
        };

        Store.addDelivery(delivery);
        this.refresh();
    }

    refresh() {
        const deliveries = Store.getDeliveries();
        const stats = Store.getStats();

        // 1. Update List
        UI.renderList(deliveries, 'shipment-list');

        // 2. Update Stats
        UI.updateStats(stats);

        // 3. Update Map
        this.map.clearMarkers();
        deliveries.forEach(d => {
            if (d.status === 'pending') {
                this.map.addMarker(d);
            }
        });
        this.map.render();
    }
}

// Start App
window.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
