(function(){
'use strict';
document.addEventListener('DOMContentLoaded',function(){
  var icons={
    '/admin/pointage/customuser/':'fa-user-gear',
    '/admin/pointage/employe/':'fa-users',
    '/admin/pointage/pointage/':'fa-clock',
    '/admin/pointage/site/':'fa-building',
    '/admin/pointage/scan/':'fa-qrcode',
    '/admin/pointage/poste/':'fa-briefcase',
    '/admin/pointage/jourferie/':'fa-calendar-days',
    '/admin/pointage/configurationpointage/':'fa-sliders',
    '/admin/pointage/anomaliepointage/':'fa-triangle-exclamation',
    '/admin/pointage/pointageaudit/':'fa-shield-halved',
    '/admin/pointage/demandemodification/':'fa-pen-to-square',
    '/admin/auth/group/':'fa-users-gear'
  };
  var nav=document.getElementById('nav-sidebar');
  if(nav){
    nav.querySelectorAll('a').forEach(function(a){
      var href=a.getAttribute('href')||'';
      var key=Object.keys(icons).find(function(k){return href.indexOf(k)===0});
      if(key && !a.querySelector('.pqr-nav-icon')){
        var i=document.createElement('i');
        i.className='fas '+icons[key]+' pqr-nav-icon';
        i.setAttribute('aria-hidden','true');
        a.insertBefore(i,a.firstChild);
      }
    });
    fetch('/api/admin-badge-counts/',{credentials:'same-origin'})
      .then(function(r){return r.ok?r.json():null})
      .then(function(data){
        if(!data)return;
        var badges=[
          ['/admin/pointage/demandemodification/',data.demandes_attente],
          ['/admin/pointage/anomaliepointage/',data.anomalies_ouvertes]
        ];
        badges.forEach(function(item){
          if(!item[1])return;
          var a=nav.querySelector('a[href*="'+item[0]+'"]');
          if(!a)return;
          var b=document.createElement('span'); b.className='pqr-nav-badge'; b.textContent=item[1];
          a.appendChild(b);
        });
      }).catch(function(){});
  }

  document.querySelectorAll('.deletelink,.btn-delete').forEach(function(a){
    a.addEventListener('click',function(e){
      if(!window.confirm('Êtes-vous sûr de vouloir supprimer cet élément ?\n\nCette action est irréversible.')) e.preventDefault();
    });
  });

  document.querySelectorAll('.pqr-form-back').forEach(function(a){
    a.innerHTML='<i class="fas fa-arrow-left" aria-hidden="true"></i> Retour';
  });

  var userTools=document.getElementById('user-tools');
  if(userTools && !document.getElementById('pqr-mobile-nav')){
    var toggle=document.createElement('button');
    toggle.type='button'; toggle.id='pqr-mobile-nav'; toggle.className='pqr-mobile-nav';
    toggle.innerHTML='<i class="fas fa-bars"></i>';
    toggle.setAttribute('aria-label','Ouvrir le menu');
    toggle.onclick=function(){
      if(nav) nav.classList.toggle('pqr-open');
    };
    userTools.parentNode.insertBefore(toggle,userTools);
  }
});
})();