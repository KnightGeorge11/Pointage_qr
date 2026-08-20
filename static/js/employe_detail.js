// static/js/employe_detail.js
// Script pour la page de détail d'un employé

(function($) {
    'use strict';

    // Variables globales
    var currentMonth = parseInt($('#calendar-month').data('month'));
    var currentYear = parseInt($('#calendar-month').data('year'));
    var employeeId = parseInt($('#employee-id').data('id'));
    var selectedDate = null;

    // Initialisation
    $(document).ready(function() {
        // Charger le calendrier initial
        loadCalendar(currentMonth, currentYear);
        
        // Gestionnaire pour le bouton "Aujourd'hui"
        $('#btn-today').on('click', function(e) {
            e.preventDefault();
            var today = new Date();
            currentMonth = today.getMonth() + 1;
            currentYear = today.getFullYear();
            loadCalendar(currentMonth, currentYear);
            selectedDate = null;
        });

        // Gestionnaire pour le mois précédent
        $('#btn-prev-month').on('click', function(e) {
            e.preventDefault();
            if (currentMonth === 1) {
                currentMonth = 12;
                currentYear--;
            } else {
                currentMonth--;
            }
            loadCalendar(currentMonth, currentYear);
            selectedDate = null;
        });

        // Gestionnaire pour le mois suivant
        $('#btn-next-month').on('click', function(e) {
            e.preventDefault();
            if (currentMonth === 12) {
                currentMonth = 1;
                currentYear++;
            } else {
                currentMonth++;
            }
            loadCalendar(currentMonth, currentYear);
            selectedDate = null;
        });

        // Gestionnaire pour le clic sur le QR Code
        $('.employee-detail-qr').on('click', function(e) {
            e.preventDefault();
            var qrUrl = $('#employee-qr-code-img').attr('src');
            if (qrUrl) {
                $('#qr-modal-image').attr('src', qrUrl);
                $('#qr-modal').modal('show');
            }
        });

        // Gestionnaire pour le téléchargement du QR
        $('#qr-download-btn').on('click', function(e) {
            e.preventDefault();
            var imgSrc = $('#qr-modal-image').attr('src');
            if (imgSrc) {
                var link = document.createElement('a');
                var fileName = 'qr-code-' + employeeId + '.png';
                link.download = fileName;
                link.href = imgSrc;
                document.body.appendChild(link);
                link.click();
                document.body.removeChild(link);
            }
        });

        // Gestionnaire pour l'impression du QR
        $('#qr-print-btn').on('click', function(e) {
            e.preventDefault();
            var imgSrc = $('#qr-modal-image').attr('src');
            if (imgSrc) {
                var printWindow = window.open('', '_blank', 'width=600,height=600');
                printWindow.document.write('<!DOCTYPE html><html><head><title>QR Code</title>');
                printWindow.document.write('<style>');
                printWindow.document.write('body { text-align: center; padding: 50px; font-family: Arial, sans-serif; }');
                printWindow.document.write('img { max-width: 400px; border: 2px solid #E2E8F0; border-radius: 8px; padding: 20px; }');
                printWindow.document.write('.title { font-size: 20px; font-weight: bold; margin-bottom: 20px; color: #0F172A; }');
                printWindow.document.write('</style>');
                printWindow.document.write('</head><body>');
                printWindow.document.write('<div class="title">QR Code</div>');
                printWindow.document.write('<img src="' + imgSrc + '" alt="QR Code">');
                printWindow.document.write('</body></html>');
                printWindow.document.close();
                printWindow.focus();
                printWindow.print();
            }
        });

        // Sélectionner automatiquement aujourd'hui si disponible
        setTimeout(function() {
            var today = getToday();
            var todayCell = $('.day-cell[data-date="' + today + '"]');
            if (todayCell.length > 0) {
                todayCell.trigger('click');
            }
        }, 600);
    });

    // Fonction pour charger le calendrier
    function loadCalendar(month, year) {
        var monthNames = ['Janvier', 'Février', 'Mars', 'Avril', 'Mai', 'Juin',
                          'Juillet', 'Août', 'Septembre', 'Octobre', 'Novembre', 'Décembre'];
        $('#calendar-title').text(monthNames[month - 1] + ' ' + year);
        
        $('#calendar-month').data('month', month);
        $('#calendar-month').data('year', year);

        $('#calendar-grid').html('<div class="text-center py-4"><i class="fas fa-spinner fa-spin"></i> Chargement...</div>');

        $.ajax({
            url: '/api/pointages-mois/',
            method: 'GET',
            data: {
                employee_id: employeeId,
                month: month,
                year: year
            },
            success: function(response) {
                renderCalendar(response, month, year);
                
                var today = getToday();
                var todayCell = $('.day-cell[data-date="' + today + '"]');
                if (todayCell.length > 0 && !selectedDate) {
                    selectedDate = today;
                    todayCell.addClass('selected');
                    loadDayDetails(today);
                } else if (selectedDate) {
                    var cell = $('.day-cell[data-date="' + selectedDate + '"]');
                    if (cell.length > 0) {
                        cell.addClass('selected');
                        loadDayDetails(selectedDate);
                    }
                }
            },
            error: function(xhr, status, error) {
                console.error('Erreur:', error);
                $('#calendar-grid').html('<div class="alert alert-danger">Erreur lors du chargement.</div>');
            }
        });
    }

    // Fonction pour afficher le calendrier
    function renderCalendar(data, month, year) {
        var firstDay = new Date(year, month - 1, 1).getDay();
        var daysInMonth = new Date(year, month, 0).getDate();
        var today = getToday();

        var html = '<table class="employee-detail-calendar-table">';
        html += '<thead><tr>';
        html += '<th>Lun</th><th>Mar</th><th>Mer</th><th>Jeu</th>';
        html += '<th>Ven</th><th>Sam</th><th>Dim</th>';
        html += '</tr></thead><tbody><tr>';

        var startOffset = (firstDay === 0) ? 6 : firstDay - 1;
        
        for (var i = 0; i < startOffset; i++) {
            html += '<td class="empty"></td>';
        }

        for (var day = 1; day <= daysInMonth; day++) {
            var dateStr = year + '-' + String(month).padStart(2, '0') + '-' + String(day).padStart(2, '0');
            var statut = data[dateStr] ? data[dateStr].statut : 'none';
            
            var classNames = 'day-cell';
            if (dateStr === today) {
                classNames += ' today';
            }
            if (statut !== 'none') {
                classNames += ' statut-' + statut;
            }
            if (selectedDate === dateStr) {
                classNames += ' selected';
            }
            
            html += '<td class="' + classNames + '" data-date="' + dateStr + '" data-statut="' + statut + '">';
            html += '<div class="day-number">' + day + '</div>';
            
            if (statut !== 'none') {
                var iconClass = getStatutIcon(statut);
                html += '<div class="day-indicator"><i class="' + iconClass + '"></i></div>';
            }
            
            html += '</td>';
            
            if ((startOffset + day) % 7 === 0 && day < daysInMonth) {
                html += '</tr><tr>';
            }
        }

        var remaining = (7 - ((startOffset + daysInMonth) % 7)) % 7;
        for (var j = 0; j < remaining; j++) {
            html += '<td class="empty"></td>';
        }

        html += '</tr></tbody></table>';
        $('#calendar-grid').html(html);

        $('.day-cell').on('click', function() {
            var date = $(this).data('date');
            selectedDate = date;
            loadDayDetails(date);
            $('.day-cell').removeClass('selected');
            $(this).addClass('selected');
        });
    }

    // Fonction pour charger les détails d'une journée
    function loadDayDetails(date) {
        $('#day-details').html('<div class="text-center py-4"><i class="fas fa-spinner fa-spin"></i> Chargement...</div>');
        
        $.ajax({
            url: '/api/pointages-jour/',
            method: 'GET',
            data: {
                employee_id: employeeId,
                date: date
            },
            success: function(response) {
                renderDayDetails(date, response);
            },
            error: function(xhr, status, error) {
                console.error('Erreur:', error);
                $('#day-details').html('<div class="alert alert-danger">Erreur lors du chargement.</div>');
            }
        });
    }

    // Fonction pour afficher les détails d'une journée
    function renderDayDetails(date, data) {
        if (!date) {
            $('#day-details').html('<div class="text-center py-4 text-muted">Sélectionnez une date.</div>');
            return;
        }

        var pointages = data[date] || null;
        var details = '';
        
        if (pointages) {
            var statut = pointages.statut || 'none';
            var jour = new Date(date + 'T00:00:00');
            var dateFormatee = jour.toLocaleDateString('fr-FR', { 
                weekday: 'long', 
                day: 'numeric', 
                month: 'long', 
                year: 'numeric' 
            });
            
            details += '<h5 class="employee-detail-day-title">' + dateFormatee.charAt(0).toUpperCase() + dateFormatee.slice(1) + '</h5>';
            details += '<div class="employee-detail-day-pointages">';
            
            var hasPointages = false;
            if (pointages.heure_entree_matin) {
                details += '<div class="pointage-row"><span class="pointage-label">Entrée matin</span><span class="pointage-value">' + pointages.heure_entree_matin + '</span></div>';
                hasPointages = true;
            }
            if (pointages.heure_sortie_midi) {
                details += '<div class="pointage-row"><span class="pointage-label">Sortie midi</span><span class="pointage-value">' + pointages.heure_sortie_midi + '</span></div>';
                hasPointages = true;
            }
            if (pointages.heure_entree_apres_midi) {
                details += '<div class="pointage-row"><span class="pointage-label">Entrée après-midi</span><span class="pointage-value">' + pointages.heure_entree_apres_midi + '</span></div>';
                hasPointages = true;
            }
            if (pointages.heure_sortie_soir) {
                details += '<div class="pointage-row"><span class="pointage-label">Sortie soir</span><span class="pointage-value">' + pointages.heure_sortie_soir + '</span></div>';
                hasPointages = true;
            }
            
            if (!hasPointages) {
                details += '<div class="text-muted text-center py-2">Aucun pointage ce jour.</div>';
            }
            
            details += '</div>';
            
            var statutLabel = getStatutLabel(statut);
            var statutIcon = getStatutIcon(statut);
            details += '<div class="employee-detail-day-statut">';
            details += '<span class="statut-label">Statut de la journée</span>';
            details += '<span class="statut-value statut-' + statut + '"><i class="' + statutIcon + '"></i> ' + statutLabel + '</span>';
            details += '</div>';
            
            var nbPointages = pointages.nb_pointages || 0;
            var resume = '';
            if (nbPointages === 0) {
                resume = 'Aucun pointage enregistré ce jour.';
            } else if (nbPointages >= 4) {
                resume = 'Journée complète avec ' + nbPointages + ' pointages.';
            } else {
                resume = nbPointages + ' pointage(s) enregistré(s) ce jour.';
            }
            details += '<div class="employee-detail-day-resume"><i class="fas fa-info-circle"></i> ' + resume + '</div>';
            
            if (pointages.anomalies && pointages.anomalies.length > 0) {
                details += '<div class="employee-detail-day-anomalies">';
                details += '<h6><i class="fas fa-exclamation-triangle text-warning"></i> Anomalies</h6>';
                pointages.anomalies.forEach(function(anomalie) {
                    details += '<div class="anomalie-item"><span class="badge badge-warning">' + anomalie.code + '</span> ' + anomalie.libelle + '</div>';
                });
                details += '</div>';
            }
        } else {
            details = '<div class="text-center py-4 text-muted">Aucun pointage enregistré pour cette date.</div>';
        }
        
        $('#day-details').html(details);
    }

    // Fonctions utilitaires
    function getStatutLabel(statut) {
        var labels = {
            'normal': 'Normal',
            'retard': 'Retard',
            'anomalie': 'Anomalie',
            'absence': 'Absence',
            'incomplet': 'Incomplet',
            'none': 'Non pointé'
        };
        return labels[statut] || statut;
    }

    function getStatutIcon(statut) {
        var icons = {
            'normal': 'fas fa-check-circle text-success',
            'retard': 'fas fa-clock text-warning',
            'anomalie': 'fas fa-exclamation-triangle text-danger',
            'absence': 'fas fa-circle text-muted',
            'incomplet': 'fas fa-minus-circle text-info',
            'none': 'fas fa-circle text-muted'
        };
        return icons[statut] || icons['none'];
    }

    function getToday() {
        var today = new Date();
        return today.getFullYear() + '-' + 
               String(today.getMonth() + 1).padStart(2, '0') + '-' + 
               String(today.getDate()).padStart(2, '0');
    }

})(jQuery);