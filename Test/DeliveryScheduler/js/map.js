/**
 * map.js - Authentication & Rendering for the Map
 * Handles render logic. Currently uses a Canvas mock to visualize data 
 * without needing an API key immediately.
 */

export class MapManager {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.ctx = null;
        this.canvas = null;
        this.markers = [];
        this.init();
    }

    init() {
        this.container.innerHTML = '';
        this.canvas = document.createElement('canvas');
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.canvas.style.display = 'block';
        this.container.appendChild(this.canvas);

        this.ctx = this.canvas.getContext('2d');

        // Handle resize
        this.resize();
        window.addEventListener('resize', () => {
            this.resize();
            this.render();
        });

        // Start animation loop
        this.animate();
    }

    resize() {
        const rect = this.container.getBoundingClientRect();
        this.canvas.width = rect.width;
        this.canvas.height = rect.height;
    }

    // Add a marker (Mock: random position on canvas)
    addMarker(delivery) {
        // In a real app, we'd use lat/lng. Here we generate a stable random position
        // based on the ID string to mock "geocoding"
        const pseudoRandom = (str) => {
            let hash = 0;
            for (let i = 0; i < str.length; i++) {
                hash = str.charCodeAt(i) + ((hash << 5) - hash);
            }
            return Math.abs(hash);
        };

        const x = (pseudoRandom(delivery.pickup) % 80) + 10; // 10-90% width
        const y = (pseudoRandom(delivery.dropoff) % 80) + 10; // 10-90% height

        this.markers.push({
            x: x / 100, // Normalized coordinates
            y: y / 100,
            color: this.getPriorityColor(delivery.priority),
            data: delivery,
            pulse: 0
        });
    }

    clearMarkers() {
        this.markers = [];
    }

    getPriorityColor(priority) {
        switch (priority) {
            case 'urgent': return '#ef4444';
            case 'high': return '#f59e0b';
            case 'standard': return '#3b82f6';
            default: return '#10b981';
        }
    }

    render() {
        const w = this.canvas.width;
        const h = this.canvas.height;

        // Clear
        this.ctx.fillStyle = '#1e1e1e'; // Dark Map Background
        this.ctx.fillRect(0, 0, w, h);

        // Draw "Streets" (Grid lines to look like a map)
        this.ctx.strokeStyle = '#333';
        this.ctx.lineWidth = 2;

        // Vertical lines
        for (let i = 0; i < w; i += 100) {
            this.ctx.beginPath();
            this.ctx.moveTo(i, 0);
            this.ctx.lineTo(i, h);
            this.ctx.stroke();
        }
        // Horizontal lines
        for (let i = 0; i < h; i += 100) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, i);
            this.ctx.lineTo(w, i);
            this.ctx.stroke();
        }

        // Draw Markers
        this.markers.forEach(m => {
            const mx = m.x * w;
            const my = m.y * h;

            // Pulse effect
            this.ctx.beginPath();
            this.ctx.arc(mx, my, 10 + m.pulse, 0, Math.PI * 2);
            this.ctx.fillStyle = m.color + '40'; // Transparent fade
            this.ctx.fill();

            // Core dot
            this.ctx.beginPath();
            this.ctx.arc(mx, my, 6, 0, Math.PI * 2);
            this.ctx.fillStyle = m.color;
            this.ctx.fill();
            this.ctx.strokeStyle = '#fff';
            this.ctx.lineWidth = 2;
            this.ctx.stroke();

            // Label
            this.ctx.fillStyle = '#fff';
            this.ctx.font = '12px Inter';
            this.ctx.fillText(m.data.pickup.substring(0, 15) + '...', mx + 12, my + 4);
        });
    }

    animate() {
        this.markers.forEach(m => {
            m.pulse = (Math.sin(Date.now() / 300) + 1) * 5; // 0 to 10px pulse
        });
        this.render();
        requestAnimationFrame(() => this.animate());
    }
}
