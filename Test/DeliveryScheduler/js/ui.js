/**
 * ui.js - DOM Manipulation Helpers
 */

export const UI = {
    // Render list of delivery cards
    renderList(deliveries, containerId) {
        const container = document.getElementById(containerId);
        container.innerHTML = '';

        if (deliveries.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <i class="ri-inbox-archive-line"></i>
                    <p>No scheduled deliveries yet</p>
                </div>`;
            return;
        }

        deliveries.forEach(d => {
            const card = document.createElement('div');
            card.className = `shipment-card priority-${d.priority}`;

            // Format time
            const date = new Date(d.deadline);
            const timeStr = date.toLocaleString('en-US', {
                weekday: 'short', hour: 'numeric', minute: '2-digit'
            });

            card.innerHTML = `
                <div class="card-header">
                    <span class="time-badge"><i class="ri-time-line"></i> ${timeStr}</span>
                    <span class="priority-badge">${d.priority}</span>
                </div>
                <div class="route-info">
                    <div class="route-point">
                        <i class="ri-map-pin-line"></i>
                        <span>${d.pickup}</span>
                    </div>
                    <div class="route-point">
                        <i class="ri-arrow-down-line" style="margin-left: 3px; opacity:0.5; font-size:0.8rem"></i>
                    </div>
                    <div class="route-point">
                        <i class="ri-map-pin-user-line"></i>
                        <span>${d.dropoff}</span>
                    </div>
                </div>
            `;
            container.appendChild(card);
        });
    },

    // Update the 4 stats cards
    updateStats(stats) {
        document.getElementById('stat-total').textContent = stats.total;
        document.getElementById('stat-pending').textContent = stats.pending;
        document.getElementById('stat-delivered').textContent = stats.delivered;
        document.getElementById('stat-urgent').textContent = stats.urgent;
    },

    // Toggle Modal
    toggleModal(modalId, show = true) {
        const modal = document.getElementById(modalId);
        if (show) {
            modal.classList.remove('hidden');
        } else {
            modal.classList.add('hidden');
        }
    }
};
