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

  var header=document.getElementById('header');
  if(header && !document.getElementById('pqr-admin-notif')){
    var wrap=document.createElement('div'); wrap.id='pqr-admin-notif'; wrap.className='pqr-admin-notif';
    wrap.innerHTML='<button type="button" aria-label="Notifications"><i class="fas fa-bell"></i><span class="pqr-dot" style="display:none"></span></button><div class="pqr-notif-menu"><div class="pqr-notif-title">Notifications</div><div class="pqr-notif-body"><div class="pqr-notif-empty">Chargement…</div></div></div>';
    var user=document.getElementById('user-tools'); if(user) user.parentNode.insertBefore(wrap,user);
    var button=wrap.querySelector('button'), menu=wrap.querySelector('.pqr-notif-menu'), body=wrap.querySelector('.pqr-notif-body'), dot=wrap.querySelector('.pqr-dot');
    function renderNotifications(data){
      var items=Array.isArray(data.notifications)?data.notifications:[];
      dot.style.display=items.length?'block':'none';
      if(!items.length){body.innerHTML='<div class="pqr-notif-empty">Aucune notification</div>';return}
      body.innerHTML='';
      items.forEach(function(n){
        var url=typeof n.url==='string'?n.url:'';
        if(n.type==='demande_en_attente') url='/admin/pointage/demandemodification/';
        if(n.type==='anomalie' && n.anomalie_id) url='/admin/pointage/anomaliepointage/'+encodeURIComponent(n.anomalie_id)+'/workflow/';
        var item=document.createElement(url?'a':'div'); item.className='pqr-notif-item'; if(url)item.href=url;
        var icon=document.createElement('i'); icon.className='fas '+(n.type==='demande_en_attente'?'fa-pen-to-square':'fa-triangle-exclamation');
        var txt=document.createElement('span'); txt.textContent=n.message||'Notification';
        item.appendChild(icon);item.appendChild(txt);body.appendChild(item);
      });
    }
    function loadNotifications(){fetch('/api/admin-notifications/',{credentials:'same-origin'}).then(function(r){return r.ok?r.json():null}).then(function(d){if(d)renderNotifications(d)}).catch(function(){});}
    button.addEventListener('click',function(e){e.stopPropagation();menu.classList.toggle('is-open');loadNotifications()});
    document.addEventListener('click',function(e){if(!wrap.contains(e.target))menu.classList.remove('is-open')});
    loadNotifications(); setInterval(loadNotifications,60000);
  }

});
})();