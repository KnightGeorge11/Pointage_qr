// Script principal pour Pointage QR

document.addEventListener('DOMContentLoaded', function() {
    // Initialiser les tooltips Bootstrap
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    var tooltipList = tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Initialiser les popovers
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    var popoverList = popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Gérer la suppression des alertes
    setTimeout(function() {
        var alerts = document.querySelectorAll('.alert');
        alerts.forEach(function(alert) {
            var bsAlert = new bootstrap.Alert(alert);
            setTimeout(function() {
                bsAlert.close();
            }, 5000);
        });
    }, 3000);
    
    // Formatage des dates et heures
    function formatTime(timeString) {
        if (!timeString) return '-';
        const date = new Date('1970-01-01T' + timeString + 'Z');
        return date.toLocaleTimeString('fr-FR', { 
            hour: '2-digit', 
            minute: '2-digit',
            timeZone: 'UTC'
        });
    }
    
    // Appliquer le formatage aux heures dans les tables
    document.querySelectorAll('.time-cell').forEach(function(cell) {
        if (cell.textContent.trim() && cell.textContent.trim() !== '-') {
            cell.textContent = formatTime(cell.textContent.trim());
        }
    });
    
    // Gestion du rafraîchissement automatique des données
    if (window.location.pathname === '/') {
        setInterval(function() {
            fetch('/api/pointages/statistiques/')
                .then(response => response.json())
                .then(data => {
                    // Mettre à jour les statistiques
                    document.querySelectorAll('[data-stat="total_employes"]').forEach(el => {
                        el.textContent = data.total_employes;
                    });
                    document.querySelectorAll('[data-stat="presents_aujourdhui"]').forEach(el => {
                        el.textContent = data.presents_aujourdhui;
                    });
                    document.querySelectorAll('[data-stat="absents_aujourdhui"]').forEach(el => {
                        el.textContent = data.absents_aujourdhui;
                    });
                    document.querySelectorAll('[data-stat="retards_aujourdhui"]').forEach(el => {
                        el.textContent = data.retards_aujourdhui;
                    });
                })
                .catch(error => console.error('Erreur de rafraîchissement:', error));
        }, 30000); // Rafraîchir toutes les 30 secondes
    }
    
    // Export CSV
    document.querySelectorAll('.export-csv').forEach(function(button) {
        button.addEventListener('click', function(e) {
            e.preventDefault();
            const table = this.closest('.table-responsive').querySelector('table');
            let csv = [];
            const rows = table.querySelectorAll('tr');
            
            rows.forEach(function(row) {
                const rowData = [];
                const cells = row.querySelectorAll('th, td');
                
                cells.forEach(function(cell) {
                    // Nettoyer le contenu
                    let text = cell.textContent.trim();
                    text = text.replace(/\s+/g, ' ');
                    text = text.replace(/"/g, '""');
                    rowData.push('"' + text + '"');
                });
                
                csv.push(rowData.join(','));
            });
            
            const csvContent = csv.join('\n');
            const blob = new Blob([csvContent], { type: 'text/csv;charset=utf-8;' });
            const link = document.createElement('a');
            const url = URL.createObjectURL(blob);
            
            link.setAttribute('href', url);
            link.setAttribute('download', 'export_' + new Date().toISOString().split('T')[0] + '.csv');
            link.style.visibility = 'hidden';
            
            document.body.appendChild(link);
            link.click();
            document.body.removeChild(link);
        });
    });
    
    // Recherche en temps réel dans les tables
    document.querySelectorAll('.table-search').forEach(function(input) {
        input.addEventListener('keyup', function() {
            const searchTerm = this.value.toLowerCase();
            const table = this.closest('.card').querySelector('table');
            const rows = table.querySelectorAll('tbody tr');
            
            rows.forEach(function(row) {
                const text = row.textContent.toLowerCase();
                row.style.display = text.includes(searchTerm) ? '' : 'none';
            });
        });
    });
    
    // Confirmation pour les actions de suppression
    document.querySelectorAll('.confirm-delete').forEach(function(link) {
        link.addEventListener('click', function(e) {
            if (!confirm('Êtes-vous sûr de vouloir supprimer cet élément ?')) {
                e.preventDefault();
            }
        });
    });
    
    // Affichage des QR codes en modal
    document.querySelectorAll('.qr-code-preview').forEach(function(img) {
        img.addEventListener('click', function() {
            const modal = document.createElement('div');
            modal.className = 'modal fade';
            modal.innerHTML = `
                <div class="modal-dialog modal-dialog-centered">
                    <div class="modal-content">
                        <div class="modal-header">
                            <h5 class="modal-title">QR Code</h5>
                            <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body text-center">
                            <img src="${this.src}" alt="QR Code" class="img-fluid" style="max-width: 300px;">
                        </div>
                        <div class="modal-footer">
                            <a href="${this.src}" download class="btn btn-primary">
                                <i class="fas fa-download"></i> Télécharger
                            </a>
                        </div>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            const modalInstance = new bootstrap.Modal(modal);
            modalInstance.show();
            
            modal.addEventListener('hidden.bs.modal', function() {
                modal.remove();
            });
        });
    });
    
    // Fonction pour formater les durées
    window.formatDuration = function(seconds) {
        if (!seconds) return '00:00';
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}`;
    };
    
    // Mettre à jour l'heure actuelle dans le header
    function updateCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('fr-FR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        document.querySelectorAll('.current-time').forEach(el => {
            el.textContent = timeString;
        });
    }
    
    setInterval(updateCurrentTime, 60000);
    updateCurrentTime();
});