// Script spécifique pour le scanner QR

class QRCodeScanner {
    constructor(options = {}) {
        this.options = {
            videoElementId: 'preview',
            resultElementId: 'result',
            siteSelectId: 'site-select',
            startButtonId: 'start-scanner',
            stopButtonId: 'stop-scanner',
            onScan: null,
            ...options
        };
        
        this.scanner = null;
        this.scanning = false;
        this.videoElement = null;
        this.resultElement = null;
        this.siteSelect = null;
        
        this.init();
    }
    
    init() {
        // Vérifier que Instascan est disponible
        if (typeof Instascan === 'undefined') {
            console.error('Instascan n\'est pas chargé');
            return;
        }
        
        // Récupérer les éléments DOM
        this.videoElement = document.getElementById(this.options.videoElementId);
        this.resultElement = document.getElementById(this.options.resultElementId);
        this.siteSelect = document.getElementById(this.options.siteSelectId);
        
        if (!this.videoElement || !this.resultElement) {
            console.error('Éléments DOM non trouvés');
            return;
        }
        
        // Initialiser le scanner
        this.scanner = new Instascan.Scanner({
            video: this.videoElement,
            mirror: false,
            backgroundScan: false,
            scanPeriod: 1
        });
        
        // Configurer l'événement de scan
        this.scanner.addListener('scan', (content) => {
            this.handleScan(content);
        });
        
        // Configurer les boutons
        this.setupControls();
    }
    
    setupControls() {
        const startButton = document.getElementById(this.options.startButtonId);
        const stopButton = document.getElementById(this.options.stopButtonId);
        
        if (startButton) {
            startButton.addEventListener('click', () => this.start());
        }
        
        if (stopButton) {
            stopButton.addEventListener('click', () => this.stop());
        }
    }
    
    async start() {
        try {
            const cameras = await Instascan.Camera.getCameras();
            
            if (cameras.length === 0) {
                this.showError('Aucune caméra disponible');
                return;
            }
            
            // Utiliser la caméra arrière si disponible, sinon la première
            const backCamera = cameras.find(c => c.name.toLowerCase().includes('back')) || cameras[0];
            
            await this.scanner.start(backCamera);
            this.scanning = true;
            
            this.showMessage('Scanner démarré', 'success');
            this.updateButtonStates(true);
            
        } catch (error) {
            this.showError(`Erreur: ${error.message}`);
        }
    }
    
    stop() {
        if (this.scanner && this.scanning) {
            this.scanner.stop();
            this.scanning = false;
            
            this.showMessage('Scanner arrêté', 'warning');
            this.updateButtonStates(false);
        }
    }
    
    handleScan(content) {
        if (this.options.onScan) {
            this.options.onScan(content);
            return;
        }
        
        // Traitement par défaut
        this.processQRContent(content);
    }
    
    async processQRContent(content) {
        // Vérifier que le site est sélectionné
        if (!this.siteSelect || !this.siteSelect.value) {
            this.showError('Veuillez sélectionner un site');
            return;
        }
        
        // Analyser le contenu du QR code
        const parts = content.split(':');
        
        if (parts.length === 3 && parts[0] === 'EMPLOYE') {
            const matricule = parts[1];
            
            // Envoyer au serveur
            const response = await this.sendScanToServer(matricule, this.siteSelect.value);
            
            if (response.success) {
                this.showScanSuccess(response);
            } else {
                this.showError(response.errors || 'Erreur lors du scan');
            }
        } else {
            this.showError('QR code non reconnu');
        }
    }
    
    async sendScanToServer(matricule, siteId) {
        try {
            const csrfToken = this.getCSRFToken();
            
            const response = await fetch('/api/scan/', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-CSRFToken': csrfToken
                },
                body: JSON.stringify({
                    employe_matricule: matricule,
                    site_id: siteId
                })
            });
            
            return await response.json();
            
        } catch (error) {
            return {
                success: false,
                errors: `Erreur réseau: ${error.message}`
            };
        }
    }
    
    showScanSuccess(data) {
        const html = `
            <div class="alert alert-success">
                <i class="fas fa-check-circle"></i>
                <strong>${data.message}</strong><br>
                <small>Employé: ${data.employe}</small><br>
                <small>Site: ${data.site}</small><br>
                <small>Prochain: ${data.prochain_scan}</small>
            </div>
        `;
        
        this.resultElement.innerHTML = html;
        this.playSuccessSound();
        
        // Réinitialiser après 3 secondes
        setTimeout(() => {
            if (this.scanning) {
                this.showMessage('Prêt pour le prochain scan', 'info');
            }
        }, 3000);
    }
    
    showMessage(message, type = 'info') {
        const icon = {
            'info': 'fas fa-info-circle',
            'success': 'fas fa-check-circle',
            'warning': 'fas fa-exclamation-triangle',
            'error': 'fas fa-times-circle'
        }[type];
        
        const alertClass = {
            'info': 'alert-info',
            'success': 'alert-success',
            'warning': 'alert-warning',
            'error': 'alert-danger'
        }[type];
        
        const html = `
            <div class="alert ${alertClass}">
                <i class="${icon}"></i> ${message}
            </div>
        `;
        
        this.resultElement.innerHTML = html;
    }
    
    showError(message) {
        this.showMessage(message, 'error');
    }
    
    updateButtonStates(scanning) {
        const startButton = document.getElementById(this.options.startButtonId);
        const stopButton = document.getElementById(this.options.stopButtonId);
        
        if (startButton) {
            startButton.disabled = scanning;
        }
        
        if (stopButton) {
            stopButton.disabled = !scanning;
        }
    }
    
    playSuccessSound() {
        // Créer un bip de succès
        try {
            const audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const oscillator = audioContext.createOscillator();
            const gainNode = audioContext.createGain();
            
            oscillator.connect(gainNode);
            gainNode.connect(audioContext.destination);
            
            oscillator.frequency.value = 800;
            oscillator.type = 'sine';
            
            gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
            gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
            
            oscillator.start(audioContext.currentTime);
            oscillator.stop(audioContext.currentTime + 0.5);
            
        } catch (error) {
            console.log('Audio context non supporté');
        }
    }
    
    getCSRFToken() {
        const name = 'csrftoken';
        let cookieValue = null;
        
        if (document.cookie && document.cookie !== '') {
            const cookies = document.cookie.split(';');
            
            for (let i = 0; i < cookies.length; i++) {
                const cookie = cookies[i].trim();
                
                if (cookie.substring(0, name.length + 1) === (name + '=')) {
                    cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                    break;
                }
            }
        }
        
        return cookieValue;
    }
}

// Initialiser le scanner quand la page est prête
document.addEventListener('DOMContentLoaded', function() {
    window.qrScanner = new QRCodeScanner();
});