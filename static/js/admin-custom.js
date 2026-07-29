/* =====================================================
   ADMIN CUSTOM - JavaScript
   Uniquement des améliorations UX
   ===================================================== */

(function($) {
    'use strict';

    $(document).ready(function() {

        // ─── Auto-dismiss des messages ──────────────────────
        $('.alert').each(function() {
            var $alert = $(this);
            
            // Ajouter une icône
            var type = $alert.hasClass('alert-success') ? 'check-circle' :
                      $alert.hasClass('alert-danger') ? 'exclamation-circle' :
                      $alert.hasClass('alert-warning') ? 'exclamation-triangle' :
                      $alert.hasClass('alert-info') ? 'info-circle' : 'bell';
            
            $alert.prepend('<i class="fas fa-' + type + '" style="margin-right: 10px; font-size: 18px;"></i>');
            
            // Auto-dismiss après 4.5 secondes
            setTimeout(function() {
                $alert.fadeOut(400, function() {
                    $(this).remove();
                });
            }, 4500);
        });

        // ─── Animation des cartes de stats ──────────────────
        $('.small-box').each(function(index) {
            var $card = $(this);
            setTimeout(function() {
                $card.addClass('animated fadeInUp');
            }, index * 100);
        });

        // ─── Confirmation de suppression ────────────────────
        $('.deletelink, .btn-delete').on('click', function(e) {
            var message = $(this).data('confirm-message') || 
                         'Êtes-vous sûr de vouloir supprimer cet élément ?\n\nCette action est irréversible.';
            if (!confirm(message)) {
                e.preventDefault();
                return false;
            }
        });

        // ─── Raccourci clavier: Ctrl+F pour recherche ──────
        $(document).on('keydown', function(e) {
            if ((e.ctrlKey || e.metaKey) && e.key === 'f') {
                var $searchInput = $('#searchbar, .filter-input, input[type="search"]');
                if ($searchInput.length) {
                    e.preventDefault();
                    $searchInput.first().focus();
                }
            }
        });

        // ─── Animation des badges ──────────────────────────
        $('.badge').each(function() {
            var $badge = $(this);
            if ($badge.hasClass('badge-success') || 
                $badge.hasClass('badge-danger') || 
                $badge.hasClass('badge-warning')) {
                setInterval(function() {
                    $badge.css('transform', 'scale(1.05)');
                    setTimeout(function() {
                        $badge.css('transform', 'scale(1)');
                    }, 300);
                }, 3000);
            }
        });

    });

})(jQuery);