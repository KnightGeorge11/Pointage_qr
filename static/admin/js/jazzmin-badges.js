// static/admin/js/jazzmin-badges.js

(function($) {
    'use strict';

    $(document).ready(function() {
        // Récupérer les compteurs via une API
        $.getJSON('/api/admin-badge-counts/', function(data) {
            // Ajouter le badge pour les demandes
            if (data.demandes_attente > 0) {
                var demandeLink = $('a[href*="demandemodification"]');
                if (demandeLink.length) {
                    var badge = $('<span class="badge badge-danger right" style="background: #EF4444; border-radius: 9999px; padding: 2px 8px; font-size: 10px; margin-left: 5px; animation: pulse-badge 2s ease-in-out infinite;">' + data.demandes_attente + '</span>');
                    demandeLink.find('p').append(badge);
                }
            }
            
            // Ajouter le badge pour les anomalies
            if (data.anomalies_ouvertes > 0) {
                var anomalieLink = $('a[href*="anomaliepointage"]');
                if (anomalieLink.length) {
                    var badge = $('<span class="badge badge-danger right" style="background: #EF4444; border-radius: 9999px; padding: 2px 8px; font-size: 10px; margin-left: 5px; animation: pulse-badge 2s ease-in-out infinite;">' + data.anomalies_ouvertes + '</span>');
                    anomalieLink.find('p').append(badge);
                }
            }
        });
    });

})(jQuery);