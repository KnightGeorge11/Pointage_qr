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
            
            // Badge pour les anomalies non traitées (jamais toutes les
            // anomalies, uniquement celles au statut "ouverte")
            if (data.anomalies_ouvertes > 0) {
                var badge = $('<span class="badge badge-danger right" style="background: #EF4444; border-radius: 9999px; padding: 2px 8px; font-size: 10px; margin-left: 5px;">' + data.anomalies_ouvertes + '</span>');
                $('a[href*="anomaliepointage"]').find('p').append(badge);
            }
            
        });

        // ── Cloche de notifications (même API/contenu que le dashboard
        // côté utilisateur : anomalies ouvertes récentes + demandes de
        // modification en attente de décision) ──
        var $navbar = $('.navbar-nav.ms-auto');
        if ($navbar.length === 0) return;

        var $bell = $(
            '<li class="nav-item dropdown" id="jazzminNotifWrap">' +
                '<a class="nav-link" href="#" role="button" id="jazzminNotifBtn" style="position:relative;">' +
                    '<i class="fas fa-bell"></i>' +
                    '<span id="jazzminNotifDot" style="display:none;position:absolute;top:8px;right:8px;width:7px;height:7px;border-radius:50%;background:#EF4444;border:1px solid #fff;"></span>' +
                '</a>' +
                '<div id="jazzminNotifDropdown" style="display:none;position:absolute;right:0;top:100%;width:320px;max-height:400px;overflow-y:auto;background:#fff;border:1px solid rgba(0,0,0,.12);border-radius:6px;box-shadow:0 8px 24px rgba(0,0,0,.15);z-index:1050;">' +
                    '<div style="padding:10px 14px;font-weight:600;font-size:13px;border-bottom:1px solid rgba(0,0,0,.08);">Notifications</div>' +
                    '<div id="jazzminNotifBody"><div style="padding:16px;text-align:center;color:#999;font-size:13px;">Chargement…</div></div>' +
                '</div>' +
            '</li>'
        );
        $navbar.prepend($bell);

        function formatDate(iso) {
            if (!iso) return '';
            var d = new Date(iso);
            return d.toLocaleDateString('fr-FR', {day: '2-digit', month: '2-digit'}) + ' à ' +
                   d.toLocaleTimeString('fr-FR', {hour: '2-digit', minute: '2-digit'});
        }

        function loadAdminNotifications() {
            $.getJSON('/api/notifications/', function(data) {
                var items = data.notifications || [];
                $('#jazzminNotifDot').css('display', items.length > 0 ? 'block' : 'none');
                var $body = $('#jazzminNotifBody');
                if (items.length === 0) {
                    $body.html('<div style="padding:16px;text-align:center;color:#999;font-size:13px;">Aucune notification</div>');
                    return;
                }
                var html = items.map(function(n) {
                    var color = {critique: '#EF4444', danger: '#EF4444', warning: '#F59E0B', success: '#22C55E', info: '#3B82F6'}[n.gravite] || '#3B82F6';
                    var icon = n.type === 'demande_traitee'
                        ? (n.gravite === 'success' ? 'fa-circle-check' : 'fa-circle-xmark')
                        : (n.type === 'demande_en_attente' ? 'fa-pen-to-square' : 'fa-triangle-exclamation');
                    var tag = n.url ? 'a href="' + n.url + '"' : 'div';
                    var closeTag = n.url ? 'a' : 'div';
                    return '<' + tag + ' style="display:flex;gap:10px;padding:9px 14px;border-bottom:1px solid rgba(0,0,0,.06);text-decoration:none;color:#333;font-size:12.5px;">' +
                        '<span style="flex-shrink:0;width:24px;height:24px;border-radius:50%;background:' + color + '22;color:' + color + ';display:flex;align-items:center;justify-content:center;font-size:10px;"><i class="fas ' + icon + '"></i></span>' +
                        '<span style="flex:1;min-width:0;">' +
                            '<div>' + n.message + '</div>' +
                            '<div style="color:#999;font-size:11px;margin-top:2px;">' + formatDate(n.date) + '</div>' +
                        '</span>' +
                    '</' + closeTag + '>';
                }).join('');
                $body.html(html);
            });
        }

        loadAdminNotifications();
        setInterval(loadAdminNotifications, 60000);

        $('#jazzminNotifBtn').on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var $dd = $('#jazzminNotifDropdown');
            if ($dd.is(':visible')) {
                $dd.hide();
            } else {
                $dd.show();
                loadAdminNotifications();
            }
        });

        $(document).on('click', function(e) {
            if (!$(e.target).closest('#jazzminNotifWrap').length) {
                $('#jazzminNotifDropdown').hide();
            }
        });
    });

})(jQuery);