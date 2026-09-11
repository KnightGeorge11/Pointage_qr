// static/admin/js/jazzmin-badges.js

(function($) {
    'use strict';

    $(document).ready(function() {
        $.getJSON('/api/admin-badge-counts/', function(data) {
            if (data.demandes_attente > 0) {
                var badge = $('<span class="badge badge-danger right"></span>')
                    .css({background: '#EF4444', borderRadius: '9999px', padding: '2px 8px', fontSize: '10px', marginLeft: '5px'})
                    .text(data.demandes_attente);
                $('a[href*="demandemodification"]').find('p').append(badge);
            }
            if (data.anomalies_ouvertes > 0) {
                var badge = $('<span class="badge badge-danger right"></span>')
                    .css({background: '#EF4444', borderRadius: '9999px', padding: '2px 8px', fontSize: '10px', marginLeft: '5px'})
                    .text(data.anomalies_ouvertes);
            }
        });

        // Journal d'audit directement sur le dashboard Jazzmin.
        // Le endpoint est protégé côté serveur : seuls les comptes RH/admin
        // peuvent recevoir ces données.
        if (window.location.pathname === '/admin/' || window.location.pathname === '/admin') {
            function loadDashboardAudit() {
                $.getJSON('/api/admin-audit/', function(data) {
                    var audits = Array.isArray(data.audits) ? data.audits : [];
                    $('#jazzminAuditDashboard').remove();

                    var $card = $('<div id="jazzminAuditDashboard"></div>').css({
                        margin: '20px 0 0',
                        background: '#fff',
                        border: '1px solid #E2E8F0',
                        borderRadius: '14px',
                        boxShadow: '0 1px 2px rgba(15,23,42,0.05)',
                        overflow: 'hidden',
                        width: '100%'
                    });

                    var $header = $('<div></div>').css({
                        padding: '16px 20px',
                        borderBottom: '1px solid #E2E8F0',
                        display: 'flex',
                        justifyContent: 'space-between',
                        alignItems: 'center',
                        gap: '12px'
                    });
                    $('<h3></h3>').css({margin: 0, fontSize: '14px', fontWeight: 600, color: '#0F172A'})
                        .html('<i class="fas fa-shield-halved" style="color:#2563EB;margin-right:8px;"></i>Audit récent')
                        .appendTo($header);
                    $('<a></a>').attr('href', '/admin/pointage/pointageaudit/')
                        .css({fontSize: '12px', fontWeight: 600, color: '#2563EB', textDecoration: 'none'})
                        .html('Voir tout <i class="fas fa-arrow-right" style="font-size:10px;"></i>')
                        .appendTo($header);
                    $card.append($header);

                    var $body = $('<div></div>').css({padding: 0, maxHeight: '360px', overflowY: 'auto'});
                    if (audits.length === 0) {
                        $('<div></div>').css({padding: '24px', textAlign: 'center', color: '#94A3B8', fontSize: '13px'})
                            .html('<i class="fas fa-shield-halved" style="font-size:22px;display:block;margin-bottom:8px;"></i>Aucune entrée d’audit récente')
                            .appendTo($body);
                    } else {
                        audits.forEach(function(audit) {
                            var $item = $('<a></a>').attr('href', audit.url || '#').css({
                                display: 'block',
                                padding: '12px 20px',
                                borderBottom: '1px solid #E2E8F0',
                                textDecoration: 'none',
                                color: 'inherit'
                            });
                            var $top = $('<div></div>').css({display: 'flex', justifyContent: 'space-between', gap: '12px', alignItems: 'center'});
                            $('<strong></strong>').css({fontSize: '12px', color: '#0F172A'}).text(audit.action || 'Action').appendTo($top);
                            $('<span></span>').css({fontSize: '10px', color: '#94A3B8', whiteSpace: 'nowrap'}).text(formatDate(audit.date)).appendTo($top);
                            $item.append($top);
                            $('<div></div>').css({fontSize: '12px', color: '#64748B', marginTop: '4px'})
                                .text((audit.employe || audit.pointage || 'Pointage') + ' · ' + (audit.administrateur || 'Système'))
                                .appendTo($item);
                            if (audit.motif && audit.motif !== '—') {
                                $('<div></div>').css({fontSize: '11px', color: '#94A3B8', marginTop: '3px'})
                                    .text('Motif : ' + audit.motif)
                                    .appendTo($item);
                            }
                            $body.append($item);
                        });
                    }
                    $card.append($body);

                    // Le dashboard personnalisé est rendu dans #content-main par Jazzmin.
                    // On l'insère en tête pour qu'il soit immédiatement visible.
                    var $anchor = $('#content-main').first();
                    if ($anchor.length === 0) $anchor = $('.content-wrapper .content').first();
                    if ($anchor.length > 0) {
                        $anchor.prepend($card);
                    }
                }).fail(function() {
                    // Ne pas masquer le problème : afficher un état visible sur le dashboard.
                    $('#jazzminAuditDashboard').remove();
                    var $error = $('<div id="jazzminAuditDashboard"></div>').css({
                        margin: '20px 0 0', padding: '16px 20px', background: '#FFF7ED',
                        border: '1px solid #FED7AA', borderRadius: '14px', color: '#9A3412', fontSize: '13px'
                    }).text('Audit : impossible de charger le journal.');
                    var $anchor = $('#content-main').first();
                    if ($anchor.length === 0) $anchor = $('.content-wrapper .content').first();
                    if ($anchor.length > 0) $anchor.prepend($error);
                });
            }

            loadDashboardAudit();
            setInterval(loadDashboardAudit, 60000);
        }

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
            var colorMap = {critique: '#EF4444', danger: '#EF4444', warning: '#F59E0B', success: '#22C55E', info: '#3B82F6'};
            var color = colorMap[n.gravite] || '#3B82F6';
            var icon = n.type === 'demande_traitee'
                ? (n.gravite === 'success' ? 'fa-circle-check' : 'fa-circle-xmark')
                : (n.type === 'demande_en_attente' ? 'fa-pen-to-square' : 'fa-triangle-exclamation');

            var $item = n.url ? $('<a></a>').attr('href', n.url) : $('<div></div>');
            $item.css({display: 'flex', gap: '10px', padding: '9px 14px', borderBottom: '1px solid rgba(0,0,0,.06)', textDecoration: 'none', color: '#333', fontSize: '12.5px'});

            var $icon = $('<span></span>').css({flexShrink: 0, width: '24px', height: '24px', borderRadius: '50%', background: color + '22', color: color, display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '10px'}).append($('<i></i>').addClass('fas ' + icon));
            var $content = $('<span></span>').css({flex: 1, minWidth: 0});
            $('<div></div>').text(n.message || '').appendTo($content);
            $('<div></div>').css({color: '#999', fontSize: '11px', marginTop: '2px'}).text(formatDate(n.date)).appendTo($content);
            $item.append($icon, $content);
            $body.append($item);
        }

        function loadAdminNotifications() {
            $.getJSON('/api/admin-notifications/', function(data) {
                var items = Array.isArray(data.notifications) ? data.notifications : [];
                $('#jazzminNotifDot').css('display', items.length > 0 ? 'block' : 'none');
                var $body = $('#jazzminNotifBody').empty();
                if (items.length === 0) {
                    $('<div></div>').css({padding: '16px', textAlign: 'center', color: '#999', fontSize: '13px'}).text('Aucune notification').appendTo($body);
                    return;
                }
                items.forEach(function(n) { addNotificationItem($body, n); });
            });
        }

        loadAdminNotifications();
        setInterval(loadAdminNotifications, 60000);

        $('#jazzminNotifBtn').on('click', function(e) {
            e.preventDefault();
            e.stopPropagation();
            var $dd = $('#jazzminNotifDropdown');
            if ($dd.is(':visible')) $dd.hide();
            else { $dd.show(); loadAdminNotifications(); }
        });

        $(document).on('click', function(e) {
            if (!$(e.target).closest('#jazzminNotifWrap').length) $('#jazzminNotifDropdown').hide();
        });
    });
})(jQuery);
