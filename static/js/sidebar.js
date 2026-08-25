// Gestion de la barre latérale

document.addEventListener('DOMContentLoaded', function() {
    const sidebar = document.querySelector('.sidebar');
    const sidebarToggle = document.querySelector('.sidebar-toggle');
    const mainContent = document.querySelector('.main-content');
    
    // Toggle de la barre latérale
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            sidebar.classList.toggle('collapsed');
            
            // Sauvegarder l'état dans localStorage
            const isCollapsed = sidebar.classList.contains('collapsed');
            localStorage.setItem('sidebarCollapsed', isCollapsed);
        });
    }
    
    // Restaurer l'état de la barre latérale
    const sidebarCollapsed = localStorage.getItem('sidebarCollapsed') === 'true';
    if (sidebarCollapsed) {
        sidebar.classList.add('collapsed');
    }
    
    // Gestion responsive
    function handleResponsive() {
        if (window.innerWidth <= 768) {
            sidebar.classList.remove('collapsed');
            sidebar.classList.add('mobile');
            sidebarToggle.innerHTML = '<i class="fas fa-times"></i>';
            
            // Cacher la barre latérale par défaut sur mobile
            if (!sidebar.classList.contains('show')) {
                sidebar.style.marginLeft = '-250px';
            }
        } else {
            sidebar.classList.remove('mobile');
            sidebarToggle.innerHTML = '<i class="fas fa-bars"></i>';
            sidebar.style.marginLeft = '0';
        }
    }
    
    // Toggle pour mobile
    if (sidebarToggle) {
        sidebarToggle.addEventListener('click', function() {
            if (window.innerWidth <= 768) {
                if (sidebar.classList.contains('show')) {
                    sidebar.classList.remove('show');
                    sidebar.style.marginLeft = '-250px';
                } else {
                    sidebar.classList.add('show');
                    sidebar.style.marginLeft = '0';
                }
            }
        });
    }
    
    // Fermer la barre latérale en cliquant à l'extérieur (sur mobile)
    document.addEventListener('click', function(event) {
        if (window.innerWidth <= 768 && 
            sidebar.classList.contains('show') &&
            !sidebar.contains(event.target) &&
            !sidebarToggle.contains(event.target)) {
            sidebar.classList.remove('show');
            sidebar.style.marginLeft = '-250px';
        }
    });
    
    // Mettre à jour l'heure
    function updateCurrentTime() {
        const now = new Date();
        const timeString = now.toLocaleTimeString('fr-FR', { 
            hour: '2-digit', 
            minute: '2-digit' 
        });
        const dateString = now.toLocaleDateString('fr-FR', {
            weekday: 'long',
            year: 'numeric',
            month: 'long',
            day: 'numeric'
        });
        
        document.querySelectorAll('.current-time').forEach(el => {
            el.textContent = timeString;
            el.setAttribute('title', dateString);
        });
    }
    
    setInterval(updateCurrentTime, 1000);
    updateCurrentTime();
    
    // Initialiser responsive
    handleResponsive();
    window.addEventListener('resize', handleResponsive);
});