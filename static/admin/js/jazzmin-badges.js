// static/admin/js/jazzmin-badges.js

(function($) {
    'use strict';

    $(document).ready(function() {
        // Récupérer les compteurs via l'API
        $.getJSON('/api/admin-badge-counts/', function(data) {
            
            // Badge pour les demandes
            if (data.demandes_attente > 0) {
                var badge = $('<span class="badge badge-danger right" style="background: #EF4444; border-radius: 9999px; padding: 2px 8px; font-size: 10px; margin-left: 5px;">' + data.demandes_attente + '</span>');
                $('a[href*="demandemodification"]').find('p').append(badge);
            }
            
            // Badge pour les anomalies
            if (data.anomalies_ouvertes > 0) {
                var badge = $('<span class="badge badge-danger right" style="background: #EF4444; border-radius: 9999px; padding: 2px 8px; font-size: 10px; margin-left: 5px;">' + data.anomalies_ouvertes + '</span>');
                $('a[href*="anomaliepointage"]').find('p').append(badge);
            }
            
        });
    });

})(jQuery);