(function(){
  const fab = document.getElementById('chatbot-fab');
  const bot = document.getElementById('chatbot');
  const closeBtn = document.getElementById('chatbot-close');
  const form = document.getElementById('chat-form');
  const input = document.getElementById('chat-text');
  const messages = document.getElementById('chat-messages');

  function openChat(){ bot.style.display = 'flex'; bot.setAttribute('aria-hidden', 'false'); input.focus(); }
  function closeChat(){ bot.style.display = 'none'; bot.setAttribute('aria-hidden', 'true'); }
  function toggleChat(){ const open = bot.style.display === 'flex'; open ? closeChat() : openChat(); }

  fab?.addEventListener('click', toggleChat);
  closeBtn?.addEventListener('click', closeChat);

  form?.addEventListener('submit', function(e){
    e.preventDefault();
    const text = (input.value || '').trim();
    if(!text) return;
    appendMessage(text, 'user');
    input.value = '';
    // Show typing indicator and send to backend
    const typingEl = appendMessage('Typing…', 'bot');
    sendMessage(text)
      .then(reply => {
        replaceTyping(typingEl, reply || 'Sorry, I could not generate a response.');
      })
      .catch(err => {
        console.error(err);
        replaceTyping(typingEl, 'Error contacting the assistant. Please try again.');
      });
  });

  function appendMessage(text, role){
    const el = document.createElement('div');
    el.className = 'message ' + role;
    el.textContent = text;
    messages.appendChild(el);
    messages.scrollTop = messages.scrollHeight;
    return el;
  }

  function replaceTyping(el, text){
    if(el && el.nodeType){
      el.className = 'message bot';
      el.textContent = text;
      messages.scrollTop = messages.scrollHeight;
    }
  }

  async function sendMessage(userText){
    // Call Django backend which proxies to Gemini
    const res = await fetch('/api/chatbot/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: userText })
    });
    
    if(!res.ok){
      let msg = `Server error (${res.status})`;
      try {
        const data = await res.json();
        msg = data.error || msg;
      } catch {}
      throw new Error(msg);
    }
    
    const data = await res.json();
    return data.reply || '';
  }
})();
