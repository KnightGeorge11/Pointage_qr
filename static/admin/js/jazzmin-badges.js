// static/admin/js/jazzmin-badges.js

(function($) {
    'use strict';

    $(document).ready(function() {
        // Récupérer les compteurs via l'API
        $.getJSON('/api/admin-badge-counts/', function(data) {
            // Badge pour les demandes
            if (data.demandes_attente > 0) {
                var badge = $('<span class="badge badge-danger right"></span>')
                    .css({
                        background: '#EF4444',
                        borderRadius: '9999px',
                        padding: '2px 8px',
                        fontSize: '10px',
                        marginLeft: '5px'
                    })
                    .text(data.demandes_attente);
                $('a[href*="demandemodification"]').find('p').append(badge);
            }

            // Badge pour les anomalies non traitées (uniquement "ouverte")
            if (data.anomalies_ouvertes > 0) {
                var badge = $('<span class="badge badge-danger right"></span>')
                    .css({
                        background: '#EF4444',
                        borderRadius: '9999px',
                        padding: '2px 8px',
                        fontSize: '10px',
                        marginLeft: '5px'
                    })
                    .text(data.anomalies_ouvertes);
                $('a[href*="anomaliepointage"]').find('p').append(badge);
            }
        });

        // ── Cloche de notifications ──
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

        function addNotificationItem($body, n) {
            var colorMap = {
                critique: '#EF4444',
                danger: '#EF4444',
                warning: '#F59E0B',
                success: '#22C55E',
                info: '#3B82F6'
            };
            var color = colorMap[n.gravite] || '#3B82F6';
            var icon = n.type === 'demande_traitee'
                ? (n.gravite === 'success' ? 'fa-circle-check' : 'fa-circle-xmark')
                : (n.type === 'demande_en_attente' ? 'fa-pen-to-square' : 'fa-triangle-exclamation');

            // Construire le DOM avec .text() et .attr() : les messages, noms
            // et URLs provenant de l'API ne doivent jamais être interprétés
            // comme du HTML (protection XSS côté administration).
            var $item = n.url ? $('<a></a>').attr('href', n.url) : $('<div></div>');
            $item.css({
                display: 'flex',
                gap: '10px',
                padding: '9px 14px',
                borderBottom: '1px solid rgba(0,0,0,.06)',
                textDecoration: 'none',
                color: '#333',
                fontSize: '12.5px'
            });

            var $icon = $('<span></span>').css({
                flexShrink: 0,
                width: '24px',
                height: '24px',
                borderRadius: '50%',
                background: color + '22',
                color: color,
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontSize: '10px'
            }).append($('<i></i>').addClass('fas ' + icon));

            var $content = $('<span></span>').css({flex: 1, minWidth: 0});
            $('<div></div>').text(n.message || '').appendTo($content);
            $('<div></div>').css({
                color: '#999',
                fontSize: '11px',
                marginTop: '2px'
            }).text(formatDate(n.date)).appendTo($content);

            $item.append($icon, $content);
            $body.append($item);
        }

        function loadAdminNotifications() {
            $.getJSON('/api/notifications/', function(data) {
                var items = Array.isArray(data.notifications) ? data.notifications : [];
                $('#jazzminNotifDot').css('display', items.length > 0 ? 'block' : 'none');
                var $body = $('#jazzminNotifBody').empty();

                if (items.length === 0) {
                    $('<div></div>').css({
                        padding: '16px',
                        textAlign: 'center',
                        color: '#999',
                        fontSize: '13px'
                    }).text('Aucune notification').appendTo($body);
                    return;
                }

                items.forEach(function(n) {
                    addNotificationItem($body, n);
                });
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
