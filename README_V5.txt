PS4 Jailbreak Tracker V5 — PWA

Arquivos:
- index.html: aplicativo
- manifest.webmanifest: configuração de instalação PWA
- sw.js: service worker/cache offline/notificações
- icon.svg: ícone do app

Como testar no Android:
1. Coloque os 4 arquivos juntos em uma hospedagem HTTPS.
2. Abra o endereço no Chrome.
3. Use o menu do Chrome > "Adicionar à tela inicial" ou "Instalar app".
4. Abra o app instalado.
5. Toque em "🔔 Notificações" para testar a permissão.

Importante:
- Abrir o index.html diretamente como arquivo não instala uma PWA completa; PWA exige HTTPS (localhost também serve para desenvolvimento).
- A V5 já tem service worker e notificação de teste.
- Notificações automáticas quando surgir uma notícia nova ainda precisam de um backend/serviço de push. Isso será a próxima etapa.
- Os dados de notícias desta versão são a base pesquisada usada na V4; o app não faz coleta automática da internet sozinho.
