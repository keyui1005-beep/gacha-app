import { fetchWithAuth, apiBase } from './api.js';
import { auth } from './auth.js';
import { items, loadItems, compressImage } from './items.js';

export let currentProposalTargetId = null;
export let currentMypageTrades = { incoming: [], outgoing: [] };
export let _currentChatTradeId = null;
export let _chatSocket = null;
export let _currentRatingTradeId = null;
export let _currentRatingScore = 5;

// ==========================================
// 提案モーダル関連
// ==========================================
export function openProposalModal(itemId) {
  if (!window.currentUserData) {
    alert('ログインが必要です。');
    return window.openLoginModal();
  }

  const targetItem = items.find(it => it.id === itemId);
  const targetText = document.getElementById('proposal-target-text');
  if (targetText) {
    targetText.textContent = targetItem
      ? `対象アイテム: ${window.escapeHtml(targetItem.seriesName)} / ${window.escapeHtml(targetItem.characterName)}`
      : '対象アイテム: -';
  }

  currentProposalTargetId = itemId;

  const radioExisting = document.querySelector('input[name="proposal_type"][value="existing"]');
  if(radioExisting) radioExisting.checked = true;
  toggleProposalType();

  const select = document.getElementById('proposal-selected-item');
  const availableMyItems = items.filter(it => it.isMine && it.status === 'available');

  if (select) {
    if (!availableMyItems.length) {
      select.innerHTML = '<option value="">出品中のアイテムがありません</option>';
      select.disabled = true;
    } else {
      select.disabled = false;
      select.innerHTML = '<option value="">-- アイテムを選択 --</option>' +
        availableMyItems.map(it => `
          <option value="${window.escapeHtml(it.id)}" data-img="${window.escapeHtml(it.imageUrl)}">${window.escapeHtml(it.seriesName)} / ${window.escapeHtml(it.characterName)}</option>
        `).join('');
    }
  }
  updateProposalPreview();

  const modal = document.getElementById('proposal-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

export function closeProposalModal() {
  const modal = document.getElementById('proposal-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
  currentProposalTargetId = null;
}

export function toggleProposalType() {
  const type = document.querySelector('input[name="proposal_type"]:checked')?.value;
  const existingArea = document.getElementById('proposal-existing-area');
  const newArea = document.getElementById('proposal-new-area');
  if(type === 'existing') {
    existingArea.classList.remove('hidden');
    newArea.classList.add('hidden');
  } else {
    existingArea.classList.add('hidden');
    newArea.classList.remove('hidden');
  }
}

export function updateProposalPreview() {
  const select = document.getElementById('proposal-selected-item');
  const wrap = document.getElementById('proposal-preview-wrap');
  const img = document.getElementById('proposal-preview-img');
  if(!select || !wrap || !img) return;
  
  const option = select.options[select.selectedIndex];
  if(option && option.value && option.dataset.img) {
    img.src = option.dataset.img;
    wrap.classList.remove('hidden');
  } else {
    img.src = '';
    wrap.classList.add('hidden');
  }
}

export async function submitProposal() {
  if (!currentProposalTargetId) {
    return alert('対象アイテムが設定されていません。');
  }

  const type = document.querySelector('input[name="proposal_type"]:checked')?.value;
  const submitButton = document.getElementById('proposal-submit');
  let proposedItemId = null;

  if (submitButton) {
    submitButton.textContent = '処理中...';
    submitButton.disabled = true;
  }

  try {
    if (type === 'existing') {
      const selectedItem = document.getElementById('proposal-selected-item');
      if (!selectedItem || !selectedItem.value) {
        throw new Error('提案するアイテムを選択してください。');
      }
      proposedItemId = selectedItem.value;
      
    } else {
      const series = document.getElementById('prop-new-series').value.trim();
      const character = document.getElementById('prop-new-character').value.trim();
      const condition = document.getElementById('prop-new-condition').value;
      const method = document.getElementById('prop-new-method').value;
      const fileInput = document.getElementById('prop-new-file');

      if (!series || !character || !condition || !fileInput.files.length) {
        throw new Error('新規登録の必須項目をすべて入力・選択してください。');
      }

      submitButton.textContent = '画像圧縮中...';
      const compressedFile = await compressImage(fileInput.files[0]);

      submitButton.textContent = 'アイテム登録中...';
      const newItemData = new FormData();
      newItemData.append('series_name', series);
      newItemData.append('character_name', character);
      newItemData.append('exchange_method', method);
      newItemData.append('handover_place', '');
      newItemData.append('condition', condition);
      newItemData.append('status', 'proposing');
      newItemData.append('file', compressedFile);

      const createRes = await fetchWithAuth('/items/', {
        method: 'POST',
        body: newItemData,
      });
      if (!createRes.ok) {
        const errBody = await createRes.json().catch(()=>null);
        throw new Error(errBody?.detail || '新規アイテムの登録に失敗しました。');
      }
      const createdItem = await createRes.json();
      proposedItemId = createdItem.id;
    }

    submitButton.textContent = '提案送信中...';
    const tradeData = new FormData();
    tradeData.append('proposed_item_id', proposedItemId);

    const res = await fetchWithAuth(`/items/${currentProposalTargetId}/trade`, {
      method: 'POST',
      body: tradeData,
    });
    
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || '交換提案に失敗しました。');
    }
    
    alert('交換提案を送信しました。');
    closeProposalModal();
    await loadItems();
    
  } catch (err) {
    alert(err.message || '処理中にエラーが発生しました。');
  } finally {
    if (submitButton) {
      submitButton.textContent = '提案する';
      submitButton.disabled = false;
    }
  }
}

// ==========================================
// 評価モーダル関連
// ==========================================
export function openRatingModal(tradeId) {
  if (!window.currentUserData) {
    return window.openLoginModal();
  }
  _currentRatingTradeId = tradeId;
  _currentRatingScore = 5;
  clearRatingModal();
  setRatingStars(5);
  const modal = document.getElementById('rating-modal');
  if (!modal) return;
  modal.classList.remove('hidden');
  modal.classList.add('flex');
}

export function closeRatingModal() {
  const modal = document.getElementById('rating-modal');
  if (!modal) return;
  modal.classList.add('hidden');
  modal.classList.remove('flex');
  _currentRatingTradeId = null;
}

export function clearRatingModal() {
  const comment = document.getElementById('rating-comment');
  if (comment) comment.value = '';
  const stars = document.querySelectorAll('#rating-stars .rating-star');
  stars.forEach(star => star.classList.remove('text-yellow-400'));
}

export function setRatingStars(score) {
  _currentRatingScore = score;
  const stars = document.querySelectorAll('#rating-stars .rating-star');
  stars.forEach(star => {
    const starScore = Number(star.dataset.score || 0);
    if (starScore <= score) {
      star.classList.add('text-yellow-400');
      star.classList.remove('text-gray-300');
    } else {
      star.classList.add('text-gray-300');
      star.classList.remove('text-yellow-400');
    }
  });
}

export async function submitRating() {
  if (!window.currentUserData) {
    return window.openLoginModal();
  }
  const tradeId = _currentRatingTradeId;
  const score = _currentRatingScore || 5;
  const commentInput = document.getElementById('rating-comment');
  const comment = commentInput ? commentInput.value.trim() : undefined;
  const submitBtn = document.getElementById('rating-submit');
  
  if (submitBtn) {
    submitBtn.disabled = true;
    submitBtn.textContent = '送信中...';
  }

  try {
    if (!tradeId) throw new Error('取引情報がありません。');
    const res = await fetchWithAuth('/ratings', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ trade_id: tradeId, score, comment }),
    });
    if (!res.ok) {
      const errorBody = await res.json().catch(() => null);
      throw new Error(errorBody?.detail || '評価の送信に失敗しました。');
    }
    closeRatingModal();
    alert('評価を送信しました。');
    window.location.reload();
  } catch (error) {
    alert(error.message || '評価の送信に失敗しました。');
  } finally {
    if (submitBtn) {
      submitBtn.textContent = '評価を送信する';
      submitBtn.disabled = false;
    }
  }
}

