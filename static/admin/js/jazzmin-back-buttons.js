/* Bouton Retour global pour Jazzmin.
 *
 * Ajoute un bouton sur les pages d'administration qui n'en ont pas déjà un.
 * Priorité : historique du navigateur, puis dernier lien utile des breadcrumbs,
 * puis /admin/. Cela évite les liens relatifs fragiles selon la profondeur de l'URL.
 */
(function () {
    'use strict';

    function isExcluded() {
        var path = window.location.pathname;
        return path === '/admin/' ||
            path === '/admin' ||
            path.indexOf('/admin/login') === 0;
    }

    function findFallbackUrl() {
        var breadcrumbs = document.querySelector('.breadcrumbs');
        if (breadcrumbs) {
            var links = breadcrumbs.querySelectorAll('a[href]');
            if (links.length) {
                return links[links.length - 1].href;
            }
        }
        return '/admin/';
    }

    function addBackButton() {
        if (isExcluded()) return;

        var content = document.querySelector('#content-main');
        if (!content) return;
        if (content.querySelector('.pqr-global-back')) return;
        if (document.querySelector('.pqr-global-back')) return;

        var button = document.createElement('a');
        button.className = 'pqr-global-back btn btn-outline-secondary';
        button.href = findFallbackUrl();
        button.innerHTML = '<i class="fas fa-arrow-left mr-1"></i> Retour';
        button.title = 'Retour à la page précédente';
        button.setAttribute('aria-label', 'Retour à la page précédente');

        button.addEventListener('click', function (event) {
            // Si l'utilisateur vient bien d'une autre page, conserver son
            // contexte (filtres/recherche) grâce à l'historique navigateur.
            if (window.history.length > 1 && document.referrer &&
                document.referrer.indexOf(window.location.origin) === 0) {
                event.preventDefault();
                window.history.back();
            }
        });

        var title = content.querySelector('.content-header, h1, .card:first-child');
        if (title && title.parentNode) {
            var wrapper = document.createElement('div');
            wrapper.className = 'pqr-global-back-wrapper';
            wrapper.appendChild(button);
            title.parentNode.insertBefore(wrapper, title);
        } else {
            content.insertBefore(button, content.firstChild);
        }
    }

    function init() {
        addBackButton();
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