// ==========================================
// 取引の更新・完了
// ==========================================
export async function updateTradeStatus(tradeId, status) {
  const res = await fetchWithAuth(`/trades/${tradeId}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ status }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => null);
    throw new Error(body?.detail || '更新エラー');
  }
  await loadIncomingTrades();
  await loadItems();
}

export async function completeTrade(tradeId, { sourceButton } = {}) {
  if (!tradeId) return;
  const btn = sourceButton || document.querySelector(`#chat-complete`);
  if (btn) {
    btn.disabled = true;
    btn.textContent = '完了中...';
  }
  try {
    const res = await fetchWithAuth(`/trades/${tradeId}/complete`, {
      method: 'POST',
    });
    if (!res.ok) {
      const body = await res.json().catch(() => null);
      throw new Error(body?.detail || '完了処理に失敗しました');
    }
    alert('取引が完了しました。');
    if (btn && btn.id === 'chat-complete') {
      closeChatModal();
    }
    openRatingModal(tradeId);
    await loadItems();
    if (typeof window.loadIncomingTrades === 'function') await window.loadIncomingTrades();
    if (typeof window.loadChatIncomingTrades === 'function') await window.loadChatIncomingTrades();
    if (typeof window.loadChatOutgoingTrades === 'function') await window.loadChatOutgoingTrades();
  } catch (err) {
    alert(err.message || '完了処理に失敗しました');
  } finally {
    if (btn) {
      btn.disabled = false;
      btn.textContent = '取引を完了する';
    }
  }
}

export async function completeChatTrade() {
  if (!_currentChatTradeId) return;
  await completeTrade(_currentChatTradeId, { sourceButton: document.getElementById('chat-complete') });
}

// ==========================================
// 取引一覧取得・描画
// ==========================================
export async function loadIncomingTrades() {
  try {
    const res = await fetchWithAuth('/trades/incoming');
    if (!res.ok) throw new Error('受信トレードの取得に失敗');
    const trades = await res.json();
    currentMypageTrades.incoming = trades || [];
    renderIncomingTrades(trades || []);
    if (window.renderMyPageList) window.renderMyPageList();
  } catch (err) {
    console.warn('loadIncomingTrades error', err);
    currentMypageTrades.incoming = [];
    renderIncomingTrades([]);
    if (window.renderMyPageList) window.renderMyPageList();
  }
}

export async function loadChatIncomingTrades() {
  try {
    const res = await fetchWithAuth('/trades/incoming');
    if (!res.ok) throw new Error('受信チャット一覧の取得に失敗');
    const trades = await res.json();
    renderChatIncomingTrades((trades || []).filter(trade => trade.status === 'accepted'));
  } catch (err) {
    console.warn('loadChatIncomingTrades error', err);
    renderChatIncomingTrades([]);
  }
}

export async function loadChatOutgoingTrades() {
  try {
    const res = await fetchWithAuth('/trades/outgoing');
    if (!res.ok) throw new Error('送信チャット一覧の取得に失敗');
    const trades = await res.json();
    renderChatOutgoingTrades((trades || []).filter(trade => trade.status === 'accepted'));
  } catch (err) {
    console.warn('loadChatOutgoingTrades error', err);
    renderChatOutgoingTrades([]);
  }
}

export function renderIncomingTrades(trades) {
  const wrap = document.getElementById('incoming-trades-list');
  if (!wrap) return;
  if (!trades || !trades.length) {
    wrap.innerHTML = '<div class="text-sm text-gray-500">受信した交換リクエストはありません。</div>';
    return;
  }
  wrap.innerHTML = trades.map(trade => {
    const applicant = trade.applicant_name || trade.applicant_id || '不明なユーザー';
    const targetInfo = trade.target_series_name ? `対象: ${window.escapeHtml(trade.target_series_name)} / ${window.escapeHtml(trade.target_character_name)}` : '';
    const proposedInfo = trade.proposed_series_name ? `${window.escapeHtml(trade.proposed_series_name)} / ${window.escapeHtml(trade.proposed_character_name)}` : '不明なアイテム';
    const proposedImg = trade.proposal_front_url ? `<img src="${window.escapeHtml(trade.proposal_front_url)}" class="w-12 h-12 object-cover rounded shadow-sm border" alt="提案アイテム" />` : '<div class="w-12 h-12 bg-gray-200 rounded"></div>';
    
    const status = trade.status || '';
    const actions = (status === 'pending') ? `
      <button class="accept-btn bg-green-500 text-white px-3 py-1.5 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}" data-action="accepted">承認</button>
      <button class="reject-btn bg-gray-200 text-gray-800 px-3 py-1.5 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}" data-action="rejected">お断り</button>
    ` : (status === 'accepted' ? `
      <button class="chat-open-btn bg-blue-500 text-white px-3 py-1.5 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}">チャット</button>
      <button class="trade-complete-btn bg-green-600 text-white px-3 py-1.5 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}">取引完了</button>
    ` : `<span class="text-xs text-gray-500 font-semibold mt-2">状態: ${window.escapeHtml(status)}</span>`);
    
    return `
      <div class="p-3 border rounded-lg flex items-center justify-between gap-3 bg-white">
        <div class="flex-1 min-w-0 flex items-center gap-3">
          ${proposedImg}
          <div class="text-sm">
            <div class="font-semibold text-gray-800">申請者: ${window.escapeHtml(applicant)}</div>
            <div class="text-xs text-red-500 font-medium mt-0.5">${targetInfo}</div>
            <div class="text-xs text-gray-600">提案: ${proposedInfo}</div>
          </div>
        </div>
        <div class="flex items-center gap-2 flex-col sm:flex-row">${actions}</div>
      </div>
    `;
  }).join('');

  wrap.querySelectorAll('.accept-btn, .reject-btn').forEach(btn => {
    btn.addEventListener('click', async () => {
      const id = btn.getAttribute('data-id');
      const action = btn.getAttribute('data-action');
      if (!id || !action) return;
      if (!confirm(action === 'accepted' ? 'この交換を承認しますか？' : 'この交換を拒否しますか？')) return;
      try { await updateTradeStatus(id, action); } catch (err) { alert('操作に失敗しました。'); }
    });
  });
  wrap.querySelectorAll('.chat-open-btn').forEach(btn => {
    btn.addEventListener('click', () => { openChatModal(btn.getAttribute('data-id')); });
  });
  wrap.querySelectorAll('.trade-complete-btn').forEach(btn => {
    btn.addEventListener('click', async () => { await completeTrade(btn.getAttribute('data-id'), { sourceButton: btn }); });
  });
}

export function renderChatIncomingTrades(trades) {
  const wrap = document.getElementById('chat-incoming-list');
  if (!wrap) return;
  if (!trades || !trades.length) {
    wrap.innerHTML = '<div class="text-sm text-gray-500">チャット可能な受信取引はありません。</div>';
    return;
  }
  wrap.innerHTML = trades.map(trade => {
    const applicant = trade.applicant_name || trade.applicant_id || '不明なユーザー';
    const targetInfo = trade.target_series_name ? `対象: ${window.escapeHtml(trade.target_series_name)} / ${window.escapeHtml(trade.target_character_name)}` : '';
    const proposedInfo = trade.proposed_series_name ? `${window.escapeHtml(trade.proposed_series_name)} / ${window.escapeHtml(trade.proposed_character_name)}` : '不明なアイテム';
    const proposedImg = trade.proposal_front_url ? `<img src="${window.escapeHtml(trade.proposal_front_url)}" class="w-12 h-12 object-cover rounded shadow-sm border" alt="提案アイテム" />` : '<div class="w-12 h-12 bg-gray-200 rounded"></div>';
    
    return `
      <div class="p-3 border rounded-lg flex items-center justify-between gap-3 bg-white">
        <div class="flex-1 min-w-0 flex items-center gap-3">
          ${proposedImg}
          <div class="text-sm">
            <div class="font-semibold text-gray-800">相手: ${window.escapeHtml(applicant)}</div>
            <div class="text-xs text-red-500 mt-0.5">${targetInfo}</div>
            <div class="text-xs text-gray-600">提案: ${proposedInfo}</div>
          </div>
        </div>
        <div class="flex items-center gap-2 flex-col sm:flex-row">
          <button class="chat-open-btn bg-blue-500 text-white px-3 py-2 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}">チャットを開く</button>
          <button class="trade-complete-btn bg-green-600 text-white px-3 py-2 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}">取引完了</button>
        </div>
      </div>
    `;
  }).join('');
  wrap.querySelectorAll('.chat-open-btn').forEach(btn => {
    btn.addEventListener('click', () => { openChatModal(btn.getAttribute('data-id')); });
  });
  wrap.querySelectorAll('.trade-complete-btn').forEach(btn => {
    btn.addEventListener('click', async () => { await completeTrade(btn.getAttribute('data-id'), { sourceButton: btn }); });
  });
}

export function renderChatOutgoingTrades(trades) {
  const wrap = document.getElementById('chat-outgoing-list');
  if (!wrap) return;
  if (!trades || !trades.length) {
    wrap.innerHTML = '<div class="text-sm text-gray-500">チャット可能な送信済み取引はありません。</div>';
    return;
  }
  wrap.innerHTML = trades.map(trade => {
    const targetInfo = trade.target_series_name ? `対象: ${window.escapeHtml(trade.target_series_name)} / ${window.escapeHtml(trade.target_character_name)}` : '';
    const proposedInfo = trade.proposed_series_name ? `${window.escapeHtml(trade.proposed_series_name)} / ${window.escapeHtml(trade.proposed_character_name)}` : '不明なアイテム';
    const proposedImg = trade.proposal_front_url ? `<img src="${window.escapeHtml(trade.proposal_front_url)}" class="w-12 h-12 object-cover rounded shadow-sm border" alt="提案アイテム" />` : '<div class="w-12 h-12 bg-gray-200 rounded"></div>';
    
    return `
      <div class="p-3 border rounded-lg flex items-center justify-between gap-3 bg-white">
        <div class="flex-1 min-w-0 flex items-center gap-3">
          ${proposedImg}
          <div class="text-sm">
            <div class="font-semibold text-gray-800">送信済みチャット</div>
            <div class="text-xs text-blue-500 mt-0.5">${targetInfo}</div>
            <div class="text-xs text-gray-600">提案: ${proposedInfo}</div>
          </div>
        </div>
        <div class="flex items-center gap-2 flex-col sm:flex-row">
          <button class="chat-open-btn bg-blue-500 text-white px-3 py-2 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}">チャットを開く</button>
          <button class="trade-complete-btn bg-green-600 text-white px-3 py-2 rounded text-sm whitespace-nowrap" data-id="${window.escapeHtml(trade.id)}">取引完了</button>
        </div>
      </div>
    `;
  }).join('');
  wrap.querySelectorAll('.chat-open-btn').forEach(btn => {
    btn.addEventListener('click', () => { openChatModal(btn.getAttribute('data-id')); });
  });
  wrap.querySelectorAll('.trade-complete-btn').forEach(btn => {
    btn.addEventListener('click', async () => { await completeTrade(btn.getAttribute('data-id'), { sourceButton: btn }); });
  });
}

export function renderOutgoingTrades(trades) {
  const wrap = document.getElementById('outgoing-trades-list');
  if (!wrap) return;
  if (!trades || !trades.length) {
    wrap.innerHTML = '<div class="text-sm text-gray-500">送信した交換リクエストはありません。</div>';
    return;
  }
  wrap.innerHTML = trades.map(trade => {
    const targetStatus = trade.status || '不明';
    const statusLabel = targetStatus === 'pending' ? '申請中' : targetStatus === 'accepted' ? '承認済み' : targetStatus === 'rejected' ? 'お断り' : targetStatus === 'completed' ? '完了' : targetStatus === 'cancelled' ? 'キャンセル' : window.escapeHtml(targetStatus);
    
    const targetInfo = trade.target_series_name ? `希望: ${window.escapeHtml(trade.target_series_name)} / ${window.escapeHtml(trade.target_character_name)}` : '';
    const proposedInfo = trade.proposed_series_name ? `${window.escapeHtml(trade.proposed_series_name)} / ${window.escapeHtml(trade.proposed_character_name)}` : '不明なアイテム';
    const proposedImg = trade.proposal_front_url ? `<img src="${window.escapeHtml(trade.proposal_front_url)}" class="w-12 h-12 object-cover rounded shadow-sm border" alt="提案アイテム" />` : '<div class="w-12 h-12 bg-gray-200 rounded"></div>';

    return `
      <div class="p-3 border rounded-lg flex items-center justify-between gap-3 bg-white">
        <div class="flex-1 min-w-0 flex items-center gap-3">
          ${proposedImg}
          <div class="text-sm">
            <div class="font-bold text-gray-800">状況: ${statusLabel}</div>
            <div class="text-xs text-blue-500 font-medium mt-0.5">${targetInfo}</div>
            <div class="text-xs text-gray-600">提案: ${proposedInfo}</div>
          </div>
        </div>
      </div>
    `;
  }).join('');
}


// ==========================================
// WebSocket チャット制御
// ==========================================
export async function openChatModal(tradeId) {
  _currentChatTradeId = tradeId;
  const modal = document.getElementById('chat-modal');
  const title = document.getElementById('chat-title');
  if (title) title.textContent = `チャット - ${tradeId}`;
  if (modal) { modal.classList.remove('hidden'); modal.classList.add('flex'); }
  
  await loadChatMessages(); 
  
  const user = auth.currentUser;
  if (!user) return;
  const token = await user.getIdToken();

  if (_chatSocket) _chatSocket.close();
  const wsProtocol = apiBase.startsWith('https') ? 'wss://' : 'ws://';
  const wsUrl = apiBase.replace(/^https?:\/\//, wsProtocol) + `/ws/trades/${window.escapeHtml(tradeId)}?token=${window.escapeHtml(token)}`;
  _chatSocket = new WebSocket(wsUrl);

  _chatSocket.onmessage = function(event) {
    const msg = JSON.parse(event.data);
    const chatWrap = document.getElementById('chat-messages');
    if (!chatWrap) return;
    
    const isMine = (msg.sender_id === window.currentUserData.id);
    const timeStr = new Date(msg.sent_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
    
    const msgHtml = `
      <div class="flex flex-col ${isMine ? 'items-end' : 'items-start'} mb-4">
        <div class="max-w-[80%] rounded-2xl px-4 py-2 text-sm shadow-sm ${isMine ? 'bg-red-500 text-white rounded-br-none' : 'bg-white border text-gray-800 rounded-bl-none'}">
          ${window.escapeHtml(msg.text)}
        </div>
        <span class="text-[10px] text-gray-400 mt-1 mx-1">${timeStr}</span>
      </div>
    `;
    chatWrap.insertAdjacentHTML('beforeend', msgHtml);
    chatWrap.scrollTop = chatWrap.scrollHeight;
  };
}

export function closeChatModal() {
  const modal = document.getElementById('chat-modal');
  if (modal) { modal.classList.add('hidden'); modal.classList.remove('flex'); }
  _currentChatTradeId = null;
  if (_chatSocket) { _chatSocket.close(); _chatSocket = null; }
}

export async function loadChatMessages() {
  const tradeId = _currentChatTradeId;
  if (!tradeId) return;
  try {
    const res = await fetchWithAuth(`/trades/${tradeId}/messages`);
    if (!res.ok) return;
    const msgs = await res.json();
    renderChatMessages(msgs || []);
  } catch (err) {
    console.warn('loadChatMessages error', err);
  }
}

export function renderChatMessages(msgs) {
  const wrap = document.getElementById('chat-messages');
  if (!wrap) return;
  wrap.innerHTML = '';
  msgs.forEach(m => {
    const isMe = window.currentUserData && window.currentUserData.id === m.sender_id;
    const el = document.createElement('div');
    el.className = isMe ? 'text-right' : 'text-left';
    el.innerHTML = `
      <div class="inline-block max-w-[80%] ${isMe ? 'bg-blue-500 text-white' : 'bg-white text-gray-800'} px-3 py-2 rounded-lg shadow-sm">
        <div class="text-xs text-gray-500 mb-1">${window.escapeHtml(m.sender_name || m.sender_id)}</div>
        <div class="whitespace-pre-wrap">${window.escapeHtml(m.text)}</div>
        <div class="text-xs text-gray-400 mt-1">${window.escapeHtml(new Date(m.sent_at).toLocaleString())}</div>
      </div>
    `;
    wrap.appendChild(el);
  });
  wrap.scrollTop = wrap.scrollHeight;
}

export async function sendChatMessage() {
  const tradeId = _currentChatTradeId;
  if (!tradeId) return;
  const input = document.getElementById('chat-input');
  if (!input) return;
  const text = input.value.trim();
  if (!text) return;
  const btn = document.getElementById('chat-send');
  if (btn) { btn.disabled = true; btn.textContent = '送信中...'; }
  try {
    if (_chatSocket && _chatSocket.readyState === WebSocket.OPEN) {
      _chatSocket.send(text);
    } else {
      throw new Error('通信が切断されています。画面を開き直してください。');
    }
    input.value = '';
  } catch (err) {
    alert(err.message || '送信に失敗しました');
  } finally {
    if (btn) { btn.disabled = false; btn.textContent = '送信'; }
  }
}